from sqlalchemy.orm import Session
from datetime import date
from typing import Optional

# Import all models that need to be initialized directly from app.models
from app.models import User, UserDailyUsage, LearningPath, Card
# Import DailyTask separately
from app.user_tasks.models import DailyTask

def setup_database_relationships():
    """
    Function to initialize database relationships after all models are defined.
    This resolves circular import issues by calling this function after all models are loaded.
    """
    # The relationship definitions are now in their respective model classes
    # This function exists in case additional setup is needed in the future
    pass

def initialize_user_daily_usage(db: Session, user_id: int) -> UserDailyUsage:
    """
    Initialize or reset a user's daily usage tracking.
    Creates a new daily usage record if one doesn't exist for today,
    or resets an existing one if it's from a previous day.
    
    Args:
        db: Database session
        user_id: User ID to initialize usage for
        
    Returns:
        User's daily usage record for today
    """
    today = date.today()
    
    # Check if the user already has a usage record for today
    usage = db.query(UserDailyUsage).filter(
        UserDailyUsage.user_id == user_id,
        UserDailyUsage.usage_date == today
    ).first()
    
    if usage:
        return usage
    
    # Get the user to determine subscription limits
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"User with ID {user_id} not found")
    
    # Determine limits based on user subscription
    subscription_type = user.subscription_type or 'free'
    
    # Set daily limits according to subscription tiers as per documentation
    if subscription_type == 'free':
        paths_limit = 3
        cards_limit = 20
    elif subscription_type == 'standard':
        paths_limit = 10
        cards_limit = 50
    elif subscription_type == 'premium':
        paths_limit = 100
        cards_limit = 500
    else:  # Default to free tier limits
        paths_limit = 3
        cards_limit = 20
    
    # Create new daily usage record
    new_usage = UserDailyUsage(
        user_id=user_id,
        usage_date=today,
        paths_generated=0,
        cards_generated=0,
        paths_daily_limit=paths_limit,
        cards_daily_limit=cards_limit
    )
    
    db.add(new_usage)
    db.commit()
    db.refresh(new_usage)
    
    return new_usage

def increment_user_resource_usage(
    db: Session, 
    user_id: int, 
    resource_type: str,
    count: int = 1
) -> tuple[UserDailyUsage, bool]:
    """
    Increment the usage count for a specific resource (paths or cards).
    
    Args:
        db: Database session
        user_id: User ID
        resource_type: Type of resource ('paths' or 'cards')
        count: Number to increment by (default: 1)
        
    Returns:
        Tuple of (UserDailyUsage object, bool indicating if limit was exceeded)
    """
    # Get or create today's usage record
    usage = initialize_user_daily_usage(db, user_id)
    
    # Check resource type and increment
    if resource_type == 'paths':
        # Check if limit would be exceeded
        if usage.paths_generated + count > usage.paths_daily_limit:
            return usage, True
            
        # Update the count
        usage.paths_generated += count
    elif resource_type == 'cards':
        # Check if limit would be exceeded
        if usage.cards_generated + count > usage.cards_daily_limit:
            return usage, True
            
        # Update the count
        usage.cards_generated += count
    else:
        raise ValueError(f"Invalid resource type: {resource_type}")
    
    db.commit()
    db.refresh(usage)
    
    # Return the updated usage and whether the limit was reached
    return usage, False

def get_user_remaining_resources(db: Session, user_id: int) -> dict:
    """
    Get the remaining resources for a user.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        Dictionary with remaining paths and cards
    """
    usage = initialize_user_daily_usage(db, user_id)
    
    return {
        "paths": {
            "used": usage.paths_generated,
            "limit": usage.paths_daily_limit,
            "remaining": usage.paths_daily_limit - usage.paths_generated
        },
        "cards": {
            "used": usage.cards_generated,
            "limit": usage.cards_daily_limit,
            "remaining": usage.cards_daily_limit - usage.cards_generated
        }
    } 