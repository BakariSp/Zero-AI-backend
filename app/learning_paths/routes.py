from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import openai

from app.db import SessionLocal
from app.auth.jwt import get_current_active_user
from app.models import User, LearningPath, UserLearningPath
from app.learning_paths.schemas import (
    LearningPathCreate,
    LearningPathResponse,
    LearningPathUpdate,
    UserLearningPathCreate,
    UserLearningPathResponse,
    UserLearningPathUpdate,
    GenerateLearningPathRequest
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
    get_user_learning_path_by_ids
)
from app.services.ai_generator import generate_learning_path_with_ai
from app.services.learning_outline_service import LearningPathOutlineService
from app.services.ai_generator import LearningPathPlannerAgent
from app.services.learning_detail_service import LearningPathDetailService
from app.learning_paths.schemas import GenerateDetailsFromOutlineRequest
from app.services.learning_outline_service import LearningPathOutlineService
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import logging
from app.services.learning_detail_service import LearningPathDetailService
from pydantic import BaseModel
from typing import List, Dict, Any
from pydantic import BaseModel
from typing import List
from app.learning_paths.schemas import GenerateCourseTitleRequest

router = APIRouter()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

# --- Helper function needed in app/learning_paths/crud.py ---
# You might need to add this function if it doesn't exist

def get_user_learning_path_by_ids(db: Session, user_id: int, learning_path_id: int) -> Optional[UserLearningPath]:
    """Retrieve a specific UserLearningPath assignment."""
    return db.query(UserLearningPath).filter(
        UserLearningPath.user_id == user_id,
        UserLearningPath.learning_path_id == learning_path_id
    ).first()
