from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db import SessionLocal
from app.auth.jwt import get_current_active_user
from app.models import User, Achievement
from app.achievements.schemas import (
    AchievementCreate,
    AchievementResponse,
    AchievementUpdate,
    UserAchievementResponse
)
from app.achievements.crud import (
    get_achievement,
    get_achievements,
    create_achievement,
    update_achievement,
    delete_achievement,
    get_user_achievements,
    award_achievement_to_user,
    check_streak_achievements
)
from app.daily_logs.crud import get_user_streak

router = APIRouter()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/achievements", response_model=List[AchievementResponse])
def read_achievements(
    skip: int = 0,
    limit: int = 100,
    achievement_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all achievements with optional type filter"""
    achievements = get_achievements(
        db, 
        skip=skip, 
        limit=limit, 
        achievement_type=achievement_type
    )
    return achievements

@router.get("/achievements/{achievement_id}", response_model=AchievementResponse)
def read_achievement(
    achievement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific achievement by ID"""
    achievement = get_achievement(db, achievement_id=achievement_id)
    if achievement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Achievement not found"
        )
    return achievement

@router.post("/achievements", response_model=AchievementResponse)
def create_new_achievement(
    achievement: AchievementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new achievement (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return create_achievement(db=db, achievement_data=achievement)

@router.put("/achievements/{achievement_id}", response_model=AchievementResponse)
def update_existing_achievement(
    achievement_id: int,
    achievement: AchievementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update an existing achievement (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return update_achievement(
        db=db, 
        achievement_id=achievement_id, 
        achievement_data=achievement.dict(exclude_unset=True)
    )

@router.delete("/achievements/{achievement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_achievement(
    achievement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete an achievement (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    delete_achievement(db=db, achievement_id=achievement_id)
    return {"detail": "Achievement deleted successfully"}

@router.get("/users/me/achievements", response_model=List[UserAchievementResponse])
def read_user_achievements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all achievements earned by the current user"""
    user_achievements = get_user_achievements(db, user_id=current_user.id)
    return user_achievements

@router.post("/users/me/check-achievements", response_model=List[UserAchievementResponse])
def check_user_achievements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Check and award any new achievements for the current user"""
    # Check streak achievements
    streak = get_user_streak(db, user_id=current_user.id)
    streak_achievements = check_streak_achievements(db, user_id=current_user.id, streak=streak)
    
    # Could add more achievement checks here
    
    return streak_achievements 