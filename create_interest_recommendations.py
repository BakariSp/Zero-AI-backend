#!/usr/bin/env python
import os
import sys
import logging
from sqlalchemy.orm import Session
from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import json
import random

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import get_db, engine
from app.models import (
    Base, LearningPath, User, UserLearningPath, 
    InterestLearningPathRecommendation
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define the interest-learning path mapping
INTEREST_LEARNING_PATHS = [
  {
    "id": "tech_basics",
    "learning_paths": [
      "Code Your First Website in 30 Days",
      "From Idea to App: Build with No-Code Tools"
    ]
  },
  {
    "id": "ai_data",
    "learning_paths": [
      "Understand How AI Thinks (Without Math)",
      "Intro to Data Storytelling: Make Numbers Speak"
    ]
  },
  {
    "id": "creative_worlds",
    "learning_paths": [
      "Design Thinking for Everyday Creators",
      "Visual Storytelling: From Sketch to Moodboard"
    ]
  },
  {
    "id": "business_mind",
    "learning_paths": [
      "Turn Ideas into Income: Beginner's Startup Map",
      "Personal Finance 101: Spend, Save, Grow"
    ]
  },
  {
    "id": "speak_express",
    "learning_paths": [
      "Speak with Confidence: English for Real Life",
      "Master the Art of Saying What You Mean"
    ]
  },
  {
    "id": "self_growth",
    "learning_paths": [
      "Build Better Habits in 21 Days",
      "Think Clearer: Mental Models for Life"
    ]
  },
  {
    "id": "mind_body",
    "learning_paths": [
      "Intro to Psychology: Why We Do What We Do",
      "Healthy Mind, Healthy You: Basics of Mental Wellness"
    ]
  },
  {
    "id": "deep_thoughts",
    "learning_paths": [
      "Big Questions: What is Consciousness?",
      "Philosophy for Daily Life Decisions"
    ]
  },
  {
    "id": "earth_universe",
    "learning_paths": [
      "Explore the Cosmos: Space 101",
      "Wild Planet: Why Animals Do What They Do"
    ]
  },
  {
    "id": "wildcards",
    "learning_paths": [
      "Curious by Nature: Learn Anything Fast",
      "100 Tiny Things You Never Knew You Loved"
    ]
  }
]

# Sample tag data for learning paths
TAGS_BY_CATEGORY = {
    "tech_basics": [["web", "beginner"], ["no-code", "practical"]],
    "ai_data": [["ai", "conceptual"], ["data", "visualization"]],
    "creative_worlds": [["design", "creative"], ["visual", "creative"]],
    "business_mind": [["entrepreneurship", "practical"], ["finance", "beginner"]],
    "speak_express": [["language", "practical"], ["communication", "intermediate"]],
    "self_growth": [["habits", "practical"], ["productivity", "conceptual"]],
    "mind_body": [["psychology", "conceptual"], ["wellness", "practical"]],
    "deep_thoughts": [["philosophy", "reflective"], ["consciousness", "advanced"]],
    "earth_universe": [["astronomy", "conceptual"], ["biology", "beginner"]],
    "wildcards": [["learning", "meta"], ["curiosity", "fun"]]
}

def create_learning_paths(db: Session):
    """Create learning paths for each interest category"""
    path_id_map = {}  # To store the mapping between path title and ID
    
    # Create learning paths first
    for interest in INTEREST_LEARNING_PATHS:
        interest_id = interest["id"]
        for i, path_title in enumerate(interest["learning_paths"]):
            # Create a description based on the title
            description = f"A learning path for {interest_id.replace('_', ' ')} that helps you {path_title.lower()}."
            
            # Set some default values with slight randomization
            est_days = random.randint(21, 45)
            difficulty = "beginner" if i == 0 else "intermediate"
            
            # Create the learning path
            learning_path = LearningPath(
                title=path_title,
                description=description,
                category=interest_id.replace("_", " ").title(),
                difficulty_level=difficulty,
                estimated_days=est_days,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                is_template=True
            )
            
            db.add(learning_path)
            try:
                # Flush to get the ID
                db.flush()
                logger.info(f"Created learning path: {path_title} (ID: {learning_path.id})")
                
                # Store the ID for later use
                path_id_map[path_title] = learning_path.id
            except IntegrityError as e:
                db.rollback()
                logger.error(f"Failed to create learning path {path_title}: {e}")
                # Try to get the existing path
                existing_path = db.query(LearningPath).filter(LearningPath.title == path_title).first()
                if existing_path:
                    path_id_map[path_title] = existing_path.id
                    logger.info(f"Using existing learning path: {path_title} (ID: {existing_path.id})")
    
    db.commit()
    return path_id_map

def create_interest_recommendations(db: Session, path_id_map: dict):
    """Create associations between interests and learning paths"""
    recommendations_created = 0
    
    for interest in INTEREST_LEARNING_PATHS:
        interest_id = interest["id"]
        for i, path_title in enumerate(interest["learning_paths"]):
            # Get the learning path ID from the map
            learning_path_id = path_id_map.get(path_title)
            if not learning_path_id:
                logger.warning(f"Learning path ID not found for {path_title}")
                continue
            
            # Determine score and priority
            score = 0.95 if i == 0 else 0.88
            priority = i + 1  # Priority is 1-based (1 is highest)
            
            # Get tags for this interest path
            tags = TAGS_BY_CATEGORY[interest_id][i] if i < len(TAGS_BY_CATEGORY.get(interest_id, [])) else None
            
            # Create the recommendation
            recommendation = InterestLearningPathRecommendation(
                interest_id=interest_id,
                learning_path_id=learning_path_id,
                score=score,
                priority=priority,
                tags=tags,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            db.add(recommendation)
            try:
                db.flush()
                recommendations_created += 1
                logger.info(f"Created recommendation: {interest_id} -> {path_title} (score: {score}, priority: {priority})")
            except IntegrityError as e:
                db.rollback()
                logger.error(f"Failed to create recommendation {interest_id} -> {path_title}: {e}")
    
    db.commit()
    return recommendations_created

def assign_learning_paths_to_admin(db: Session, path_id_map: dict):
    """Assign all learning paths to the admin user (ID=1)"""
    # Check if admin user exists
    admin = db.query(User).filter(User.id == 1).first()
    if not admin:
        logger.warning("Admin user (ID=1) not found")
        return 0
    
    assignments_created = 0
    
    for path_title, path_id in path_id_map.items():
        # Check if assignment already exists
        existing = db.query(UserLearningPath).filter(
            UserLearningPath.user_id == 1,
            UserLearningPath.learning_path_id == path_id
        ).first()
        
        if existing:
            logger.info(f"Learning path {path_title} already assigned to admin")
            continue
        
        # Create new assignment
        assignment = UserLearningPath(
            user_id=1,
            learning_path_id=path_id,
            progress=0.0,
            start_date=datetime.now(),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(assignment)
        try:
            db.flush()
            assignments_created += 1
            logger.info(f"Assigned learning path {path_title} to admin")
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Failed to assign learning path {path_title} to admin: {e}")
    
    db.commit()
    return assignments_created

def update_admin_interests(db: Session):
    """Update admin user's interests to include all interest categories"""
    admin = db.query(User).filter(User.id == 1).first()
    if not admin:
        logger.warning("Admin user (ID=1) not found")
        return False
    
    interests = [interest["id"] for interest in INTEREST_LEARNING_PATHS]
    
    admin.interests = interests
    db.add(admin)
    db.commit()
    
    logger.info(f"Updated admin user's interests: {interests}")
    return True

def main():
    """Main function to run the script"""
    logger.info("Starting to create interest-based learning path recommendations")
    
    # Create a DB session
    db = next(get_db())
    
    try:
        # Create learning paths
        path_id_map = create_learning_paths(db)
        logger.info(f"Created {len(path_id_map)} learning paths")
        
        # Create recommendations
        recommendations = create_interest_recommendations(db, path_id_map)
        logger.info(f"Created {recommendations} interest-learning path recommendations")
        
        # Assign learning paths to admin
        assignments = assign_learning_paths_to_admin(db, path_id_map)
        logger.info(f"Assigned {assignments} learning paths to admin user")
        
        # Update admin interests
        update_admin_interests(db)
        
        logger.info("Successfully completed interest recommendation setup")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main() 