from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
import logging

from app.models import LearningPath, CourseSection, UserLearningPath, User, Course
from app.backend_tasks.models import UserTask
from app.learning_paths.schemas import LearningPathCreate, CourseSectionCreate
from sqlalchemy.orm import joinedload, selectinload
from app.users.crud import check_subscription_limits
from app.user_daily_usage.crud import increment_usage

def get_learning_path(db: Session, path_id: int) -> Optional[LearningPath]:
    return db.query(LearningPath).filter(LearningPath.id == path_id).first()

def get_learning_paths(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    category: Optional[str] = None
) -> List[LearningPath]:
    query = db.query(LearningPath)
    
    if category:
        query = query.filter(LearningPath.category == category)
    
    return query.offset(skip).limit(limit).all()

def create_learning_path(db: Session, path_data: LearningPathCreate) -> LearningPath:
    # Extract sections data if present
    sections_data = path_data.sections if hasattr(path_data, "sections") else None
    
    # Create path without sections first
    path_dict = path_data.dict(exclude={"sections"})
    db_path = LearningPath(**path_dict)
    db.add(db_path)
    db.commit()
    db.refresh(db_path)
    
    # Add sections if provided
    if sections_data:
        for section_data in sections_data:
            db_section = CourseSection(**section_data.dict(), learning_path_id=db_path.id)
            db.add(db_section)
        
        db.commit()
        db.refresh(db_path)
    
    return db_path

def update_learning_path(
    db: Session, 
    path_id: int, 
    path_data: Dict[str, Any]
) -> LearningPath:
    db_path = get_learning_path(db, path_id)
    if not db_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning path not found"
        )
    
    for key, value in path_data.items():
        setattr(db_path, key, value)
    
    db.commit()
    db.refresh(db_path)
    return db_path

def delete_learning_path(db: Session, path_id: int) -> bool:
    db_path = get_learning_path(db, path_id)
    if not db_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning path not found"
        )
    
    # Delete associated UserTasks first to avoid foreign key constraint errors
    db.query(UserTask).filter(UserTask.learning_path_id == path_id).delete(synchronize_session=False)
    
    # Now delete the LearningPath
    db.delete(db_path)
    db.commit()
    return True

def get_user_learning_paths(db: Session, user_id: int) -> List[UserLearningPath]:
    user_paths = (
        db.query(UserLearningPath)
        .options(
            selectinload(UserLearningPath.learning_path)
            .selectinload(LearningPath.courses)
            .selectinload(Course.sections)
            .selectinload(CourseSection.cards)
        )
        .filter(UserLearningPath.user_id == user_id)
        .order_by(UserLearningPath.created_at.desc())
        .all()
    )

    return [path for path in user_paths if path.learning_path]

def get_user_learning_path(db: Session, user_id: int, path_id: int) -> Optional[UserLearningPath]:
    return db.query(UserLearningPath).filter(
        UserLearningPath.user_id == user_id,
        UserLearningPath.learning_path_id == path_id
    ).first()

def assign_learning_path_to_user(
    db: Session, 
    user_id: int, 
    learning_path_id: int
) -> UserLearningPath:
    # Check if user already has this learning path
    existing = get_user_learning_path(db, user_id, learning_path_id)
    if existing:
        return existing
    
    # Check if user has reached their daily limit for learning paths
    has_reached_limit, remaining = check_subscription_limits(db, user_id, 'paths')
    if has_reached_limit:
        # Get the user's daily limit
        from app.user_daily_usage.crud import get_or_create_daily_usage
        daily_usage = get_or_create_daily_usage(db, user_id)
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You have reached your daily limit for learning paths. "
                   f"Your limit is {daily_usage.paths_daily_limit} paths per day. "
                   f"Please try again tomorrow or upgrade your subscription for higher limits."
        )
    
    # Create new user learning path
    db_user_path = UserLearningPath(
        user_id=user_id,
        learning_path_id=learning_path_id,
        progress=0.0
    )
    db.add(db_user_path)
    db.commit()
    db.refresh(db_user_path)
    
    # Increment the daily usage count for paths
    try:
        # This will increment the paths_generated count and check daily limits
        increment_usage(db, user_id, "paths")
        logging.info(f"Incremented daily path usage for user {user_id}")
    except Exception as e:
        logging.error(f"Error incrementing path usage for user {user_id}: {str(e)}")
        # We don't want to fail the operation if the usage tracking fails
        # The path was already created, so we'll return it
    
    return db_user_path

def update_user_learning_path_progress(
    db: Session,
    user_id: int,
    path_id: int,
    progress: float
) -> UserLearningPath:
    db_user_path = get_user_learning_path(db, user_id, path_id)
    if not db_user_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User learning path not found"
        )
    
    db_user_path.progress = progress
    db.commit()
    db.refresh(db_user_path)
    return db_user_path

def get_user_learning_path_by_ids(db: Session, user_id: int, learning_path_id: int) -> Optional[UserLearningPath]:
    """Retrieve a specific UserLearningPath assignment."""
    return db.query(UserLearningPath).filter(
        UserLearningPath.user_id == user_id,
        UserLearningPath.learning_path_id == learning_path_id
    ).first() 