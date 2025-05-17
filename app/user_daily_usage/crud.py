from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List, Tuple
from datetime import date, datetime, timedelta
from fastapi import HTTPException, status

from .models import UserDailyUsage
from .schemas import UserDailyUsageCreate, UserDailyUsageUpdate
from app.models import User

def get_user_daily_usage(
    db: Session, 
    user_id: int, 
    usage_date: Optional[date] = None
) -> Optional[UserDailyUsage]:
    """
    Get a user's daily usage record for a specific date. 
    If no date is provided, returns today's record.
    """
    if usage_date is None:
        usage_date = date.today()
        
    return db.query(UserDailyUsage).filter(
        UserDailyUsage.user_id == user_id,
        UserDailyUsage.usage_date == usage_date
    ).first()

def get_or_create_daily_usage(
    db: Session, 
    user_id: int, 
    paths_daily_limit: int = 5, 
    cards_daily_limit: int = 20,
    usage_date: Optional[date] = None
) -> UserDailyUsage:
    """
    Get a user's daily usage record or create it if it doesn't exist.
    """
    if usage_date is None:
        usage_date = date.today()
        
    usage = get_user_daily_usage(db, user_id, usage_date)
    
    if not usage:
        # Check if the user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
        # Create new record
        usage = UserDailyUsage(
            user_id=user_id,
            usage_date=usage_date,
            paths_generated=0,
            cards_generated=0,
            paths_daily_limit=paths_daily_limit,
            cards_daily_limit=cards_daily_limit
        )
        db.add(usage)
        db.commit()
        db.refresh(usage)
        
    return usage

def update_daily_usage(
    db: Session, 
    usage_id: int, 
    update_data: UserDailyUsageUpdate
) -> Optional[UserDailyUsage]:
    """
    Update a daily usage record.
    """
    usage = db.query(UserDailyUsage).filter(UserDailyUsage.id == usage_id).first()
    if not usage:
        return None
    
    update_dict = update_data.dict(exclude_unset=True)
    
    for key, value in update_dict.items():
        setattr(usage, key, value)
    
    db.commit()
    db.refresh(usage)
    return usage

def increment_usage(
    db: Session, 
    user_id: int, 
    resource_type: str,
    count: int = 1,
    usage_date: Optional[date] = None
) -> Tuple[UserDailyUsage, bool]:
    """
    Increment the usage count for a specific resource (paths or cards).
    Returns the updated record and a boolean indicating whether the limit was reached.
    """
    if usage_date is None:
        usage_date = date.today()
    
    usage = get_or_create_daily_usage(db, user_id, usage_date=usage_date)
    
    # Check if user has premium subscription (skip limit check for premium users)
    user = db.query(User).filter(User.id == user_id).first()
    is_premium = user and user.subscription_type == 'premium'
    
    if resource_type == 'paths':
        # Check if limit would be exceeded (only for non-premium users)
        if not is_premium and usage.paths_generated + count > usage.paths_daily_limit:
            return usage, True
            
        # Update the count
        usage.paths_generated += count
    elif resource_type == 'cards':
        # Check if limit would be exceeded (only for non-premium users)
        if not is_premium and usage.cards_generated + count > usage.cards_daily_limit:
            return usage, True
            
        # Update the count
        usage.cards_generated += count
    else:
        raise ValueError(f"Invalid resource type: {resource_type}")
    
    db.commit()
    db.refresh(usage)
    
    # Return the updated usage and whether the limit was reached
    return usage, False

def reset_daily_usage_if_needed(
    db: Session, 
    user_id: int
) -> Optional[UserDailyUsage]:
    """
    Check if the user's daily usage record is from a previous day.
    If so, create a new record for today.
    """
    today = date.today()
    usage = get_user_daily_usage(db, user_id)
    
    if not usage:
        # No previous record, create a new one
        return get_or_create_daily_usage(db, user_id)
    
    if usage.usage_date < today:
        # Record is from a previous day, create a new one
        return get_or_create_daily_usage(db, user_id)
    
    # Record is current
    return usage 