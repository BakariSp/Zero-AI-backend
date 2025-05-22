from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime, timedelta

from app.db import SessionLocal
from app.users.routes import get_current_active_user_unified
from app.models import User

from . import schemas, crud
from .models import UserDailyUsage

router = APIRouter()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/me", response_model=schemas.UserDailyUsageResponse)
async def get_my_daily_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """
    Get the current user's daily usage for today.
    Creates a new record if one doesn't exist for today.
    """
    # Reset usage if needed (if the last record is from a previous day)
    usage = crud.reset_daily_usage_if_needed(db, current_user.id)
    return usage

@router.post("/increment", response_model=schemas.UserDailyUsageResponse)
async def increment_resource_usage(
    resource_type: str,
    count: int = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """
    Increment the usage count for a specific resource (paths or cards).
    Returns the updated usage record.
    """
    if resource_type not in ['paths', 'cards']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid resource type. Must be 'paths' or 'cards'."
        )
    
    if count <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Count must be a positive integer."
        )
    
    # Reset usage if needed (if the last record is from a previous day)
    crud.reset_daily_usage_if_needed(db, current_user.id)
    
    # Increment usage
    usage, limit_reached = crud.increment_usage(db, current_user.id, resource_type, count)
    
    if limit_reached:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Daily limit reached for {resource_type}. Please try again tomorrow or upgrade your subscription."
        )
    
    return usage

@router.get("/history", response_model=List[schemas.UserDailyUsageResponse])
async def get_usage_history(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """
    Get the user's daily usage history for a date range.
    If no dates are provided, returns the last 30 days.
    """
    if end_date is None:
        end_date = date.today()
    
    if start_date is None:
        start_date = end_date - timedelta(days=30)
    
    # Query history within the date range
    history = db.query(UserDailyUsage).filter(
        UserDailyUsage.user_id == current_user.id,
        UserDailyUsage.usage_date >= start_date,
        UserDailyUsage.usage_date <= end_date
    ).order_by(UserDailyUsage.usage_date.desc()).all()
    
    return history

# Admin-only endpoint to manage user limits
@router.put("/{user_id}", response_model=schemas.UserDailyUsageResponse)
async def update_user_daily_limits(
    user_id: int,
    limits: schemas.UserDailyUsageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """
    Update a user's daily usage limits.
    Admin-only endpoint.
    """
    # Check if the current user is an admin
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update another user's limits"
        )
    
    # Get or create the user's daily usage
    usage = crud.reset_daily_usage_if_needed(db, user_id)
    if not usage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update limits
    updated_usage = crud.update_daily_usage(db, usage.id, limits)
    
    return updated_usage 