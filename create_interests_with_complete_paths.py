#!/usr/bin/env python
import os
import sys
import logging
import asyncio
from sqlalchemy.orm import Session
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
from app.services.learning_path_planner import LearningPathPlannerService
from app.learning_paths.crud import get_learning_path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define the interest categories
INTEREST_CATEGORIES = [
    {"id": "tech_basics", "name": "Technology Basics"},
    {"id": "ai_data", "name": "AI & Data"},
    {"id": "creative_worlds", "name": "Creative Worlds"},
    {"id": "business_mind", "name": "Business Mind"},
    {"id": "speak_express", "name": "Speaking & Expression"},
    {"id": "self_growth", "name": "Self Growth"},
    {"id": "mind_body", "name": "Mind & Body"},
    {"id": "deep_thoughts", "name": "Deep Thoughts"},
    {"id": "earth_universe", "name": "Earth & Universe"},
    {"id": "wildcards", "name": "Wild Cards"}
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

# Predefined learning path titles to match
LEARNING_PATH_TITLES = {
    "tech_basics": [
        "Code Your First Website in 30 Days",
        "From Idea to App: Build with No-Code Tools"
    ],
    "ai_data": [
        "Understand How AI Thinks (Without Math)",
        "Intro to Data Storytelling: Make Numbers Speak"
    ],
    "creative_worlds": [
        "Design Thinking for Everyday Creators",
        "Visual Storytelling: From Sketch to Moodboard"
    ],
    "business_mind": [
        "Turn Ideas into Income: Beginner's Startup Map",
        "Personal Finance 101: Spend, Save, Grow"
    ],
    "speak_express": [
        "Speak with Confidence: English for Real Life",
        "Master the Art of Saying What You Mean"
    ],
    "self_growth": [
        "Build Better Habits in 21 Days",
        "Think Clearer: Mental Models for Life"
    ],
    "mind_body": [
        "Intro to Psychology: Why We Do What We Do",
        "Healthy Mind, Healthy You: Basics of Mental Wellness"
    ],
    "deep_thoughts": [
        "Big Questions: What is Consciousness?",
        "Philosophy for Daily Life Decisions"
    ],
    "earth_universe": [
        "Explore the Cosmos: Space 101",
        "Wild Planet: Why Animals Do What They Do"
    ],
    "wildcards": [
        "Curious by Nature: Learn Anything Fast",
        "100 Tiny Things You Never Knew You Loved"
    ]
}

async def generate_learning_path_for_interest(
    db: Session, 
    planner_service: LearningPathPlannerService, 
    interest_id: str, 
    path_title: str, 
    user_id: int = 1
) -> dict:
    """Generate a complete learning path with courses and sections for a specific interest"""
    try:
        # Customize interests and difficulty based on the interest category
        interests = [interest_id.replace("_", " ")]
        difficulty = "beginner"
        
        # Customize the estimated days (to create some variety)
        estimated_days = random.randint(21, 45)
        
        logger.info(f"Generating learning path '{path_title}' for interest '{interest_id}'")
        
        # Use the learning path planner service to generate a complete path
        result = await planner_service.generate_complete_learning_path(
            db=db,
            interests=interests,
            user_id=user_id,
            difficulty_level=difficulty,
            estimated_days=estimated_days
        )
        
        # Extract the learning path ID
        learning_path_id = result["learning_path"]["id"]
        
        # Update the title to match our predefined title
        learning_path = get_learning_path(db, learning_path_id)
        learning_path.title = path_title
        db.add(learning_path)
        db.commit()
        
        logger.info(f"Successfully generated learning path: {path_title} (ID: {learning_path_id})")
        
        return {
            "interest_id": interest_id,
            "learning_path_id": learning_path_id,
            "title": path_title
        }
    except Exception as e:
        logger.error(f"Error generating learning path for {interest_id}: {e}", exc_info=True)
        return None

async def create_interest_recommendations(db: Session, paths_data: list):
    """Create associations between interests and learning paths"""
    recommendations_created = 0
    
    for path_data in paths_data:
        if not path_data:
            continue
            
        interest_id = path_data["interest_id"]
        learning_path_id = path_data["learning_path_id"]
        path_title = path_data["title"]
        
        # Get the index of this path within its interest category
        path_index = LEARNING_PATH_TITLES[interest_id].index(path_title)
        
        # Determine score and priority
        score = 0.95 if path_index == 0 else 0.88
        priority = path_index + 1  # Priority is 1-based (1 is highest)
        
        # Get tags for this interest path
        tags = TAGS_BY_CATEGORY[interest_id][path_index] if path_index < len(TAGS_BY_CATEGORY.get(interest_id, [])) else None
        
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

def update_admin_interests(db: Session):
    """Update admin user's interests to include all interest categories"""
    admin = db.query(User).filter(User.id == 1).first()
    if not admin:
        logger.warning("Admin user (ID=1) not found")
        return False
    
    interests = [interest["id"] for interest in INTEREST_CATEGORIES]
    
    admin.interests = interests
    db.add(admin)
    db.commit()
    
    logger.info(f"Updated admin user's interests: {interests}")
    return True

async def main():
    """Main function to run the script"""
    logger.info("Starting to create interest-based learning paths with complete content")
    
    # Create a DB session
    db = next(get_db())
    
    try:
        # Initialize the learning path planner service
        planner_service = LearningPathPlannerService()
        
        # Generate learning paths for each interest category, two per category
        paths_data = []
        
        for interest in INTEREST_CATEGORIES:
            interest_id = interest["id"]
            # Process each title for this interest
            for path_title in LEARNING_PATH_TITLES[interest_id]:
                # Generate learning path
                path_data = await generate_learning_path_for_interest(
                    db=db, 
                    planner_service=planner_service,
                    interest_id=interest_id,
                    path_title=path_title
                )
                
                if path_data:
                    paths_data.append(path_data)
                    logger.info(f"Completed path: {path_title}")
                
                # Add a small delay to avoid overwhelming the API
                await asyncio.sleep(1)
        
        # Create recommendations based on the generated paths
        recommendations = await create_interest_recommendations(db, paths_data)
        logger.info(f"Created {recommendations} interest-learning path recommendations")
        
        # Update admin interests
        update_admin_interests(db)
        
        logger.info("Successfully completed interest recommendation setup with full learning paths")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main()) 