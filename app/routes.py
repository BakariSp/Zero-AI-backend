from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date

from app.db import get_db
from app.auth.jwt import get_current_active_user
from app.models import User
from app.setup import get_user_remaining_resources, initialize_user_daily_usage

router = APIRouter()

@router.get("/users/me/daily-usage", response_model=dict)
def get_my_daily_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the current user's daily usage limits and remaining resources
    """
    try:
        # Initialize or get the user's daily usage
        initialize_user_daily_usage(db, current_user.id)
        
        # Get remaining resources
        resources = get_user_remaining_resources(db, current_user.id)
        
        # Add subscription info
        resources["subscription_tier"] = current_user.subscription_tier
        resources["usage_date"] = date.today().isoformat()
        
        return resources
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error retrieving daily usage: {str(e)}"
        ) 