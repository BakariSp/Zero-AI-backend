from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, validator

class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    profile_picture: Optional[str] = None
    interests: Optional[List[str]] = None

class UserCreate(UserBase):
    password: Optional[str] = None

class UserUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    profile_picture: Optional[str] = None
    interests: Optional[List[str]] = None

class UserInterests(BaseModel):
    interests: List[str]

class UserResponse(UserBase):
    id: int
    is_active: bool
    oauth_provider: Optional[str] = None
    created_at: Optional[str] = None
    is_superuser: Optional[bool] = False
    
    @validator('created_at', pre=True)
    def format_datetime(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v
    
    class Config:
        from_attributes = True 