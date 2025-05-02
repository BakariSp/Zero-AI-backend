from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, validator

class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    profile_picture: Optional[str] = None
    interests: Optional[List[str]] = None
    subscription_type: Optional[str] = 'free'
    subscription_start_date: Optional[datetime] = None
    subscription_expiry_date: Optional[datetime] = None

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None
    is_active: bool = True
    subscription_type: Optional[str] = 'free'

class UserUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    profile_picture: Optional[str] = None
    interests: Optional[List[str]] = None
    subscription_type: Optional[str] = None
    subscription_start_date: Optional[datetime] = None
    subscription_expiry_date: Optional[datetime] = None

class UserInterests(BaseModel):
    interests: List[str]

class UserResponse(UserBase):
    id: int
    is_active: bool
    oauth_provider: Optional[str] = None
    created_at: Optional[str] = None
    is_superuser: Optional[bool] = False
    
    @validator('created_at', 'subscription_start_date', 'subscription_expiry_date', pre=True)
    def format_datetime(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v
    
    class Config:
        from_attributes = True

# Terms Acceptance Schemas
class TermsAcceptanceCreate(BaseModel):
    terms_version: str
    ip_address: Optional[str] = None

class TermsAcceptanceResponse(BaseModel):
    id: int
    user_id: int
    terms_version: str
    signed_at: datetime
    ip_address: Optional[str] = None
    
    @validator('signed_at', pre=True)
    def format_datetime(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v
    
    class Config:
        from_attributes = True 