from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import timedelta, datetime
from pydantic import BaseModel, EmailStr, validator
from starlette.responses import RedirectResponse
import os
import base64
import json



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
    update_user
)
from app.models import User
from app.users.schemas import UserBase, UserUpdate, UserResponse, UserInterests

router = APIRouter()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models for request/response
class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    profile_picture: Optional[str] = None

class UserUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    profile_picture: Optional[str] = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    oauth_provider: Optional[str] = None
    created_at: Optional[str] = None
    
    @validator('created_at', pre=True)
    def format_datetime(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v
    
    class Config:
        from_attributes = True

# User profile routes
@router.get("/users/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@router.put("/users/me", response_model=UserResponse)
def update_user_me(
    user_update: UserUpdate,
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

@router.put("/users/me/interests", response_model=UserResponse)
def update_user_interests(
    interests: UserInterests,
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
@router.get("/users/{user_id}", response_model=UserResponse)
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

@router.get("/users", response_model=List[UserResponse])
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

@router.get("/me", response_model=UserResponse)
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