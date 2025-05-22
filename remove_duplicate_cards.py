#!/usr/bin/env python3
import os
import sys
import argparse
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from collections import defaultdict
from dotenv import load_dotenv
import urllib.parse

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def get_database_url():
    """Get database URL from environment variables or use default for PostgreSQL"""
    db_user = os.environ.get('DB_USER', 'postgres.ecwdxlkvqiqyjffcovby')
    db_password = os.environ.get('DB_PASSWORD', 'usvWwFHsvcAEymNQ')
    db_host = os.environ.get('DB_HOST', 'aws-0-ap-southeast-1.pooler.supabase.com')
    db_port = os.environ.get('DB_PORT', '6543')
    db_name = os.environ.get('DB_NAME', 'postgres')
    
    # URL encode the password to handle special characters
    encoded_password = urllib.parse.quote_plus(db_password) if db_password else ""
    
    # Use PostgreSQL connection string
    return f"postgresql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"

def connect_to_database():
    """Connect to the database and return a session"""
    try:
        db_url = get_database_url()
        logging.info(f"Connecting to database with URL: {db_url.split('@')[1]}")  # Log URL without credentials
        
        # Configure the engine with connection pooling for PostgreSQL
        engine = create_engine(
            db_url,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True
        )
        
        # Try to connect and verify connection works
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logging.info("Database connection test successful")
        
        Session = sessionmaker(bind=engine)
        return Session()
    except SQLAlchemyError as e:
        logging.error(f"Database connection error: {e}")
        logging.info("Try setting correct database credentials in environment variables:")
        logging.info("  DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME")
        sys.exit(1)

def get_learning_paths(db, path_id=None):
    """Get all learning paths or a specific one"""
    try:
        if path_id:
            query = text("""
                SELECT id, title FROM learning_paths 
                WHERE id = :path_id
            """)
            return db.execute(query, {"path_id": path_id}).fetchall()
        else:
            query = text("""
                SELECT id, title FROM learning_paths
            """)
            return db.execute(query).fetchall()
    except SQLAlchemyError as e:
        logging.error(f"Database error getting learning paths: {e}")
        return []

def get_learning_path_courses(db, path_id):
    """Get all courses in a learning path"""
    try:
        query = text("""
            SELECT c.id, c.title
            FROM courses c
            JOIN learning_path_courses lpc ON c.id = lpc.course_id
            WHERE lpc.learning_path_id = :path_id
            ORDER BY lpc.order_index
        """)
        return db.execute(query, {"path_id": path_id}).fetchall()
    except SQLAlchemyError as e:
        logging.error(f"Database error getting courses for path {path_id}: {e}")
        return []

def get_course_sections(db, course_id):
    """Get all sections in a course"""
    try:
        query = text("""
            SELECT cs.id, cs.title
            FROM course_sections cs
            JOIN course_section_association csa ON cs.id = csa.section_id
            WHERE csa.course_id = :course_id
            ORDER BY csa.order_index
        """)
        return db.execute(query, {"course_id": course_id}).fetchall()
    except SQLAlchemyError as e:
        logging.error(f"Database error getting sections for course {course_id}: {e}")
        return []

def get_section_cards(db, section_id):
    """Get all cards in a section"""
    try:
        query = text("""
            SELECT c.id, c.keyword, c.question, sc.order_index
            FROM cards c
            JOIN section_cards sc ON c.id = sc.card_id
            WHERE sc.section_id = :section_id
            ORDER BY sc.order_index
        """)
        return db.execute(query, {"section_id": section_id}).fetchall()
    except SQLAlchemyError as e:
        logging.error(f"Database error getting cards for section {section_id}: {e}")
        return []

def get_all_cards_in_learning_path(db, path_id):
    """Get all cards across all sections in a learning path"""
    all_cards = []
    courses = get_learning_path_courses(db, path_id)
    
    # Also get sections directly under learning path (if any)
    try:
        lp_sections_query = text("""
            SELECT id, title
            FROM course_sections
            WHERE learning_path_id = :path_id
            ORDER BY order_index
        """)
        lp_sections = db.execute(lp_sections_query, {"path_id": path_id}).fetchall()
        
        for section in lp_sections:
            section_id = section[0]
            section_title = section[1]
            cards = get_section_cards(db, section_id)
            for card in cards:
                all_cards.append({
                    "card_id": card[0],
                    "keyword": card[1],
                    "question": card[2],
                    "order_index": card[3],
                    "section_id": section_id,
                    "section_title": section_title,
                    "course_id": None,
                    "course_title": None
                })
    except SQLAlchemyError as e:
        logging.error(f"Error fetching sections for learning path {path_id}: {e}")
    
    # Get cards from course sections
    for course in courses:
        course_id = course[0]
        course_title = course[1]
        sections = get_course_sections(db, course_id)
        
        for section in sections:
            section_id = section[0]
            section_title = section[1]
            cards = get_section_cards(db, section_id)
            
            for card in cards:
                all_cards.append({
                    "card_id": card[0],
                    "keyword": card[1],
                    "question": card[2],
                    "order_index": card[3],
                    "section_id": section_id,
                    "section_title": section_title,
                    "course_id": course_id,
                    "course_title": course_title
                })
    
    return all_cards

def find_duplicate_cards(cards):
    """Find duplicate cards in a learning path"""
    # Use card_id as the key for duplicates
    card_occurrences = defaultdict(list)
    
    for card in cards:
        card_occurrences[card["card_id"]].append(card)
    
    # Only return cards that appear more than once
    duplicates = {card_id: occurrences for card_id, occurrences in card_occurrences.items() 
                 if len(occurrences) > 1}
    
    return duplicates

def remove_card_from_section(db, card_id, section_id, dry_run=True):
    """Remove a card from a section"""
    try:
        if dry_run:
            logging.info(f"DRY RUN: Would remove card {card_id} from section {section_id}")
            return True
        
        # First check if this card is already present in the user_section_cards table
        user_section_query = text("""
            SELECT usc.user_section_id, us.user_id
            FROM user_section_cards usc
            JOIN user_sections us ON usc.user_section_id = us.id
            WHERE usc.card_id = :card_id
            AND us.section_template_id = :section_id
        """)
        user_sections = db.execute(user_section_query, {
            "card_id": card_id, 
            "section_id": section_id
        }).fetchall()
        
        # Remove from user_section_cards if present
        for user_section in user_sections:
            user_section_id = user_section[0]
            user_id = user_section[1]
            
            logging.info(f"Removing card {card_id} from user_section {user_section_id} (user: {user_id})")
            
            delete_user_section_card_query = text("""
                DELETE FROM user_section_cards
                WHERE user_section_id = :user_section_id AND card_id = :card_id
            """)
            db.execute(delete_user_section_card_query, {
                "user_section_id": user_section_id,
                "card_id": card_id
            })
        
        # Now remove from the section_cards association table
        delete_query = text("""
            DELETE FROM section_cards
            WHERE section_id = :section_id AND card_id = :card_id
        """)
        
        result = db.execute(delete_query, {
            "section_id": section_id,
            "card_id": card_id
        })
        
        # Re-index the remaining cards in the section
        reindex_query = text("""
            SET @idx := 0;
            UPDATE section_cards
            SET order_index = (@idx := @idx + 1)
            WHERE section_id = :section_id
            ORDER BY order_index;
        """)
        
        db.execute(text("SET @idx := 0;"))
        db.execute(text("""
            UPDATE section_cards
            SET order_index = (@idx := @idx + 1)
            WHERE section_id = :section_id
            ORDER BY order_index;
        """), {"section_id": section_id})
        
        db.commit()
        
        logging.info(f"Successfully removed card {card_id} from section {section_id}")
        return True
    
    except SQLAlchemyError as e:
        logging.error(f"Database error removing card {card_id} from section {section_id}: {e}")
        db.rollback()
        return False

def update_section_progress(db, section_id, dry_run=True):
    """Update progress for a section based on card completion"""
    try:
        if dry_run:
            logging.info(f"DRY RUN: Would update progress for section {section_id}")
            return
        
        # Find all user sections for this template section
        user_sections_query = text("""
            SELECT id, user_id
            FROM user_sections
            WHERE section_template_id = :section_id
        """)
        
        user_sections = db.execute(user_sections_query, {"section_id": section_id}).fetchall()
        
        for user_section in user_sections:
            user_section_id = user_section[0]
            user_id = user_section[1]
            
            # Count total cards in this user section
            total_cards_query = text("""
                SELECT COUNT(*) 
                FROM user_section_cards
                WHERE user_section_id = :user_section_id
            """)
            
            total_cards = db.execute(total_cards_query, {
                "user_section_id": user_section_id
            }).scalar() or 0
            
            if total_cards == 0:
                continue
                
            # Count completed cards
            completed_cards_query = text("""
                SELECT COUNT(*) 
                FROM user_section_cards
                WHERE user_section_id = :user_section_id
                AND is_completed = TRUE
            """)
            
            completed_cards = db.execute(completed_cards_query, {
                "user_section_id": user_section_id
            }).scalar() or 0
            
            # Calculate progress
            progress = round((completed_cards / total_cards) * 100, 2) if total_cards > 0 else 0.0
            
            # Update user section progress
            update_query = text("""
                UPDATE user_sections
                SET progress = :progress
                WHERE id = :user_section_id
            """)
            
            db.execute(update_query, {
                "progress": progress,
                "user_section_id": user_section_id
            })
            
            logging.info(f"Updated section {section_id} progress for user {user_id} to {progress}%")
        
        db.commit()
    
    except SQLAlchemyError as e:
        logging.error(f"Database error updating progress for section {section_id}: {e}")
        db.rollback()

def update_course_and_path_progress(db, path_id, course_id=None, dry_run=True):
    """Update progress for a course and learning path"""
    try:
        if dry_run:
            if course_id:
                logging.info(f"DRY RUN: Would update progress for course {course_id} and path {path_id}")
            else:
                logging.info(f"DRY RUN: Would update progress for path {path_id}")
            return
        
        # Get all users assigned to this learning path
        users_query = text("""
            SELECT user_id
            FROM user_learning_paths
            WHERE learning_path_id = :path_id
        """)
        
        users = db.execute(users_query, {"path_id": path_id}).fetchall()
        
        for user_row in users:
            user_id = user_row[0]
            
            # If course_id is specified, update that specific course
            if course_id:
                # Get all sections in this course
                section_ids_query = text("""
                    SELECT section_id
                    FROM course_section_association
                    WHERE course_id = :course_id
                """)
                
                section_ids = [row[0] for row in db.execute(section_ids_query, {
                    "course_id": course_id
                }).fetchall()]
                
                if not section_ids:
                    continue
                
                # Get all user sections for this user and these template sections
                user_sections_query = text("""
                    SELECT id, progress
                    FROM user_sections
                    WHERE user_id = :user_id
                    AND section_template_id IN :section_ids
                """)
                
                user_sections = db.execute(user_sections_query, {
                    "user_id": user_id,
                    "section_ids": tuple(section_ids) if len(section_ids) > 1 else f"({section_ids[0]})"
                }).fetchall()
                
                if not user_sections:
                    continue
                
                # Calculate average progress
                total_progress = sum(user_section[1] for user_section in user_sections)
                avg_progress = round(total_progress / len(user_sections), 2)
                
                # Update user course progress
                update_course_query = text("""
                    UPDATE user_courses
                    SET progress = :progress
                    WHERE user_id = :user_id
                    AND course_id = :course_id
                """)
                
                db.execute(update_course_query, {
                    "progress": avg_progress,
                    "user_id": user_id,
                    "course_id": course_id
                })
                
                logging.info(f"Updated course {course_id} progress for user {user_id} to {avg_progress}%")
            
            # Update learning path progress
            # Get all courses in this learning path
            course_ids_query = text("""
                SELECT course_id
                FROM learning_path_courses
                WHERE learning_path_id = :path_id
            """)
            
            course_ids = [row[0] for row in db.execute(course_ids_query, {
                "path_id": path_id
            }).fetchall()]
            
            if not course_ids:
                continue
            
            # Get all user courses for this user and these courses
            user_courses_query = text("""
                SELECT id, progress
                FROM user_courses
                WHERE user_id = :user_id
                AND course_id IN :course_ids
            """)
            
            user_courses = db.execute(user_courses_query, {
                "user_id": user_id,
                "course_ids": tuple(course_ids) if len(course_ids) > 1 else f"({course_ids[0]})"
            }).fetchall()
            
            if not user_courses:
                continue
            
            # Calculate average progress
            total_progress = sum(user_course[1] for user_course in user_courses)
            avg_progress = round(total_progress / len(user_courses), 2)
            
            # Update user learning path progress
            update_path_query = text("""
                UPDATE user_learning_paths
                SET progress = :progress
                WHERE user_id = :user_id
                AND learning_path_id = :path_id
            """)
            
            db.execute(update_path_query, {
                "progress": avg_progress,
                "user_id": user_id,
                "path_id": path_id
            })
            
            logging.info(f"Updated learning path {path_id} progress for user {user_id} to {avg_progress}%")
        
        db.commit()
    
    except SQLAlchemyError as e:
        logging.error(f"Database error updating progress for path {path_id}: {e}")
        db.rollback()

def process_learning_path(db, path_id, dry_run=True):
    """Process a learning path to find and remove duplicate cards"""
    try:
        # Get all cards in the learning path
        cards = get_all_cards_in_learning_path(db, path_id)
        logging.info(f"Found {len(cards)} cards in learning path {path_id}")
        
        # Find duplicate cards
        duplicates = find_duplicate_cards(cards)
        
        if not duplicates:
            logging.info(f"No duplicate cards found in learning path {path_id}")
            return 0
        
        logging.info(f"Found {len(duplicates)} duplicate card IDs in learning path {path_id}")
        
        # Keep track of affected sections and courses
        affected_sections = set()
        affected_courses = set()
        
        # Process each duplicate card
        for card_id, occurrences in duplicates.items():
            # Sort by course_id, section_id, and order_index to ensure consistent removal
            # We want to keep the first occurrence (smallest order_index)
            sorted_occurrences = sorted(
                occurrences, 
                key=lambda x: (
                    x["course_id"] or float('inf'),  # Handle None course_id
                    x["section_id"], 
                    x["order_index"]
                )
            )
            
            # Keep the first occurrence, remove all others
            keep = sorted_occurrences[0]
            remove = sorted_occurrences[1:]
            
            logging.info(f"Card {card_id} ({keep['keyword']}) appears {len(occurrences)} times in learning path {path_id}")
            logging.info(f"  Keeping: Section {keep['section_id']} ({keep['section_title']}), " +
                        f"Course: {keep['course_id'] or 'None'} ({keep['course_title'] or 'None'})")
            
            for card in remove:
                logging.info(f"  Removing: Section {card['section_id']} ({card['section_title']}), " +
                            f"Course: {card['course_id'] or 'None'} ({card['course_title'] or 'None'})")
                
                # Remove card from section
                success = remove_card_from_section(db, card_id, card['section_id'], dry_run)
                
                if success:
                    affected_sections.add(card['section_id'])
                    if card['course_id']:
                        affected_courses.add(card['course_id'])
        
        # Update progress for affected sections and courses
        for section_id in affected_sections:
            update_section_progress(db, section_id, dry_run)
        
        for course_id in affected_courses:
            update_course_and_path_progress(db, path_id, course_id, dry_run)
        
        # Update learning path progress
        update_course_and_path_progress(db, path_id, None, dry_run)
        
        return len(duplicates)
    
    except Exception as e:
        logging.error(f"Error processing learning path {path_id}: {e}")
        return 0

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Remove duplicate cards from learning paths')
    parser.add_argument('--path-id', type=int, help='Process a specific learning path ID')
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without making changes')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--check-connection', action='store_true', help='Only check database connection and exit')
    args = parser.parse_args()
    
    # Set logging level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Verbose logging enabled")
    
    try:
        # Connect to the database
        logging.info("Connecting to database...")
        db = connect_to_database()
        
        # If only checking connection, exit after successful connection
        if args.check_connection:
            logging.info("Database connection successful! Exiting...")
            return
        
        # Get learning paths to process
        if args.path_id:
            logging.info(f"Getting learning path with ID {args.path_id}...")
            learning_paths = get_learning_paths(db, args.path_id)
            if not learning_paths:
                logging.error(f"Learning path with ID {args.path_id} not found")
                return
        else:
            logging.info("Getting all learning paths...")
            learning_paths = get_learning_paths(db)
            
        if not learning_paths:
            logging.error("No learning paths found. Check database connection and permissions.")
            return
        
        logging.info(f"Found {len(learning_paths)} learning paths to process")
        
        # Debug info about dry run mode
        if args.dry_run:
            logging.info("DRY RUN mode enabled - no changes will be made to the database")
        
        # Process each learning path
        total_duplicates = 0
        for path in learning_paths:
            path_id = path[0]
            path_title = path[1]
            
            logging.info(f"Processing learning path {path_id}: {path_title}")
            duplicates = process_learning_path(db, path_id, args.dry_run)
            total_duplicates += duplicates
        
        # Final summary
        if args.dry_run:
            logging.info(f"DRY RUN: Would have removed {total_duplicates} duplicate cards across {len(learning_paths)} learning paths")
        else:
            logging.info(f"Successfully removed {total_duplicates} duplicate cards across {len(learning_paths)} learning paths")
    
    except KeyboardInterrupt:
        logging.info("Process interrupted by user")
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        # Close database connection if it exists
        if 'db' in locals():
            logging.debug("Closing database connection...")
            db.close()
            logging.debug("Database connection closed")

if __name__ == "__main__":
    main() 