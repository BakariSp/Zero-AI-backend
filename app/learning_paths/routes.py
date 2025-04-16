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
    update_user_learning_path_progress
)
from app.services.ai_generator import generate_learning_path_with_ai

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