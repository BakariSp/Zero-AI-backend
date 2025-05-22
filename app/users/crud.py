from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from typing import Dict, Any, List, Optional, Tuple
import logging
from datetime import date, datetime, timedelta
from sqlalchemy import text

from app.models import User, PromotionCodeUsage, UserTermsAcceptance
from app.users.schemas import UserCreate, UserUpdate, UserInterests
from app.utils.security import pwd_context
from app.user_daily_usage.crud import get_or_create_daily_usage

# Add constants for subscription limits
SUBSCRIPTION_LIMITS = {
    'free': {'paths': 3, 'cards': 20},
    'standard': {'paths': 10, 'cards': 100},
    'premium': {'paths': float('inf'), 'cards': float('inf')}  # Unlimited
}

# Promotion codes are now managed in the database via the PromotionCodeUsage model

def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return db.query(User).offset(skip).limit(limit).all()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()

def get_user_by_oauth(db: Session, provider: str, oauth_id: str):
    return db.query(User).filter(
        User.oauth_provider == provider,
        User.oauth_id == oauth_id
    ).first()

def create_user(db: Session, user: UserCreate, oauth_provider: str = None, oauth_id: str = None, profile_picture: str = None):
    """
    Create a new user in the database
    """
    # Hash the password if it's provided
    hashed_password = pwd_context.hash(user.password) if user.password else None
    
    # Create a new User object
    db_user = User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password,
        full_name=user.full_name,
        is_active=True,
        oauth_provider=oauth_provider,
        oauth_id=oauth_id,
        profile_picture=profile_picture
    )
    
    # Add the user to the database
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

def update_user(db: Session, user_id: int, user_data: Dict[str, Any]) -> User:
    logging.info(f"Updating user {user_id} with data: {user_data}")
    
    db_user = get_user(db, user_id)
    if not db_user:
        logging.error(f"User not found with ID: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Try two approaches to ensure updates are persisted
    
    # Method 1: Using ORM attribute setting
    try:
        for key, value in user_data.items():
            setattr(db_user, key, value)
        
        db.commit()
        logging.info(f"User {user_id} updated successfully via ORM")
    except Exception as e:
        logging.error(f"Error during ORM update for user {user_id}: {str(e)}")
        db.rollback()
        # Continue to try the direct SQL approach
    
    # Method 2: Direct SQL update for certain fields
    try:
        # For text fields like username
        if 'username' in user_data:
            username = user_data['username']
            sql = text("UPDATE users SET username = :username WHERE id = :id")
            db.execute(sql, {"username": username, "id": user_id})
            
        # For JSON fields like interests
        if 'interests' in user_data:
            interests = user_data['interests']
            
            # For PostgreSQL, we need to convert to JSON
            import json
            interests_json = json.dumps(interests)
            
            # Use PostgreSQL's specific JSON update syntax
            sql = text("UPDATE users SET interests = :interests::jsonb WHERE id = :id")
            db.execute(sql, {"interests": interests_json, "id": user_id})
        
        # Commit direct SQL changes
        db.commit()
        logging.info(f"User {user_id} updated successfully via direct SQL")
    except Exception as e:
        logging.error(f"Error during direct SQL update for user {user_id}: {str(e)}")
        db.rollback()
    
    # Refresh the user object to reflect all changes
    try:
        db.refresh(db_user)
    except Exception as e:
        logging.error(f"Error refreshing user object: {str(e)}")
        # Try to get a fresh copy of the user
        db_user = get_user(db, user_id)
    
    return db_user

def delete_user(db: Session, user_id: int) -> bool:
    db_user = get_user(db, user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    db.delete(db_user)
    db.commit()
    return True

def check_subscription_limits(db: Session, user_id: int, resource_type: str) -> Tuple[bool, int]:
    """
    Check if the user has reached their subscription limits for learning paths or cards.
    
    For premium users, this function will immediately return (False, -1) indicating no limit
    and unlimited remaining resources.
    
    For other users, this function checks daily usage limits.
    
    Args:
        db: Database session
        user_id: The user's ID
        resource_type: 'paths' or 'cards'
    
    Returns:
        Tuple of (has_reached_limit, remaining_count)
    """
    # Get the user and their subscription type
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get subscription type, default to 'free' if not set
    subscription = user.subscription_type or 'free'
    
    # Log the user's subscription for debugging
    logging.debug(f"Checking {resource_type} limits for user {user_id} with {subscription} subscription")
    
    # Premium users have unlimited resources
    if subscription == 'premium':
        logging.debug(f"User {user_id} has premium subscription, no limits applied")
        return False, -1  # -1 indicates unlimited resources
    
    # Get or create daily usage record for today
    today = date.today()
    daily_usage = get_or_create_daily_usage(db, user_id)
    
    if resource_type == 'paths':
        daily_count = daily_usage.paths_generated
        daily_max = daily_usage.paths_daily_limit
    else:  # resource_type == 'cards'
        daily_count = daily_usage.cards_generated
        daily_max = daily_usage.cards_daily_limit
    
    logging.debug(f"Daily count: {daily_count}, Daily max: {daily_max}")
    
    # Check if daily limit is reached
    daily_limit_reached = daily_count >= daily_max
    if daily_limit_reached:
        logging.debug(f"User has reached daily limit for {resource_type}: {daily_count}/{daily_max}")
    
    # Calculate remaining resources
    remaining = daily_max - daily_count
    logging.debug(f"Remaining {resource_type}: {remaining}")
    
    return daily_limit_reached, remaining

def get_promotion_code(db: Session, code: str) -> Optional[PromotionCodeUsage]:
    """Get promotion code details from database"""
    return db.query(PromotionCodeUsage).filter(PromotionCodeUsage.code == code).first()

def increment_promotion_code_usage(db: Session, code: str) -> PromotionCodeUsage:
    """Increment the usage count for a promotion code"""
    promo_code = get_promotion_code(db, code)
    if not promo_code:
        raise ValueError(f"Promotion code {code} not found")
    
    promo_code.times_used += 1
    db.commit()
    db.refresh(promo_code)
    return promo_code

def is_promotion_code_valid(db: Session, code: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check if a promotion code is valid and has not exceeded its usage limit.
    
    Returns:
        Tuple of (is_valid, error_message, tier)
    """
    promo_code = get_promotion_code(db, code)
    
    if not promo_code:
        return False, "Invalid promotion code", None
    
    if promo_code.times_used >= promo_code.total_limit:
        return False, "This promotion code has reached its maximum number of redemptions", None
    
    return True, None, promo_code.tier

def update_user_subscription(db: Session, user_id: int, subscription_type: str = None, promotion_code: Optional[str] = None, expiry_days: int = 30) -> User:
    """
    Update a user's subscription type.
    
    Args:
        db: Database session
        user_id: The user's ID
        subscription_type: One of 'free', 'standard', or 'premium'
        promotion_code: Optional promotion code
        expiry_days: Number of days until subscription expires (default 30 days)
    
    Returns:
        Updated user object
    """
    # Set up logging
    logging.info(f"Starting subscription update for user {user_id}, type={subscription_type}, promo={promotion_code}")
    
    # Get the user first to make sure they exist
    user = get_user(db, user_id)
    if not user:
        logging.error(f"User {user_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Store current subscription for comparison
    old_subscription = user.subscription_type or 'free'
    logging.info(f"Current user subscription: {old_subscription}")
    
    # Check if using only promotion code without subscription type
    if promotion_code:
        logging.info(f"Processing promotion code: {promotion_code}")
        is_valid, error_message, code_tier = is_promotion_code_valid(db, promotion_code)
        
        if not is_valid:
            logging.error(f"Invalid promotion code: {error_message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message
            )
        
        logging.info(f"Valid promotion code, tier: {code_tier}")
        
        # If no subscription_type provided, use the one from the code
        if not subscription_type:
            subscription_type = code_tier
            logging.info(f"Using promotion code tier: {subscription_type}")
        # If using both, take the higher tier
        elif _get_tier_level(code_tier) > _get_tier_level(subscription_type):
            logging.info(f"Promotion tier ({code_tier}) is higher than specified tier ({subscription_type}), using promotion tier")
            subscription_type = code_tier
        else:
            logging.info(f"Keeping specified tier ({subscription_type}) as it's higher than promotion tier ({code_tier})")
        
        # Increment usage count for the promotion code
        increment_promotion_code_usage(db, promotion_code)
        logging.info(f"Incremented usage count for promotion code: {promotion_code}")

    # Make sure we have a valid subscription type at this point
    if not subscription_type:
        logging.error("No subscription type provided and no valid promotion code")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either subscription_type or a valid promotion code"
        )
    
    # Make sure it's a valid subscription type
    if subscription_type not in SUBSCRIPTION_LIMITS:
        logging.error(f"Invalid subscription type: {subscription_type}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid subscription type: {subscription_type}. Valid types are: {', '.join(SUBSCRIPTION_LIMITS.keys())}"
        )
    
    # Check if this is an upgrade to a higher tier
    is_upgrade = _get_tier_level(subscription_type) > _get_tier_level(old_subscription)
    
    # Calculate expiry date
    now = datetime.utcnow()
    expiry_date = now + timedelta(days=expiry_days)
    
    # Update the user's subscription info
    user.subscription_type = subscription_type
    user.subscription_start_date = now
    user.subscription_expiry_date = expiry_date
    logging.info(f"Updated user subscription to: {subscription_type} (expires: {expiry_date})")
    
    # Update the user's daily usage limits based on the new subscription
    from app.user_daily_usage.crud import get_user_daily_usage, get_or_create_daily_usage
    
    # Define the new daily limits based on subscription type
    if subscription_type == 'premium':
        # Premium users get higher limits (999 as virtually unlimited)
        paths_limit = 999
        cards_limit = 999
        logging.info("Setting premium limits: paths=999, cards=999")
    else:
        # Otherwise, use the standard limits from SUBSCRIPTION_LIMITS
        paths_limit = SUBSCRIPTION_LIMITS[subscription_type]['paths']
        cards_limit = SUBSCRIPTION_LIMITS[subscription_type]['cards']
        logging.info(f"Setting {subscription_type} limits: paths={paths_limit}, cards={cards_limit}")
    
    # Check if daily usage record exists for today and update it
    today = date.today()
    daily_usage = get_user_daily_usage(db, user_id, today)
    
    if daily_usage:
        logging.info(f"Found existing daily usage record for {today}. Current limits: paths={daily_usage.paths_daily_limit}, cards={daily_usage.cards_daily_limit}")
        
        # Update existing record's limits
        daily_usage.paths_daily_limit = paths_limit
        daily_usage.cards_daily_limit = cards_limit
        
        # If this is an upgrade, we'll reset the usage counts to make sure the user can use their new limits immediately
        if is_upgrade:
            logging.info("This is an upgrade to a higher tier - resetting usage counts")
            
            # Reset counts but only if they're close to the limit
            if daily_usage.paths_generated > daily_usage.paths_daily_limit * 0.8:
                daily_usage.paths_generated = 0
                logging.info("Reset paths_generated to 0")
            
            if daily_usage.cards_generated > daily_usage.cards_daily_limit * 0.8:
                daily_usage.cards_generated = 0
                logging.info("Reset cards_generated to 0")
        
        logging.info(f"Updated existing daily usage limits to: paths={paths_limit}, cards={cards_limit}")
    else:
        logging.info(f"No daily usage record found for {today}, creating new one with updated limits")
        # Create new record with the correct limits
        daily_usage = get_or_create_daily_usage(
            db, 
            user_id, 
            paths_daily_limit=paths_limit,
            cards_daily_limit=cards_limit
        )
        logging.info(f"Created new daily usage record with limits: paths={daily_usage.paths_daily_limit}, cards={daily_usage.cards_daily_limit}")
    
    # Commit all changes
    try:
        db.commit()
        logging.info("Successfully committed all changes to database")
    except Exception as e:
        logging.error(f"Error committing changes: {str(e)}")
        db.rollback()
        raise
        
    db.refresh(user)
    db.refresh(daily_usage)
    
    # Final check to ensure limits were actually updated
    logging.info(f"VERIFICATION - User {user_id} subscription type is now: {user.subscription_type}")
    logging.info(f"VERIFICATION - Daily usage limits are now: paths={daily_usage.paths_daily_limit}, cards={daily_usage.cards_daily_limit}")
    logging.info(f"VERIFICATION - Current usage: paths={daily_usage.paths_generated}/{daily_usage.paths_daily_limit}, cards={daily_usage.cards_generated}/{daily_usage.cards_daily_limit}")
    
    return user

def _get_tier_level(tier: str) -> int:
    """Helper function to get the numerical level of a tier for comparison"""
    tier_levels = {
        'free': 1,
        'standard': 2,
        'premium': 3
    }
    return tier_levels.get(tier, 0)

def get_subscription_limits(subscription_type: str) -> Dict[str, int]:
    """
    Get the subscription limits for a given subscription type.
    
    Args:
        subscription_type: One of 'free', 'standard', or 'premium'
    
    Returns:
        Dictionary with limits for paths and cards
    """
    if subscription_type not in SUBSCRIPTION_LIMITS:
        subscription_type = 'free'  # Default to free if invalid
    
    limits = SUBSCRIPTION_LIMITS[subscription_type]
    
    # Convert infinite limits to a readable format for the frontend
    result = {}
    for key, value in limits.items():
        if value == float('inf'):
            result[key] = -1  # Use -1 to represent unlimited
        else:
            result[key] = value
    
    return result 

# Functions for user terms acceptance
def create_terms_acceptance(db: Session, user_id: int, terms_version: str, ip_address: str = None):
    """
    Create a new record of terms acceptance for a user
    """
    # First verify the user exists
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Create new terms acceptance record
    db_terms = UserTermsAcceptance(
        user_id=user_id,
        terms_version=terms_version,
        ip_address=ip_address
    )
    
    db.add(db_terms)
    db.commit()
    db.refresh(db_terms)
    return db_terms

def get_user_terms_acceptances(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    """
    Get all terms acceptances for a specific user
    """
    return db.query(UserTermsAcceptance).filter(
        UserTermsAcceptance.user_id == user_id
    ).order_by(
        UserTermsAcceptance.signed_at.desc()
    ).offset(skip).limit(limit).all()

def get_latest_terms_acceptance(db: Session, user_id: int, terms_version: str = None):
    """
    Get the latest terms acceptance for a user, optionally filtering by version
    """
    query = db.query(UserTermsAcceptance).filter(UserTermsAcceptance.user_id == user_id)
    
    if terms_version:
        query = query.filter(UserTermsAcceptance.terms_version == terms_version)
    
    return query.order_by(UserTermsAcceptance.signed_at.desc()).first()

def has_accepted_terms(db: Session, user_id: int, terms_version: str):
    """
    Check if a user has accepted a specific version of the terms
    """
    acceptance = get_latest_terms_acceptance(db, user_id, terms_version)
    return acceptance is not None

def auto_accept_terms_for_oauth_user(db: Session, user_id: int, terms_version: str = "v1.0", ip_address: str = "0.0.0.0") -> bool:
    """
    Automatically accept the current terms version for a user created via OAuth.
    This should be called when a user logs in or registers through an OAuth provider.
    
    Args:
        db: Database session
        user_id: The ID of the user
        terms_version: Version of the terms to accept (default: "v1.0")
        ip_address: IP address of the user (default: "0.0.0.0" for system-generated)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if the user has already accepted this version
        if has_accepted_terms(db, user_id, terms_version):
            # Already accepted, nothing to do
            return True
        
        # Create the terms acceptance record
        create_terms_acceptance(db, user_id, terms_version, ip_address)
        logging.info(f"Auto-accepted terms version {terms_version} for OAuth user ID {user_id}")
        return True
    except Exception as e:
        logging.error(f"Failed to auto-accept terms for user {user_id}: {str(e)}")
        return False 