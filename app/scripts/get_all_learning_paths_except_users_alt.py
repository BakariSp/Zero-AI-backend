#!/usr/bin/env python
"""
Alternative script to retrieve all learning paths except those belonging to users with specific IDs.
This script uses a more efficient SQL approach with subqueries.
"""

import os
import sys
import logging
import csv
from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy import and_, not_, or_, exists
from sqlalchemy.orm import Session, joinedload, selectinload

# Add the parent directory to the Python path so we can import our app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.db import SessionLocal
from app.models import LearningPath, UserLearningPath, User, Course

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def get_learning_paths_not_owned_by_users(db: Session, excluded_user_ids: List[int]) -> List[LearningPath]:
    """
    Retrieve all learning paths that are NOT owned by the specified users.
    This uses a more efficient approach with a subquery.
    
    Args:
        db: Database session
        excluded_user_ids: List of user IDs whose learning paths should be excluded
        
    Returns:
        List of LearningPath objects
    """
    # Create a subquery to find learning paths assigned to excluded users
    subquery = db.query(UserLearningPath.learning_path_id).filter(
        UserLearningPath.user_id.in_(excluded_user_ids)
    ).subquery()
    
    # Query all learning paths that DON'T exist in the subquery
    learning_paths = db.query(LearningPath).filter(
        ~LearningPath.id.in_(subquery)
    ).options(
        # Optionally load related data
        selectinload(LearningPath.courses),
        selectinload(LearningPath.sections)
    ).all()
    
    return learning_paths

def export_to_csv(paths: List[LearningPath], output_file: str = "learning_paths_export.csv") -> None:
    """Export learning paths to a CSV file."""
    fieldnames = [
        "id", "title", "description", "category", "difficulty_level", 
        "estimated_days", "created_at", "updated_at", "is_template", 
        "num_courses", "num_sections"
    ]
    
    rows = []
    for path in paths:
        # Count related items
        num_courses = len(path.courses) if path.courses else 0
        num_sections = len(path.sections) if path.sections else 0
        
        # Create row
        row = {
            "id": path.id,
            "title": path.title,
            "description": path.description,
            "category": path.category,
            "difficulty_level": path.difficulty_level,
            "estimated_days": path.estimated_days,
            "created_at": path.created_at.isoformat() if path.created_at else None,
            "updated_at": path.updated_at.isoformat() if path.updated_at else None,
            "is_template": path.is_template,
            "num_courses": num_courses,
            "num_sections": num_sections
        }
        rows.append(row)
    
    # Write to CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    logger.info(f"Exported {len(rows)} learning paths to {output_file}")

def print_summary(paths: List[LearningPath]) -> None:
    """Print a summary of the learning paths found."""
    if not paths:
        logger.info("No learning paths found matching the criteria.")
        return
    
    # Count by category
    categories = {}
    difficulties = {}
    template_count = 0
    
    for path in paths:
        # Count by category
        if path.category:
            categories[path.category] = categories.get(path.category, 0) + 1
        
        # Count by difficulty level
        if path.difficulty_level:
            difficulties[path.difficulty_level] = difficulties.get(path.difficulty_level, 0) + 1
        
        # Count templates
        if path.is_template:
            template_count += 1
    
    # Print summary information
    print("\n=== SUMMARY ===")
    print(f"Total learning paths: {len(paths)}")
    print(f"Template paths: {template_count}")
    print(f"User custom paths: {len(paths) - template_count}")
    
    print("\nCategories:")
    for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {category}: {count}")
    
    print("\nDifficulty Levels:")
    for difficulty, count in sorted(difficulties.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {difficulty}: {count}")

def main():
    """Main function to run the script."""
    excluded_user_ids = [1, 13]
    
    logger.info(f"Retrieving all learning paths except those belonging to users with IDs: {excluded_user_ids}")
    
    # Create a database session
    db = SessionLocal()
    try:
        # Get learning paths using the more efficient method
        learning_paths = get_learning_paths_not_owned_by_users(db, excluded_user_ids)
        
        logger.info(f"Found {len(learning_paths)} learning paths")
        
        # Print summary
        print_summary(learning_paths)
        
        # Export to CSV
        if learning_paths:
            export_to_csv(learning_paths)
            
            # Also export as JSON for completeness
            from app.scripts.get_all_learning_paths_except_users import export_as_json
            export_as_json(learning_paths, "learning_paths_export_alt.json")
    
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    main() 