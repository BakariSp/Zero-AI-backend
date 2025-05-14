#!/usr/bin/env python
"""
Script to retrieve all learning paths except those belonging to users with specific IDs.
This script excludes learning paths assigned to users with IDs 1 or 13.
"""

import os
import sys
import logging
from typing import List
from datetime import datetime
from sqlalchemy import and_, not_, or_
from sqlalchemy.orm import Session, joinedload

# Add the parent directory to the Python path so we can import our app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.db import SessionLocal
from app.models import LearningPath, UserLearningPath, User
from app.learning_paths.schemas import LearningPathResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def get_all_learning_paths_except_users(db: Session, excluded_user_ids: List[int]) -> List[LearningPath]:
    """
    Retrieve all learning paths except those assigned to users with the specified IDs.
    
    Args:
        db: Database session
        excluded_user_ids: List of user IDs whose learning paths should be excluded
        
    Returns:
        List of LearningPath objects
    """
    # First approach: get all learning paths
    all_paths_query = db.query(LearningPath)
    
    # Get all learning path IDs assigned to the excluded users
    excluded_path_ids = (
        db.query(UserLearningPath.learning_path_id)
        .filter(UserLearningPath.user_id.in_(excluded_user_ids))
        .all()
    )
    
    # Extract IDs from result tuples
    excluded_ids = [path_id[0] for path_id in excluded_path_ids]
    
    # Filter out those learning paths
    if excluded_ids:
        filtered_paths = all_paths_query.filter(not_(LearningPath.id.in_(excluded_ids))).all()
    else:
        filtered_paths = all_paths_query.all()
    
    return filtered_paths

def print_learning_path_info(path: LearningPath) -> None:
    """Print formatted information about a learning path."""
    print(f"ID: {path.id}")
    print(f"Title: {path.title}")
    print(f"Description: {path.description[:100]}..." if path.description and len(path.description) > 100 else f"Description: {path.description}")
    print(f"Category: {path.category}")
    print(f"Difficulty: {path.difficulty_level}")
    print(f"Estimated Days: {path.estimated_days}")
    print(f"Created: {path.created_at}")
    print(f"Updated: {path.updated_at}")
    print(f"Is Template: {path.is_template}")
    print("-" * 80)

def export_as_json(paths: List[LearningPath], output_file: str = "learning_paths_export.json") -> None:
    """Export learning paths to a JSON file."""
    import json
    
    def datetime_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")
    
    # Convert to dictionaries for JSON serialization
    paths_data = []
    for path in paths:
        path_dict = {
            "id": path.id,
            "title": path.title,
            "description": path.description,
            "category": path.category,
            "difficulty_level": path.difficulty_level,
            "estimated_days": path.estimated_days,
            "created_at": path.created_at,
            "updated_at": path.updated_at,
            "is_template": path.is_template
        }
        paths_data.append(path_dict)
    
    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(paths_data, f, indent=2, default=datetime_serializer)
    
    logger.info(f"Exported {len(paths_data)} learning paths to {output_file}")

def main():
    """Main function to run the script."""
    excluded_user_ids = [1, 13]
    
    logger.info(f"Retrieving all learning paths except those belonging to users with IDs: {excluded_user_ids}")
    
    # Create a database session
    db = SessionLocal()
    try:
        # Get learning paths
        learning_paths = get_all_learning_paths_except_users(db, excluded_user_ids)
        
        logger.info(f"Found {len(learning_paths)} learning paths")
        
        # Display paths information
        for path in learning_paths:
            print_learning_path_info(path)
        
        # Export to JSON if there are paths
        if learning_paths:
            export_as_json(learning_paths)
    
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    main() 