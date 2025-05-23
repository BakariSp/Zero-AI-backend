from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db import get_db
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
    check_streak_achievements,
    check_completion_achievements
)
from app.daily_logs.crud import get_user_streak
from app.users.routes import get_current_active_user_unified

router = APIRouter()

@router.get("/achievements", response_model=List[AchievementResponse])
def read_achievements(
    skip: int = 0,
    limit: int = 100,
    achievement_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
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
    current_user: User = Depends(get_current_active_user_unified)
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
    current_user: User = Depends(get_current_active_user_unified)
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
    current_user: User = Depends(get_current_active_user_unified)
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
    current_user: User = Depends(get_current_active_user_unified)
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
    current_user: User = Depends(get_current_active_user_unified)
):
    """Get all achievements earned by the current user"""
    user_achievements = get_user_achievements(db, user_id=current_user.id)
    return user_achievements

@router.post("/users/me/check-achievements", response_model=List[UserAchievementResponse])
def check_user_achievements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """
    Check and award any new achievements for the current user.
    
    This endpoint evaluates and awards both streak-based achievements and
    completion-based achievements (cards completed, courses completed, etc.).
    It's called automatically when users complete cards/courses/paths, but
    can also be called manually to check for new achievements.
    """
    # Check streak achievements
    streak = get_user_streak(db, user_id=current_user.id)
    streak_achievements = check_streak_achievements(db, user_id=current_user.id, streak=streak)
    
    # Check completion achievements
    completion_achievements = check_completion_achievements(db, user_id=current_user.id)
    
    # Combine all achievements
    all_achievements = streak_achievements + completion_achievements
    
    return all_achievements

# Add a duplicate route to match the URL that the frontend is actually using
@router.post("/achievements/users/me/check-achievements", response_model=List[UserAchievementResponse])
def check_user_achievements_alt_path(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """
    Alternative path for checking and awarding achievements.
    This is a duplicate of the endpoint above to handle a different URL pattern
    that the frontend is using.
    """
    # Check streak achievements
    streak = get_user_streak(db, user_id=current_user.id)
    streak_achievements = check_streak_achievements(db, user_id=current_user.id, streak=streak)
    
    # Check completion achievements
    completion_achievements = check_completion_achievements(db, user_id=current_user.id)
    
    # Combine all achievements
    all_achievements = streak_achievements + completion_achievements
    
    return all_achievements 