from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import timedelta, datetime, date
from pydantic import BaseModel, EmailStr, validator
from starlette.responses import RedirectResponse
import os
import base64
import json
import logging

from app.db import SessionLocal
from app.auth.jwt import (
    create_access_token, 
    get_current_active_user,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    Token
)
from app.auth.oauth import oauth, get_oauth_user
from app.users.crud import (
    get_user, 
    get_users, 
    get_user_by_email,
    get_user_by_username,
    update_user,
    get_subscription_limits,
    check_subscription_limits,
    update_user_subscription as update_user_subscription_crud
)
from app.models import User
from app.users import schemas
from app.user_daily_usage.crud import get_or_create_daily_usage
from app.users import crud
from app.users.schemas import UserCreate, UserResponse, UserUpdate, UserInterests, TermsAcceptanceCreate, TermsAcceptanceResponse

router = APIRouter()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# User profile routes
@router.get("/users/me", response_model=schemas.UserResponse)
def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@router.put("/users/me", response_model=schemas.UserResponse)
def update_user_me(
    user_update: schemas.UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Check if username is being updated and is already taken
    if user_update.username and user_update.username != current_user.username:
        username_exists = get_user_by_username(db, username=user_update.username)
        if username_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    updated_user = update_user(
        db=db,
        user_id=current_user.id,
        user_data=user_update.dict(exclude_unset=True)
    )
    return updated_user

@router.put("/users/me/interests", response_model=schemas.UserResponse)
def update_user_interests(
    interests: schemas.UserInterests,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update user's interests and generate personalized learning paths"""
    updated_user = update_user(
        db=db,
        user_id=current_user.id,
        user_data={"interests": interests.interests}
    )
    
    # Here we would trigger the generation of learning paths based on interests
    # This will be implemented in the learning paths service
    
    return updated_user

# Admin routes
@router.get("/users/{user_id}", response_model=schemas.UserResponse)
def read_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Only allow superusers to view other users
    if user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    db_user = get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return db_user

@router.get("/users", response_model=List[schemas.UserResponse])
def read_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Only allow superusers to list all users
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    users = get_users(db, skip=skip, limit=limit)
    return users

@router.get("/test")
def test_route():
    return {"message": "Test route is working"}

@router.get("/me", response_model=schemas.UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get information about the currently authenticated user"""
    user_data = {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "profile_picture": current_user.profile_picture,
        "is_active": current_user.is_active,
        "oauth_provider": current_user.oauth_provider,
        "is_superuser": current_user.is_superuser,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None
    }
    return user_data 

# Add this route to handle card deletion from learning paths
@router.delete("/me/learning-paths/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card_from_learning_path(
    card_id: int,
    section_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Remove a card from a section in the user's learning path.
    This is a proxy to the cards router endpoint.
    """
    from app.cards.crud import remove_card_from_user_learning_path
    
    try:
        # Check if current_user is None
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
            
        remove_card_from_user_learning_path(db, user_id=current_user.id, card_id=card_id, section_id=section_id)
        return {"detail": "Card removed from learning path successfully"}
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        # Log any unexpected errors
        logging.error(f"Error removing card {card_id} from learning path: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove card: {str(e)}"
        ) 

@router.get("/subscription", response_model=dict)
async def get_user_subscription_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the current user's subscription information, including plan type, dates, and daily usage.
    """
    # Get current subscription info
    subscription_type = current_user.subscription_type or 'free'
    
    # Format subscription dates
    subscription_start = None
    subscription_expiry = None
    is_active = True
    
    if current_user.subscription_start_date:
        subscription_start = current_user.subscription_start_date.isoformat()
    
    if current_user.subscription_expiry_date:
        subscription_expiry = current_user.subscription_expiry_date.isoformat()
        # Check if subscription has expired
        from datetime import datetime
        is_active = current_user.subscription_expiry_date > datetime.utcnow()
    
    # Get daily usage information
    daily_usage = get_or_create_daily_usage(db, current_user.id)
    
    return {
        "plan": {
            "type": subscription_type,
            "start_date": subscription_start,
            "expiry_date": subscription_expiry,
            "is_active": is_active
        },
        "daily_limits": {
            "paths": daily_usage.paths_daily_limit,
            "cards": daily_usage.cards_daily_limit
        },
        "daily_usage": {
            "date": daily_usage.usage_date.isoformat(),
            "paths": {
                "count": daily_usage.paths_generated,
                "remaining": daily_usage.paths_daily_limit - daily_usage.paths_generated,
                "limit_reached": daily_usage.paths_generated >= daily_usage.paths_daily_limit
            },
            "cards": {
                "count": daily_usage.cards_generated,
                "remaining": daily_usage.cards_daily_limit - daily_usage.cards_generated,
                "limit_reached": daily_usage.cards_generated >= daily_usage.cards_daily_limit
            }
        }
    }

@router.put("/subscription", response_model=schemas.UserResponse)
async def update_user_subscription(
    subscription_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update the current user's subscription type.
    Only superusers can upgrade other users' subscriptions.
    
    Request body can include:
    - user_id: Optional, only for superusers to update other users
    - subscription_type: Optional, one of 'free', 'standard', 'premium'
    - promotion_code: Optional, a valid promotion code to apply (will automatically determine tier)
    - expiry_days: Optional, number of days until subscription expires (default 30)
    
    Either subscription_type or promotion_code must be provided. If both are provided,
    the system will choose the higher tier between the two.
    """
    import logging
    
    user_id = subscription_data.get("user_id", current_user.id)
    subscription_type = subscription_data.get("subscription_type")
    promotion_code = subscription_data.get("promotion_code")
    expiry_days = subscription_data.get("expiry_days", 30)
    
    # Validate input
    if not subscription_type and not promotion_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either subscription_type or promotion_code"
        )
    
    # Only allow superusers to update other users' subscriptions
    if user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update another user's subscription"
        )
    
    # Make DB changes in a transaction to ensure consistency
    try:
        # Start transaction explicitly (although SQLAlchemy session already does this implicitly)
        logging.info(f"Starting subscription update transaction: type={subscription_type}, promo={promotion_code}")
        
        # Update subscription
        updated_user = update_user_subscription_crud(
            db, 
            user_id, 
            subscription_type, 
            promotion_code,
            expiry_days
        )
        
        # Ensure daily usage limits are properly updated
        from app.user_daily_usage.crud import get_user_daily_usage
        
        # Define limits based on the updated subscription type
        sub_type = updated_user.subscription_type or 'free'
        from app.users.crud import SUBSCRIPTION_LIMITS
        
        if sub_type == 'premium':
            paths_limit = 999
            cards_limit = 999
        else:
            paths_limit = SUBSCRIPTION_LIMITS[sub_type]['paths']
            cards_limit = SUBSCRIPTION_LIMITS[sub_type]['cards']
        
        # Double check that the daily usage limits were updated
        today = date.today()
        daily_usage = get_user_daily_usage(db, user_id, today)
        
        if daily_usage:
            # Verify limits were set correctly
            if daily_usage.paths_daily_limit != paths_limit or daily_usage.cards_daily_limit != cards_limit:
                logging.warning(f"Daily limits incorrectly set: expected paths={paths_limit}, cards={cards_limit} but got paths={daily_usage.paths_daily_limit}, cards={daily_usage.cards_daily_limit}")
                # Force update the limits
                daily_usage.paths_daily_limit = paths_limit
                daily_usage.cards_daily_limit = cards_limit
                db.commit()
                logging.info(f"Forced update of daily limits to: paths={paths_limit}, cards={cards_limit}")
        
        logging.info(f"Completed subscription update successfully for user {user_id}")
        return updated_user
        
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        # Log any unexpected errors
        logging.error(f"Error updating subscription: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update subscription: {str(e)}"
        ) 

# Terms Acceptance Routes
@router.post("/terms/accept", response_model=TermsAcceptanceResponse, status_code=status.HTTP_201_CREATED)
def accept_terms(
    terms: TermsAcceptanceCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Record a user's acceptance of terms and conditions.
    This endpoint records when a user accepts the terms, which version they accepted,
    and optionally their IP address for audit purposes.
    """
    # If IP address is not provided in the request, get it from the request
    if not terms.ip_address:
        # Get client IP from request
        terms.ip_address = request.client.host
    
    return crud.create_terms_acceptance(
        db=db,
        user_id=current_user.id,
        terms_version=terms.terms_version,
        ip_address=terms.ip_address
    )

@router.get("/terms/history", response_model=List[TermsAcceptanceResponse])
def get_terms_acceptance_history(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the history of all terms acceptances for the current user
    """
    return crud.get_user_terms_acceptances(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )

@router.get("/terms/status/{terms_version}", response_model=dict)
def check_terms_status(
    terms_version: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Check if the user has accepted a specific version of the terms
    """
    has_accepted = crud.has_accepted_terms(
        db=db,
        user_id=current_user.id,
        terms_version=terms_version
    )
    
    return {
        "user_id": current_user.id,
        "terms_version": terms_version,
        "has_accepted": has_accepted
    } 