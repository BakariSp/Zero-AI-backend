from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import logging
from sqlalchemy import text

from app.db import get_db
from app.models import User, UserLearningPath, LearningPath, Course, UserCourse
from app.auth.jwt import create_access_token, get_current_user
from app.users.schemas import GuestUserResponse, MergeAccountRequest, MergeAccountResponse
from app.users.crud import get_user
from pydantic import BaseModel
from typing import Optional
router = APIRouter()

# Set up logging
log = logging.getLogger(__name__)

def create_guest_user(db: Session) -> User:
    """
    Create a new guest user in the database
    """
    # Generate a unique username with timestamp (since guest users don't have emails)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    username = f"guest_{timestamp}"
    
    # Create a new guest User object
    db_user = User(
        email=f"{username}@guest.temporary",  # Temporary email that won't be used
        username=username,
        hashed_password=None,  # No password for guest users
        is_active=True,
        is_guest=True,
        last_active_at=datetime.utcnow(),
        created_at=datetime.utcnow()
    )
    
    # Add the user to the database
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    log.info(f"Created new guest user: {username} with ID {db_user.id}")
    
    return db_user

def merge_guest_user(db: Session, guest_id: int, real_user_id: int) -> bool:
    """
    Merge a guest user account into a regular user account
    """
    # Validate both users exist
    guest_user = db.query(User).filter_by(id=guest_id, is_guest=True).first()
    real_user = db.query(User).filter_by(id=real_user_id, is_guest=False).first()

    if not guest_user or not real_user:
        log.error(f"Merge failed: Guest user {guest_id} or real user {real_user_id} not found")
        return False

    # Migrate learning paths
    db.query(UserLearningPath).filter_by(user_id=guest_user.id).update({"user_id": real_user_id})
    
    # Migrate user courses
    db.query(UserCourse).filter_by(user_id=guest_user.id).update({"user_id": real_user_id})
    
    # Migrate other user-related data that might exist
    try:
        # Try to migrate user cards
        db.execute(
            text("UPDATE user_cards SET user_id = :real_user_id WHERE user_id = :guest_user_id"),
            {"real_user_id": real_user_id, "guest_user_id": guest_user.id}
        )
    except Exception as e:
        log.warning(f"Error migrating user cards: {str(e)}")
    
    try:
        # Try to migrate user sections
        db.execute(
            text("UPDATE user_sections SET user_id = :real_user_id WHERE user_id = :guest_user_id"),
            {"real_user_id": real_user_id, "guest_user_id": guest_user.id}
        )
    except Exception as e:
        log.warning(f"Error migrating user sections: {str(e)}")
    
    try:
        # Try to migrate daily logs
        db.execute(
            text("UPDATE daily_logs SET user_id = :real_user_id WHERE user_id = :guest_user_id"),
            {"real_user_id": real_user_id, "guest_user_id": guest_user.id}
        )
    except Exception as e:
        log.warning(f"Error migrating daily logs: {str(e)}")
    
    # Mark guest as merged
    guest_user.merged_into_user_id = real_user_id
    guest_user.is_active = False  # Deactivate the guest account
    
    db.commit()
    log.info(f"Successfully merged guest user {guest_id} into real user {real_user_id}")
    
    return True

def update_guest_activity(db: Session, user_id: int) -> bool:
    """
    Update the last_active_at timestamp for a guest user
    """
    guest_user = db.query(User).filter_by(id=user_id, is_guest=True).first()
    if guest_user:
        guest_user.last_active_at = datetime.utcnow()
        db.commit()
        return True
    return False


@router.post("/merge", response_model=MergeAccountResponse)
def merge_accounts(
    merge_data: MergeAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Merge a guest account into the current user's account"""
    if current_user.is_guest:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A guest account cannot merge another account"
        )
    
    # Get the guest user
    guest_user = get_user(db, merge_data.guest_id)
    if not guest_user or not guest_user.is_guest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest user not found"
        )
    
    # Check if guest account is already merged
    if guest_user.merged_into_user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Guest account has already been merged"
        )
    
    # Perform the merge
    success = merge_guest_user(db, guest_user.id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to merge accounts"
        )
    
    return MergeAccountResponse(
        status="merged",
        real_user_id=current_user.id,
        guest_id=guest_user.id,
        message="Successfully merged guest account data into your account"
    )
    
@router.put("/guest/activity")
def update_guest_activity_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update the last_active_at timestamp for the current guest user"""
    if not current_user.is_guest:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only guest users can update activity timestamp"
        )
    
    success = update_guest_activity(db, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest user not found"
        )
    
    return {"status": "updated", "message": "Guest user activity timestamp updated"} 


class GuestCreateRequest(BaseModel):
    username: str
    email: str

@router.post("/guest", response_model=GuestUserResponse)
def create_guest_user_endpoint(
    payload: GuestCreateRequest,
    db: Session = Depends(get_db)
):
    # 使用 username 和 email 作为 guest 用户唯一标识
    username = payload.username
    email = payload.email

    # 先查是否已存在（幂等）
    user = db.query(User).filter(User.email == email).first()
    if user:
        token = create_access_token(data={"sub": user.email, "is_guest": True})
        return GuestUserResponse(
            id=user.id,
            is_guest=True,
            token=token,
            created_at=user.created_at
        )

    # 新建 guest user
    new_user = User(
        email=email,
        username=username,
        is_guest=True,
        is_active=True,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow()
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log.info(f"✅ Created new guest user: {new_user.email} (id={new_user.id})")

    token = create_access_token(data={"sub": new_user.email, "is_guest": True})
    return GuestUserResponse(
        id=new_user.id,
        is_guest=True,
        token=token,
        created_at=new_user.created_at
    )