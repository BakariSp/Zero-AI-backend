from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional, Dict, Any
import logging

from app.db import get_db
from app.auth.jwt import get_current_active_user
from app.models import User, LearningPath, UserLearningPath, CourseSection
from app.learning_paths.schemas import (
    LearningPathCreate,
    LearningPathResponse,
    LearningPathUpdate,
    UserLearningPathCreate,
    UserLearningPathResponse,
    UserLearningPathUpdate,
    GenerateLearningPathRequest,
    LearningPathBasicInfo,
    GenerateDetailsFromOutlineRequest,
    GenerateCourseTitleRequest,
    CourseSectionCreate,
    CourseSectionUpdate,
    CourseSectionResponse
)
from app.learning_paths.crud import (
    get_learning_path,
    get_learning_paths,
    create_learning_path,
    update_learning_path,
    delete_learning_path,
    get_user_learning_paths,
    get_user_learning_path,
    assign_learning_path_to_user,
    update_user_learning_path_progress,
    get_user_learning_path_by_ids,
    clone_learning_path_for_user
)
from app.services.ai_generator import generate_learning_path_with_ai
from app.services.learning_outline_service import LearningPathOutlineService
from app.services.ai_generator import LearningPathPlannerAgent
from app.services.learning_detail_service import LearningPathDetailService
from app.setup import increment_user_resource_usage, get_user_remaining_resources

router = APIRouter()

@router.get("/learning-paths", response_model=List[LearningPathResponse])
def read_learning_paths(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all learning paths with optional category filter"""
    learning_paths = get_learning_paths(db, skip=skip, limit=limit, category=category)
    return learning_paths

@router.get("/learning-paths/basic", response_model=List[LearningPathBasicInfo])
def read_all_learning_paths_basic(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a basic list of all learning paths (id, name, description, state).
    Requires authentication.
    """
    learning_paths = get_learning_paths(db=db, limit=1000)
    return learning_paths

@router.get("/learning-paths/{path_id}", response_model=LearningPathResponse)
def read_learning_path(
    path_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific learning path by ID"""
    learning_path = get_learning_path(db, path_id=path_id)
    if learning_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning path not found"
        )
    return learning_path

@router.post("/learning-paths", response_model=LearningPathResponse)
def create_new_learning_path(
    learning_path: LearningPathCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new learning path (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return create_learning_path(db=db, path_data=learning_path)

@router.put("/learning-paths/{path_id}", response_model=LearningPathResponse)
def update_existing_learning_path(
    path_id: int,
    learning_path: LearningPathUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update an existing learning path (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return update_learning_path(
        db=db, 
        path_id=path_id, 
        path_data=learning_path.dict(exclude_unset=True)
    )

@router.delete("/learning-paths/{path_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_learning_path(
    path_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a learning path (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    delete_learning_path(db=db, path_id=path_id)
    return {"detail": "Learning path deleted successfully"}

@router.get("/users/me/learning-paths", response_model=List[UserLearningPathResponse])
def read_user_learning_paths(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all learning paths for the current user"""
    return get_user_learning_paths(db=db, user_id=current_user.id)

@router.get("/users/me/learning-paths/basic", response_model=List[LearningPathBasicInfo])
def read_my_learning_paths_basic(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a basic list (id, name, description, state) of learning paths
    assigned to the current user.
    """
    user_path_assignments = get_user_learning_paths(db=db, user_id=current_user.id)
    # Extract the LearningPath object from each assignment
    learning_paths = [assignment.learning_path for assignment in user_path_assignments]
    # Pydantic's response_model handles filtering the fields
    return learning_paths

@router.post("/users/me/learning-paths", response_model=UserLearningPathResponse)
def add_learning_path_to_user(
    user_path: UserLearningPathCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Add an existing learning path to the current user"""
    # Check if learning path exists
    learning_path = get_learning_path(db, path_id=user_path.learning_path_id)
    if not learning_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning path not found"
        )
    
    return assign_learning_path_to_user(
        db=db, 
        user_id=current_user.id, 
        learning_path_id=user_path.learning_path_id
    )

@router.put("/users/me/learning-paths/{path_id}", response_model=UserLearningPathResponse)
def update_user_learning_path(
    path_id: int,
    user_path_update: UserLearningPathUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update progress for a user's learning path"""
    user_path = get_user_learning_path(db, user_id=current_user.id, path_id=path_id)
    if not user_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning path not found for this user"
        )
    
    # Update progress if provided
    if user_path_update.progress is not None:
        user_path = update_user_learning_path_progress(
            db=db,
            user_id=current_user.id,
            path_id=path_id,
            progress=user_path_update.progress
        )
    
    # Update completed_at if provided
    if user_path_update.completed_at is not None:
        user_path.completed_at = user_path_update.completed_at
        db.commit()
        db.refresh(user_path)
    
    return user_path

@router.post("/generate-learning-path", response_model=LearningPathResponse)
async def generate_ai_learning_path(
    request: GenerateLearningPathRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Generate a learning path using AI based on user interests"""
    try:
        # Check user's daily usage limit for learning paths
        # Get current resources
        resources = get_user_remaining_resources(db, current_user.id)
        
        # Check if user has reached their daily limit
        if resources["paths"]["remaining"] <= 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Daily limit reached for learning paths. Your limit is {resources['paths']['limit']} paths per day."
            )
        
        # Generate learning path with AI
        learning_path_data = await generate_learning_path_with_ai(
            interests=request.interests,
            difficulty_level=request.difficulty_level,
            estimated_days=request.estimated_days
        )
        
        # Create the learning path in the database
        learning_path = create_learning_path(db=db, path_data=learning_path_data)
        
        # Assign the learning path to the user
        assign_learning_path_to_user(
            db=db,
            user_id=current_user.id,
            learning_path_id=learning_path.id
        )
        
        # Increment user's daily usage for learning paths
        increment_user_resource_usage(db, current_user.id, "paths")
        
        return learning_path
    
    except Exception as e:
        logging.error(f"Error generating learning path: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate learning path: {str(e)}"
        )

@router.post("/generate-learning-courses")
async def generate_learning_courses(request: GenerateLearningPathRequest):
    try:
        outline_service = LearningPathOutlineService()
        detail_service = LearningPathDetailService()

        # 1. 生成 course outline（课程标题）
        all_titles = await outline_service.generate_outline(
            interests=request.interests,
            difficulty_level=request.difficulty_level,
            estimated_days=request.estimated_days
        )

        # 2. 去掉已有的，最多取 5 个
        new_titles = [title for title in all_titles if title not in request.existing_items][:5]

        # 3. 生成每个 title 对应的 detail（section），限制每个不超过 4 个
        detailed_results = await detail_service.generate_from_outline(
            titles=new_titles,
            difficulty_level=request.difficulty_level,
            estimated_days=request.estimated_days
        )

        # 4. 只保留每个 title 的前 4 个 sections（如果超出）
        structured = []
        for course in detailed_results.get("courses", []):
            structured.append({
                "title": course["title"],
                "sections": course.get("sections", [])[:4]
            })

        return {"courses": structured}

    except Exception as e:
        logging.error(f"Failed to generate courses with sections: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate courses with sections")

@router.post("/generate-course-titles")
async def generate_course_titles(request: GenerateCourseTitleRequest):
    try:
        service = LearningPathOutlineService()
        outline = await service.generate_outline(
            interests=request.interests,
            difficulty_level=request.difficulty_level,
            estimated_days=request.estimated_days
        )
        filtered = [item for item in outline if item not in request.existing_items]
        return {"titles": filtered[:5]}  # 最多返回5个
    except Exception as e:
        logging.error(f"Failed to generate course titles: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate course titles")

@router.post("/generate-sections")
async def generate_sections_from_titles(request: GenerateDetailsFromOutlineRequest):
    try:
        detail_service = LearningPathDetailService()
        detailed_results = await detail_service.generate_from_outline(
            titles=request.titles,
            difficulty_level=request.difficulty_level,
            estimated_days=request.estimated_days
        )

        # 最多保留每个 course 的前 4 个 section
        structured = []
        for course in detailed_results.get("courses", []):
            structured.append({
                "title": course["title"],
                "sections": course.get("sections", [])[:4]
            })

        return {"courses": structured}
    except Exception as e:
        logging.error(f"Failed to generate sections: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate sections")

@router.delete("/users/me/learning-paths/{path_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_learning_path(
    path_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a learning path assigned to the current user.
    This will also delete associated courses, sections, and cards
    if database cascading is configured.
    """
    # 1. Check if the user is actually assigned to this learning path
    user_path_assignment = get_user_learning_path_by_ids(
        db=db, user_id=current_user.id, learning_path_id=path_id
    )

    if not user_path_assignment:
        # If the user is not assigned, they cannot delete it.
        # Return 404 to avoid revealing if the path exists but belongs to someone else.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning path assignment not found for this user."
        )

    # 2. If assigned, proceed with deletion using the existing function
    #    (which relies on DB cascades or needs enhancement)
    try:
        deleted = delete_learning_path(db=db, path_id=path_id)
        if not deleted: # Should not happen if assignment check passed, but good practice
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learning path not found during deletion attempt."
            )
        # No explicit return body needed for 204 No Content
        return

    except HTTPException as e:
        # Re-raise specific HTTP exceptions (like 404 from delete_learning_path)
        raise e
    except Exception as e:
        # Catch potential errors during deletion
        logging.error(f"Error deleting learning path {path_id} for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the learning path."
        )

@router.post("/learning-paths/{path_id}/add-to-my-paths", response_model=UserLearningPathResponse)
def add_learning_path_to_user_collection(
    path_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Add a learning path to the user's collection by creating a personal copy.
    
    This endpoint:
    1. Creates a clone of the learning path with all its courses and sections
    2. Associates the cloned path with the user
    3. Returns the new user-learning path association
    
    This allows users to have their own copy of learning paths they discover through recommendations.
    """
    try:
        # Clone the learning path for the user
        user_path = clone_learning_path_for_user(db, current_user.id, path_id)
        
        # Return the user learning path association
        return UserLearningPathResponse(
            id=user_path.id,
            user_id=user_path.user_id,
            learning_path_id=user_path.learning_path_id,
            progress=user_path.progress,
            start_date=user_path.start_date,
            completed_at=user_path.completed_at,
            created_at=user_path.created_at,
            updated_at=user_path.updated_at,
            learning_path=LearningPathResponse.model_validate(user_path.learning_path)
        )
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        # Log any other errors
        logging.error(f"Error adding learning path to user collection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add learning path to your collection: {str(e)}"
        )
