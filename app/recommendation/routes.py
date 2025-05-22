from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import BackgroundTasks
import logging
from pydantic import BaseModel
import time
import random
import base64
import json
import hashlib

from app.db import get_db
from app.models import (
    LearningPath, Course, Card, User, UserLearningPath, 
    learning_path_courses,  # Add this import
    learning_path_courses as LearningPathCourse,  # Fixed import
    course_section_association,  # Add this import
    CourseSection
)
from app.recommendation.schemas import (
    LearningPathResponse, CourseResponse, CardResponse, 
    RecommendationResponse, LearningPathRequest, ChatPromptRequest, 
    LearningPathStructureRequest, TaskCreationResponse, EnhancedTaskStatus,
    InterestRecommendationResponse, RecommendationMetadata, SimplifiedLearningPathResponse
)
from app.recommendation.crud import (
    get_recommended_learning_paths, get_recommended_courses, 
    get_recommended_cards, get_interest_learning_paths, get_random_learning_paths
)
from app.services.learning_path_planner import LearningPathPlannerService
from app.users.routes import get_current_active_user_unified
from app.learning_paths.crud import assign_learning_path_to_user
from app.services.background_tasks import schedule_learning_path_generation, schedule_full_learning_path_generation, schedule_structured_learning_path_generation, get_task_status
from app.setup import increment_user_resource_usage, get_user_remaining_resources

router = APIRouter()

@router.get("/recommendations", response_model=RecommendationResponse)
def get_recommendations(
    db: Session = Depends(get_db)
):
    """
    Get recommendations for the landing page:
    - Top 3 learning paths
    - Top 3 courses
    - Top 10 cards
    """
    # Get recommendations without user personalization
    learning_paths = get_recommended_learning_paths(db)
    courses = get_recommended_courses(db)
    cards = get_recommended_cards(db)
    
    return RecommendationResponse(
        learning_paths=[LearningPathResponse.from_orm(path) for path in learning_paths],
        courses=[CourseResponse.from_orm(course) for course in courses],
        cards=[CardResponse.from_orm(card) for card in cards]
    )

@router.get("/learning-paths/{path_id}/full", response_model=LearningPathResponse)
def get_learning_path_full(
    path_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a complete learning path with all its courses, sections, and cards
    """
    learning_path = db.query(LearningPath).filter(LearningPath.id == path_id).first()
    
    if not learning_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Learning path with ID {path_id} not found"
        )
    
    # The response model should handle the relationships automatically
    # if they're properly defined in your Pydantic models
    return LearningPathResponse.from_orm(learning_path)

@router.post("/recommendations/personalized", response_model=RecommendationResponse)
async def get_personalized_recommendations(
    interests: List[str],
    difficulty_level: str = "intermediate",
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """
    Get personalized recommendations based on user interests:
    - Personalized learning paths
    - Recommended courses
    - Relevant cards
    """
    # Use the learning path planner service to generate recommendations
    planner_service = LearningPathPlannerService()
    
    # Generate learning path structure (without creating in DB yet)
    learning_path_data = await planner_service.planner_agent.generate_learning_path(
        interests=interests,
        difficulty_level=difficulty_level,
        estimated_days=30  # Default value, could be made configurable
    )
    
    # Extract components for recommendations
    learning_path_info = learning_path_data.get("learning_path", {})
    courses_data = learning_path_data.get("courses", [])
    
    # Create temporary response objects (not saved to DB)
    learning_path_response = LearningPathResponse(
        id=-1,  # Temporary ID
        title=learning_path_info.get("title"),
        description=learning_path_info.get("description"),
        category=learning_path_info.get("category"),
        difficulty_level=learning_path_info.get("difficulty_level"),
        estimated_days=learning_path_info.get("estimated_days"),
        sections=[],  # Will be populated from courses
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    course_responses = []
    card_keywords = []
    
    # Process courses and extract card keywords
    for course_data in courses_data:
        course_response = CourseResponse(
            id=-1,  # Temporary ID
            title=course_data.get("title"),
            description=course_data.get("description"),
            estimated_days=course_data.get("estimated_days", 7),
            is_template=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        course_responses.append(course_response)
        
        # Extract card keywords from sections
        for section in course_data.get("sections", []):
            keywords = section.get("card_keywords", [])
            card_keywords.extend(keywords)
    
    # Get a sample of cards based on extracted keywords (limit to 10)
    sample_cards = []
    for keyword in card_keywords[:10]:
        # Try to find existing card with similar keyword
        existing_card = db.query(Card).filter(Card.keyword.ilike(f"%{keyword}%")).first()
        if existing_card:
            sample_cards.append(existing_card)
    
    return RecommendationResponse(
        learning_paths=[learning_path_response],
        courses=course_responses[:3],  # Limit to top 3
        cards=[CardResponse.from_orm(card) for card in sample_cards]
    )

@router.post("/learning-paths/generate", response_model=Dict[str, Any])
async def generate_and_save_learning_path(
    background_tasks: BackgroundTasks,
    request: LearningPathRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """
    Generate a complete learning path with courses, sections, and cards,
    then save it to the database and associate it with the current user.
    
    Cards are generated in the background to avoid blocking the request.
    """
    # Check user's daily usage limit for learning paths
    from app.setup import increment_user_resource_usage, get_user_remaining_resources
    
    # Get current resources
    resources = get_user_remaining_resources(db, current_user.id)
    
    # Check if user has reached their daily limit
    if resources["paths"]["remaining"] <= 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Daily limit reached for learning paths. Your limit is {resources['paths']['limit']} paths per day."
        )
    
    # Initialize the learning path planner service
    planner_service = LearningPathPlannerService()
    
    # Generate and save the complete learning path structure
    result = await planner_service.generate_complete_learning_path(
        db=db,
        interests=request.interests,
        user_id=current_user.id,
        difficulty_level=request.difficulty_level,
        estimated_days=request.estimated_days
    )
    
    # Get the learning path ID
    learning_path_id = result["learning_path"]["id"]
    
    # Schedule card generation as a background task
    task_id = schedule_learning_path_generation(
        background_tasks=background_tasks,
        db=db,
        learning_path_structure=result,
        learning_path_id=learning_path_id,
        user_id=current_user.id
    )
    
    # Assign the learning path to the user
    assign_learning_path_to_user(
        db=db,
        user_id=current_user.id,
        learning_path_id=learning_path_id
    )
    
    # Increment user's daily usage for learning paths
    increment_user_resource_usage(db, current_user.id, "paths")
    
    # Get the learning path without waiting for card generation
    learning_path = db.query(LearningPath).filter(LearningPath.id == learning_path_id).first()
    
    if not learning_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Failed to retrieve generated learning path"
        )
    
    # Return the learning path with task ID for tracking progress
    return {
        "learning_path": LearningPathResponse.from_orm(learning_path).model_dump(),
        "task_id": task_id,
        "message": "Learning path created. Cards are being generated in the background."
    }

@router.get("/tasks/{task_id}/status", response_model=EnhancedTaskStatus)
async def get_task_status_endpoint(
    task_id: str,
    current_user: User = Depends(get_current_active_user_unified)
):
    """
    Get the status of a background task.
    """
    status_info = get_task_status(task_id)
    if not status_info:
        raise HTTPException(status_code=404, detail="Task not found")

    # Add a check and potentially defaults before Pydantic validation
    if "task_id" not in status_info:
        logging.error(f"Task {task_id} status info is missing 'task_id'. Data: {status_info}")
        status_info["task_id"] = task_id # Add it back if missing
    if "created_at" not in status_info:
         logging.warning(f"Task {task_id} status info is missing 'created_at'. Setting to default.")
         # Add a sensible default, perhaps from DB if available, or current time
         status_info["created_at"] = datetime.now(timezone.utc)
    if "updated_at" not in status_info:
         logging.warning(f"Task {task_id} status info is missing 'updated_at'. Setting to default.")
         status_info["updated_at"] = datetime.now(timezone.utc) # Or use created_at

    try:
        # Now validate with Pydantic
        return EnhancedTaskStatus(**status_info)
    except ValidationError as e:
        logging.error(f"Error validating task status for {task_id}: {e} - Data: {status_info}")
        # Return a generic error or a simplified status
        raise HTTPException(status_code=500, detail=f"Internal server error validating task status: {e}")

@router.post("/learning-paths/{learning_path_id}/generate-cards", response_model=Dict[str, Any])
async def generate_cards_for_learning_path(
    learning_path_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """
    Generate cards for an existing learning path
    """
    # Check if learning path exists
    learning_path = db.query(LearningPath).filter(LearningPath.id == learning_path_id).first()
    if not learning_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning path not found"
        )
    
    # Check if user has access to this learning path
    user_has_access = False
    
    # Check if learning path is a template (public)
    if learning_path.is_template:
        user_has_access = True
    else:
        # Check if learning path is assigned to user
        user_learning_path = db.query(UserLearningPath).filter(
            UserLearningPath.user_id == current_user.id,
            UserLearningPath.learning_path_id == learning_path_id
        ).first()
        if user_learning_path:
            user_has_access = True
    
    if not user_has_access and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this learning path"
        )
    
    # Get the learning path structure
    # We need to build a structure similar to what generate_complete_learning_path returns
    courses = db.query(Course).join(
        learning_path_courses,  # Use the table name directly
        learning_path_courses.c.course_id == Course.id  # Use .c to access columns
    ).filter(
        learning_path_courses.c.learning_path_id == learning_path_id
    ).order_by(learning_path_courses.c.order_index).all()
    
    # Build the structure needed for card generation
    result_courses = []
    for course in courses:
        sections = db.query(CourseSection).join(
            course_section_association,
            course_section_association.c.section_id == CourseSection.id
        ).filter(
            course_section_association.c.course_id == course.id
        ).order_by(course_section_association.c.order_index).all()
        
        result_sections = []
        for section in sections:
            # For each section, we need to extract or generate keywords
            # This could be from existing cards or section title/description
            keywords = []
            
            # Try to extract keywords from section title and description
            if section.title:
                # Simple approach: use the section title as a keyword
                keywords.append(section.title)
            
            result_sections.append({
                "section_id": section.id,
                "title": section.title,
                "keywords": keywords
            })
        
        result_courses.append({
            "course_id": course.id,
            "title": course.title,
            "sections": result_sections
        })
    
    # Create the structure for the learning path
    learning_path_structure = {
        "learning_path": {
            "id": learning_path.id,
            "title": learning_path.title,
            "description": learning_path.description
        },
        "courses": result_courses
    }
    
    # Schedule card generation as a background task
    task_id = schedule_learning_path_generation(
        background_tasks=background_tasks,
        db=db,
        learning_path_structure=learning_path_structure,
        learning_path_id=learning_path_id,
        user_id=current_user.id
    )
    
    # Return response with task ID for tracking progress
    return {
        "learning_path_id": learning_path_id,
        "task_id": task_id,
        "message": "Card generation started. Cards are being generated in the background."
    }

@router.post("/chat/generate-learning-path", response_model=TaskCreationResponse)
async def generate_learning_path_from_chat(
    request_body: ChatPromptRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """
    Accepts a chat prompt and schedules a background task
    to generate the full learning path. Returns a task ID immediately.
    """
    try:
        prompt = request_body.prompt
        if not prompt:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prompt cannot be empty")

        # Schedule the comprehensive background task
        task_id = schedule_full_learning_path_generation(
            background_tasks=background_tasks,
            db=db,
            prompt=prompt,
            user_id=current_user.id
        )

        # Return the task ID immediately
        return TaskCreationResponse(
            task_id=task_id,
            message="Learning path generation has started. You can check the status using the task ID."
        )

    except Exception as e:
        # Log the specific error that occurred during scheduling
        logging.error(f"Error scheduling learning path generation from chat: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to schedule learning path generation."
        )

@router.post("/learning-paths/create-from-structure", response_model=TaskCreationResponse)
async def create_learning_path_from_structure(
    request: LearningPathStructureRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """
    Creates a learning path, courses, and sections from a predefined structure,
    assigns it to the user, and schedules background card generation (4 cards per section).
    """
    try:
        # Check user's daily usage limit for learning paths
        resources = get_user_remaining_resources(db, current_user.id)
        
        # Check if user has reached their daily limit
        if resources["paths"]["remaining"] <= 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Daily limit reached for learning paths. Your limit is {resources['paths']['limit']} paths per day."
            )
            
        # Increment user's daily usage for learning paths
        increment_user_resource_usage(db, current_user.id, "paths")
        
        # Schedule the entire process (structure saving + card generation)
        task_id = schedule_structured_learning_path_generation(
            background_tasks=background_tasks,
            db=db,
            user_id=current_user.id,
            structure_request=request
        )

        return TaskCreationResponse(
            task_id=task_id,
            message="Learning path creation and card generation initiated. Track progress using the task ID."
        )
    except HTTPException as http_exc:
        # Re-raise HTTPExceptions (like the one from failed task creation)
        raise http_exc
    except Exception as e:
        logging.error(f"Failed to schedule learning path creation from structure: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate learning path creation."
        )

class InterestPathRequest(BaseModel):
    """Request for getting interest-based learning path recommendations"""
    interests: List[str]
    limit: Optional[int] = 3
    refresh_token: Optional[str] = None
    exclude_paths: Optional[List[int]] = None

@router.post("/recommendations/interests", response_model=InterestRecommendationResponse)
async def get_interest_learning_path_recommendations(
    request: InterestPathRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user_unified)
):
    """
    Get simplified learning path recommendations based on interests with support for refreshing results.
    
    This endpoint:
    1. Accepts a list of interest IDs
    2. Returns learning paths recommended for those interests
    3. Provides a refresh token for getting different results next time
    4. Can exclude specific learning path IDs
    
    The refresh token ensures different results on subsequent calls.
    Falls back to random learning paths if interests are invalid or empty.
    Always returns exactly 3 learning paths, filling with random ones if needed.
    """
    # Set a fixed target count of 3 paths to return
    target_count = 3
    actual_limit = request.limit or target_count
    
    # Parse refresh token if provided
    seed = None
    if request.refresh_token:
        try:
            # Decode the refresh token to get the timestamp and seed
            token_data = json.loads(base64.b64decode(request.refresh_token.encode()).decode())
            # We won't use the timestamp for validation, just the seed
            previous_seed = token_data.get('seed')
            
            # Generate a new seed based on the previous one
            if previous_seed:
                seed = (previous_seed * 1.5 + int(time.time())) % 10000
        except Exception as e:
            logging.warning(f"Error parsing refresh token: {e}")
            # Continue with a new seed if token parsing fails
    
    # If no valid seed from refresh token, generate a new one
    if seed is None:
        seed = random.random() * 10000
    
    # Check if interests is valid
    recommendations = []
    used_fallback = False
    filled_with_random = False
    
    try:
        # If interests is empty or None, use fallback
        if not request.interests:
            logging.info("No interests provided, using random fallback paths")
            recommendations = get_random_learning_paths(
                db=db,
                limit=actual_limit,
                exclude_ids=request.exclude_paths
            )
            used_fallback = True
        else:
            # Try to get recommendations based on interests
            recommendations = get_interest_learning_paths(
                db=db,
                interests=request.interests,
                limit=actual_limit,
                seed=seed,
                exclude_ids=request.exclude_paths
            )
            
            # If no recommendations found, use fallback
            if not recommendations:
                logging.info(f"No recommendations found for interests: {request.interests}, using random fallback paths")
                recommendations = get_random_learning_paths(
                    db=db,
                    limit=actual_limit,
                    exclude_ids=request.exclude_paths
                )
                used_fallback = True
    except Exception as e:
        # If any error occurs, use fallback
        logging.error(f"Error getting interest recommendations: {e}", exc_info=True)
        recommendations = get_random_learning_paths(
            db=db,
            limit=actual_limit,
            exclude_ids=request.exclude_paths
        )
        used_fallback = True
    
    # Check if we need to fill with random paths to reach target_count (3)
    current_path_count = len(recommendations)
    
    if current_path_count < target_count:
        logging.info(f"Only found {current_path_count} paths, filling with {target_count - current_path_count} random paths")
        
        # Get IDs of paths we already have to exclude them
        existing_path_ids = [rec["learning_path"].id for rec in recommendations]
        exclude_ids = existing_path_ids
        
        # Also exclude any explicitly requested excludes 
        if request.exclude_paths:
            exclude_ids = list(set(exclude_ids + request.exclude_paths))
        
        # Fill with random paths
        random_paths = get_random_learning_paths(
            db=db,
            limit=target_count - current_path_count,
            exclude_ids=exclude_ids
        )
        
        recommendations.extend(random_paths)
        filled_with_random = True
    
    # Ensure we only return exactly 3 paths (in case we got more than needed)
    recommendations = recommendations[:target_count]
    
    # Map learning path IDs to metadata
    metadata = {}
    learning_paths = []
    
    for rec in recommendations:
        learning_path = rec["learning_path"]
        learning_paths.append(learning_path)
        
        # Store metadata for this learning path
        metadata[learning_path.id] = RecommendationMetadata(
            interest_id=rec["recommendation"]["interest_id"],
            score=rec["recommendation"]["score"],
            priority=rec["recommendation"]["priority"],
            tags=rec["recommendation"]["tags"] if "tags" in rec["recommendation"] and rec["recommendation"]["tags"] else []
        )
    
    # Generate a refresh token for the next request
    next_seed = (seed * 1.3 + int(time.time())) % 10000
    refresh_token = base64.b64encode(
        json.dumps({
            "timestamp": int(time.time()),
            "seed": next_seed,
            "used_fallback": used_fallback,
            "filled_with_random": filled_with_random
        }).encode()
    ).decode()
    
    # Return the response with simplified learning path data
    return InterestRecommendationResponse(
        learning_paths=[SimplifiedLearningPathResponse.from_orm(path) for path in learning_paths],
        metadata=metadata,
        refresh_token=refresh_token
    )
