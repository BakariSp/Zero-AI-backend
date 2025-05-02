#!/usr/bin/env python
import os
import sys
import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_, text

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import get_db, engine
from app.models import (
    Base, LearningPath, User, UserLearningPath, 
    InterestLearningPathRecommendation,
    learning_path_courses, course_section_association, section_cards
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def cleanup_learning_paths(db: Session, start_id: int = 81, end_id: int = 100):
    """
    Remove learning paths with IDs in the specified range and all related data:
    - Backend tasks references
    - Recommendation associations
    - User-learning path associations
    - Course-section associations
    - Section-card associations
    - Course associations
    """
    try:
        # Get all learning paths to delete
        paths_to_delete = db.query(LearningPath).filter(
            and_(
                LearningPath.id >= start_id,
                LearningPath.id <= end_id
            )
        ).all()
        
        path_ids = [path.id for path in paths_to_delete]
        
        if not path_ids:
            logger.info(f"No learning paths found in ID range {start_id}-{end_id}")
            return 0
        
        logger.info(f"Found {len(path_ids)} learning paths to delete: {path_ids}")
        
        # 0. Handle backend_tasks records (new step)
        try:
            # Try to delete from backend_tasks directly
            for path_id in path_ids:
                # Try to set learning_path_id to NULL in backend_tasks
                backend_tasks_count = db.execute(
                    text("UPDATE backend_tasks SET learning_path_id = NULL WHERE learning_path_id = :path_id"),
                    {"path_id": path_id}
                ).rowcount
                
                if backend_tasks_count > 0:
                    logger.info(f"Set NULL for learning_path_id in {backend_tasks_count} backend_tasks records for path {path_id}")
                
                # Alternative approach: try user_tasks if backend_tasks doesn't exist
                user_tasks_count = db.execute(
                    text("UPDATE user_tasks SET learning_path_id = NULL WHERE learning_path_id = :path_id"),
                    {"path_id": path_id}
                ).rowcount
                
                if user_tasks_count > 0:
                    logger.info(f"Set NULL for learning_path_id in {user_tasks_count} user_tasks records for path {path_id}")
                    
            db.commit()
        except Exception as e:
            logger.warning(f"Could not update backend_tasks/user_tasks: {e}")
            db.rollback()
            
            # Try with a more generic approach in case the table name is different
            try:
                # Get all tables in the database
                tables = db.execute(text("SHOW TABLES")).fetchall()
                task_tables = [t[0] for t in tables if 'task' in t[0].lower()]
                
                for table in task_tables:
                    # Check if the table has a learning_path_id column
                    columns = db.execute(text(f"SHOW COLUMNS FROM `{table}`")).fetchall()
                    column_names = [c[0] for c in columns]
                    
                    if 'learning_path_id' in column_names:
                        # Update to set learning_path_id to NULL
                        for path_id in path_ids:
                            count = db.execute(
                                text(f"UPDATE `{table}` SET learning_path_id = NULL WHERE learning_path_id = :path_id"),
                                {"path_id": path_id}
                            ).rowcount
                            if count > 0:
                                logger.info(f"Set NULL for learning_path_id in {count} {table} records for path {path_id}")
                db.commit()
            except Exception as e2:
                logger.warning(f"Could not update task tables: {e2}")
                db.rollback()
        
        # 1. Delete interest recommendations
        recommendation_count = db.query(InterestLearningPathRecommendation).filter(
            InterestLearningPathRecommendation.learning_path_id.in_(path_ids)
        ).delete(synchronize_session=False)
        logger.info(f"Deleted {recommendation_count} interest recommendations")
        
        # 2. Delete user-learning path associations
        user_path_count = db.query(UserLearningPath).filter(
            UserLearningPath.learning_path_id.in_(path_ids)
        ).delete(synchronize_session=False)
        logger.info(f"Deleted {user_path_count} user-learning path associations")
        
        # 3. Find all course IDs associated with these learning paths
        course_ids = []
        for path_id in path_ids:
            # Query course_ids from learning_path_courses association table
            path_courses = db.execute(
                learning_path_courses.select().where(
                    learning_path_courses.c.learning_path_id == path_id
                )
            ).fetchall()
            course_ids.extend([course[1] for course in path_courses])  # [1] is the course_id column
        
        logger.info(f"Found {len(course_ids)} courses associated with these learning paths")
        
        # 4. Find all section IDs associated with these courses
        section_ids = []
        for course_id in course_ids:
            # Query section_ids from course_section_association table
            course_sections = db.execute(
                course_section_association.select().where(
                    course_section_association.c.course_id == course_id
                )
            ).fetchall()
            section_ids.extend([section[1] for section in course_sections])  # [1] is the section_id column
        
        logger.info(f"Found {len(section_ids)} sections associated with these courses")
        
        # 5. Delete section-card associations
        if section_ids:
            card_assoc_count = db.execute(
                section_cards.delete().where(
                    section_cards.c.section_id.in_(section_ids)
                )
            )
            logger.info(f"Deleted section-card associations for {len(section_ids)} sections")
        
        # 6. Delete course-section associations
        if course_ids:
            course_section_count = db.execute(
                course_section_association.delete().where(
                    course_section_association.c.course_id.in_(course_ids)
                )
            )
            logger.info(f"Deleted course-section associations for {len(course_ids)} courses")
        
        # 7. Delete learning path-course associations
        if path_ids:
            path_course_count = db.execute(
                learning_path_courses.delete().where(
                    learning_path_courses.c.learning_path_id.in_(path_ids)
                )
            )
            logger.info(f"Deleted learning path-course associations for {len(path_ids)} paths")
        
        # 8. Finally, delete the learning paths themselves
        for path_id in path_ids:
            try:
                path = db.query(LearningPath).filter(LearningPath.id == path_id).first()
                if path:
                    db.delete(path)
                    db.flush()  # Try to flush each delete individually to catch specific errors
                    logger.info(f"Deleted learning path: ID={path_id}, Title='{path.title}'")
            except IntegrityError as e:
                db.rollback()
                logger.error(f"Failed to delete learning path ID={path_id}: {e}")
                logger.info(f"Attempting direct SQL delete for path ID={path_id}")
                
                # Try more aggressive deletion if needed
                try:
                    # Direct SQL approach as a last resort
                    db.execute(text("DELETE FROM learning_paths WHERE id = :path_id"), {"path_id": path_id})
                    db.commit()
                    logger.info(f"Successfully deleted learning path ID={path_id} using direct SQL")
                except Exception as sql_err:
                    db.rollback()
                    logger.error(f"Failed to delete learning path ID={path_id} even with direct SQL: {sql_err}")
        
        # Commit all changes
        db.commit()
        logger.info(f"Successfully deleted {len(path_ids)} learning paths and all related data")
        
        return len(path_ids)
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error cleaning up learning paths: {str(e)}", exc_info=True)
        raise

def main():
    """Main function"""
    try:
        # Get start and end IDs from command line args if provided
        start_id = int(sys.argv[1]) if len(sys.argv) > 1 else 81
        end_id = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        
        # If only one ID is provided, use it for both start and end
        if len(sys.argv) == 2:
            end_id = start_id
        
        logger.info(f"Starting cleanup of learning paths with IDs {start_id}-{end_id}")
        
        # Create DB session
        db = next(get_db())
        
        # Perform cleanup
        deleted_count = cleanup_learning_paths(db, start_id, end_id)
        
        logger.info(f"Cleanup completed. Deleted {deleted_count} learning paths.")
        
    except Exception as e:
        logger.error(f"An error occurred during cleanup: {str(e)}", exc_info=True)
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    main() 