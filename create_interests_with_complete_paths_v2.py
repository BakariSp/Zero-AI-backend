#!/usr/bin/env python
import os
import sys
import asyncio
import logging
import json
import random
import time
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import get_db, engine
from app.models import (
    Base, LearningPath, User, UserLearningPath, 
    InterestLearningPathRecommendation
)
from app.recommendation.schemas import LearningPathStructureRequest, CourseStructureInput, SectionStructureInput
from app.services.background_tasks import schedule_structured_learning_path_generation, get_task_status
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

# Predefined course and section structures for each learning path
# This makes the generation more deterministic and faster than AI generation
PREDEFINED_STRUCTURES = {
    "Code Your First Website in 30 Days": {
        "courses": [
            {
                "title": "HTML Fundamentals",
                "sections": [
                    {"title": "Understanding HTML Structure"},
                    {"title": "Working with Text and Links"},
                    {"title": "Adding Images and Media"}
                ]
            },
            {
                "title": "CSS Styling Basics",
                "sections": [
                    {"title": "CSS Selectors and Properties"},
                    {"title": "Layout and Positioning"},
                    {"title": "Responsive Design Principles"}
                ]
            },
            {
                "title": "Your First Web Project",
                "sections": [
                    {"title": "Planning Your Website"},
                    {"title": "Building the Pages"},
                    {"title": "Publishing Your Site"}
                ]
            }
        ]
    },
    # Add more predefined structures for other learning paths...
}

async def create_learning_path_from_structure(
    db: Session,
    interest_id: str,
    path_title: str, 
    user_id: int = 1
) -> dict:
    """Generate a complete learning path with courses and sections for a specific interest using the structure endpoint"""
    try:
        # Get structure for the path (predefined or generate a basic one)
        structure = PREDEFINED_STRUCTURES.get(path_title)
        if not structure:
            # Create a basic structure if no predefined one exists
            structure = {
                "courses": [
                    {
                        "title": f"{path_title} - Part 1",
                        "sections": [
                            {"title": "Getting Started"},
                            {"title": "Basic Concepts"},
                            {"title": "Practical Application"}
                        ]
                    },
                    {
                        "title": f"{path_title} - Part 2",
                        "sections": [
                            {"title": "Intermediate Techniques"},
                            {"title": "Advanced Skills"},
                            {"title": "Final Project"}
                        ]
                    }
                ]
            }
        
        # Convert to the expected schema format
        courses = []
        for course_data in structure["courses"]:
            sections = []
            for section_data in course_data["sections"]:
                sections.append(SectionStructureInput(
                    title=section_data["title"]
                ))
            
            courses.append(CourseStructureInput(
                title=course_data["title"],
                sections=sections
            ))
        
        # Create the full request structure
        structure_request = LearningPathStructureRequest(
            prompt=f"Create a learning path about {interest_id.replace('_', ' ')} with title: {path_title}",
            title=path_title,
            courses=courses,
            difficulty_level="beginner",
            estimated_days=30
        )
        
        # Schedule the background task
        task_id = schedule_structured_learning_path_generation(
            background_tasks=None,  # We're not in a FastAPI context
            db=db,
            user_id=user_id,
            structure_request=structure_request
        )
        
        logger.info(f"Started task {task_id} for learning path: {path_title}")
        
        # Wait for the task to complete (or timeout after 2 minutes)
        learning_path_id = None
        start_time = time.time()
        timeout = 120  # 2 minutes timeout
        
        while time.time() - start_time < timeout:
            # Sleep to avoid hammering the status endpoint
            await asyncio.sleep(5)
            
            # Check task status
            status = get_task_status(task_id)
            if not status:
                logger.warning(f"Task {task_id} not found")
                continue
                
            # Extract learning path ID if available
            if status.get("learning_path_id"):
                learning_path_id = status.get("learning_path_id")
                
            # Check if task is completed or failed
            if status.get("status") in ["completed", "failed"]:
                if status.get("status") == "completed":
                    logger.info(f"Task {task_id} completed successfully")
                else:
                    logger.error(f"Task {task_id} failed: {status.get('error_details', 'Unknown error')}")
                break
                
            # Log progress
            logger.info(f"Task {task_id} in progress: {status.get('stage')} ({status.get('progress')}%)")
        
        if not learning_path_id:
            logger.error(f"Failed to get learning path ID for task {task_id}")
            return None
            
        # Update the title if needed
        learning_path = get_learning_path(db, learning_path_id)
        if learning_path.title != path_title:
            learning_path.title = path_title
            db.add(learning_path)
            db.commit()
            logger.info(f"Updated learning path title to {path_title}")
        
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
        
        # Check if recommendation already exists
        existing_rec = db.query(InterestLearningPathRecommendation).filter(
            InterestLearningPathRecommendation.interest_id == interest_id,
            InterestLearningPathRecommendation.learning_path_id == learning_path_id
        ).first()
        
        if existing_rec:
            logger.info(f"Recommendation already exists for {interest_id} -> {path_title}")
            existing_rec.score = score
            existing_rec.priority = priority
            existing_rec.tags = tags
            db.add(existing_rec)
            recommendations_created += 1
            continue
        
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
    logger.info("Starting to create interest-based learning paths with complete content using structured path generation")
    
    # Create a DB session
    db = next(get_db())
    
    try:
        # Generate learning paths for each interest category, one at a time to avoid overwhelming the system
        paths_data = []
        
        # By default, start with just a few paths to test
        # You can uncomment the full list once you've confirmed it works
        categories_to_process = [
            {"id": "tech_basics", "paths": ["Code Your First Website in 30 Days"]},
            {"id": "ai_data", "paths": ["Understand How AI Thinks (Without Math)"]},
            # Add more as needed, or use the full list below
        ]
        
        # Full list (uncomment to process all)
        """
        categories_to_process = []
        for interest in INTEREST_CATEGORIES:
            interest_id = interest["id"]
            categories_to_process.append({
                "id": interest_id,
                "paths": LEARNING_PATH_TITLES[interest_id]
            })
        """
        
        for category in categories_to_process:
            interest_id = category["id"]
            for path_title in category["paths"]:
                # Generate learning path
                path_data = await create_learning_path_from_structure(
                    db=db, 
                    interest_id=interest_id,
                    path_title=path_title
                )
                
                if path_data:
                    paths_data.append(path_data)
                    logger.info(f"Completed path: {path_title}")
                
                # Add a delay to avoid overwhelming the system
                await asyncio.sleep(3)
        
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