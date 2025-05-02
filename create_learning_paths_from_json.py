#!/usr/bin/env python
import os
import sys
import asyncio
import logging
import json
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

async def create_learning_path_from_structure(
    db: Session,
    interest_id: str,
    path_title: str,
    path_structure: dict,
    user_id: int = 1,
    task_timeout: int = 180  # 3 minutes timeout
) -> dict:
    """Generate a complete learning path with courses and sections using the provided structure"""
    try:
        # Convert to the expected schema format
        courses = []
        for course_data in path_structure["courses"]:
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
        
        # Get required imports to run directly
        from app.services.background_tasks import task_status, _run_structured_path_creation_task
        from app.db import SessionLocal
        from app.backend_tasks.models import UserTask
        
        # Generate a unique task ID
        task_id = f"struct_path_gen_{user_id}_{int(time.time())}"
        logger.info(f"Starting task {task_id} for learning path: {path_title}")
        
        # Create a UserTask if the record exists
        try:
            from app.backend_tasks.schemas import UserTaskCreate, TaskStatusEnum
            from app.backend_tasks.crud import create_user_task
            create_user_task(db, UserTaskCreate(task_id=task_id, user_id=user_id, status=TaskStatusEnum.QUEUED))
        except Exception as e:
            # It's okay if this fails - user_tasks might not exist in our DB schema
            logger.warning(f"Could not create user task record: {e}")
        
        # Initialize task status
        task_status[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "stage": "queued",
            "progress": 0,
            "message": "Task queued for processing.",
            "learning_path_id": None,
            "total_sections": None,
            "sections_completed": 0,
            "total_cards_expected": None,
            "cards_completed": 0,
            "section_status": {}, 
            "errors": [],
            "error_details": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        # Run the task directly (this is normally scheduled as a background task)
        await _run_structured_path_creation_task(
            task_id=task_id,
            db_session_factory=SessionLocal,
            user_id=user_id,
            structure_request=structure_request,
            timeout_seconds=task_timeout
        )
        
        # Check status and get learning path ID
        status = task_status.get(task_id, {})
        learning_path_id = status.get("learning_path_id")
        
        if not learning_path_id:
            logger.error(f"Failed to get learning path ID for task {task_id}")
            return None
        
        # Log success
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
    
    # Group paths by interest for proper indexing
    paths_by_interest = {}
    for path_data in paths_data:
        if not path_data:
            continue
        
        interest_id = path_data["interest_id"]
        if interest_id not in paths_by_interest:
            paths_by_interest[interest_id] = []
        
        paths_by_interest[interest_id].append(path_data)
    
    # Process each path
    for path_data in paths_data:
        if not path_data:
            continue
            
        interest_id = path_data["interest_id"]
        learning_path_id = path_data["learning_path_id"]
        path_title = path_data["title"]
        
        # Get the index of this path within its interest category
        interest_paths = paths_by_interest.get(interest_id, [])
        path_index = 0  # Default to first position
        
        for i, p in enumerate(interest_paths):
            if p["title"] == path_title:
                path_index = i
                break
        
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
    try:
        admin = db.query(User).filter(User.id == 1).first()
        if not admin:
            logger.warning("Admin user (ID=1) not found")
            return False
        
        # Get all unique interest categories from the structures
        interests = list(STRUCTURES_BY_INTEREST.keys())
        if not interests:
            logger.warning("No interests found in STRUCTURES_BY_INTEREST")
            return False
        
        # Update the admin's interests
        admin.interests = interests
        db.add(admin)
        db.commit()
        
        logger.info(f"Updated admin user's interests: {interests}")
        return True
    except Exception as e:
        logger.error(f"Error updating admin interests: {e}", exc_info=True)
        db.rollback()
        return False

# Function to extract learning paths to process from command line arguments
def get_paths_to_process(structures_by_interest):
    """Extract paths to process based on command line arguments"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate learning paths from JSON structures')
    parser.add_argument('--interest', type=str, help='Process a specific interest category')
    parser.add_argument('--path', type=str, help='Process a specific learning path title')
    parser.add_argument('--limit', type=int, default=0, help='Limit the number of paths to process')
    parser.add_argument('--timeout', type=int, default=180, help='Timeout in seconds for each path generation task (default: 180)')
    args = parser.parse_args()
    
    paths_to_process = []
    
    if args.interest and args.path:
        # Process a specific path in a specific interest
        if args.interest in structures_by_interest and args.path in structures_by_interest[args.interest]:
            paths_to_process.append({
                "interest_id": args.interest,
                "path_title": args.path,
                "structure": structures_by_interest[args.interest][args.path]
            })
    elif args.interest:
        # Process all paths in a specific interest
        if args.interest in structures_by_interest:
            for path_title, structure in structures_by_interest[args.interest].items():
                paths_to_process.append({
                    "interest_id": args.interest,
                    "path_title": path_title,
                    "structure": structure
                })
    else:
        # Process all paths (or up to limit)
        for interest_id, paths in structures_by_interest.items():
            for path_title, structure in paths.items():
                paths_to_process.append({
                    "interest_id": interest_id,
                    "path_title": path_title,
                    "structure": structure
                })
    
    # Apply limit if specified
    if args.limit > 0 and len(paths_to_process) > args.limit:
        paths_to_process = paths_to_process[:args.limit]
    
    return paths_to_process, args.timeout

async def main():
    """Main function to run the script"""
    global STRUCTURES_BY_INTEREST
    
    try:
        # Load learning path structures from JSON file
        try:
            with open('learning_path_structures.json', 'r') as f:
                STRUCTURES_BY_INTEREST = json.load(f)
            total_paths = sum(len(paths) for paths in STRUCTURES_BY_INTEREST.values())
            logger.info(f"Loaded {total_paths} learning path structures")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading learning path structures: {e}")
            return
        
        # Get paths to process based on command line arguments
        paths_to_process, task_timeout = get_paths_to_process(STRUCTURES_BY_INTEREST)
        
        if not paths_to_process:
            logger.warning("No learning paths to process")
            return
            
        total_to_process = len(paths_to_process)
        logger.info(f"STARTING BATCH GENERATION: Will process {total_to_process} learning paths")
        logger.info(f"Timeout set to {task_timeout} seconds per learning path")
        
        # Print a summary of what will be processed
        interest_summary = {}
        for path_info in paths_to_process:
            interest_id = path_info["interest_id"]
            if interest_id not in interest_summary:
                interest_summary[interest_id] = 0
            interest_summary[interest_id] += 1
        
        for interest, count in interest_summary.items():
            logger.info(f"  - {interest}: {count} paths")
        
        # Create a DB session
        db = next(get_db())
        
        try:
            # Generate learning paths one at a time
            paths_data = []
            successful_count = 0
            failed_count = 0
            overall_start_time = time.time()
            
            for i, path_info in enumerate(paths_to_process):
                interest_id = path_info["interest_id"]
                path_title = path_info["path_title"]
                structure = path_info["structure"]
                
                progress_str = f"[{i+1}/{total_to_process}]"
                print("\n" + "="*80)
                logger.info(f"{progress_str} STARTING: {interest_id} - \"{path_title}\"")
                print("="*80)
                
                # Generate learning path
                start_time = time.time()
                path_data = await create_learning_path_from_structure(
                    db=db, 
                    interest_id=interest_id,
                    path_title=path_title,
                    path_structure=structure,
                    task_timeout=task_timeout
                )
                duration = time.time() - start_time
                
                if path_data:
                    paths_data.append(path_data)
                    successful_count += 1
                    print("\n" + "-"*80)
                    logger.info(f"{progress_str} COMPLETED: {interest_id} - \"{path_title}\" (ID: {path_data['learning_path_id']}) in {duration:.1f}s")
                    logger.info(f"Progress: {successful_count} complete, {failed_count} failed, {total_to_process - i - 1} remaining")
                    print("-"*80)
                else:
                    failed_count += 1
                    print("\n" + "-"*80)
                    logger.warning(f"{progress_str} FAILED: {interest_id} - \"{path_title}\" after {duration:.1f}s")
                    logger.info(f"Progress: {successful_count} complete, {failed_count} failed, {total_to_process - i - 1} remaining")
                    print("-"*80)
                
                # Add a delay between path creations
                if i < total_to_process - 1:  # Don't wait after the last one
                    next_path = paths_to_process[i+1]
                    logger.info(f"Waiting 2 seconds before starting next path: {next_path['interest_id']} - \"{next_path['path_title']}\"")
                    await asyncio.sleep(2)
            
            # Create recommendations for all successfully generated paths
            if paths_data:
                print("\n" + "="*80)
                logger.info(f"CREATING RECOMMENDATIONS: {len(paths_data)} learning path associations")
                print("="*80)
                
                recommendations = await create_interest_recommendations(db, paths_data)
                logger.info(f"Created {recommendations} interest-learning path recommendations")
                
                # Update admin interests
                if update_admin_interests(db):
                    logger.info("Successfully updated admin user interests")
                else:
                    logger.warning("Failed to update admin user interests")
            
            total_duration = time.time() - overall_start_time
            hours, remainder = divmod(total_duration, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = ''
            if hours > 0:
                time_str += f"{int(hours)} hours, "
            if minutes > 0 or hours > 0:
                time_str += f"{int(minutes)} minutes, "
            time_str += f"{seconds:.1f} seconds"
            
            print("\n" + "="*80)
            logger.info(f"GENERATION COMPLETE: {successful_count} paths created, {failed_count} failed")
            logger.info(f"Total time: {time_str}")
            print("="*80)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main()) 