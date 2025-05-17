from typing import Optional, List, Dict, Any
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
    
    @validator('username')
    def username_alphanumeric(cls, v):
        assert v.isalnum(), 'must be alphanumeric'
        return v

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    profile_picture: Optional[str] = None
    interests: Optional[List[str]] = None
    is_active: Optional[bool] = None
    subscription_type: Optional[str] = None
    subscription_start_date: Optional[datetime] = None
    subscription_expiry_date: Optional[datetime] = None

class UserInDB(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    oauth_provider: Optional[str] = None
    oauth_id: Optional[str] = None
    subscription_type: Optional[str] = None
    subscription_start_date: Optional[datetime] = None
    subscription_expiry_date: Optional[datetime] = None
    profile_picture: Optional[str] = None

    class Config:
        from_attributes = True

class User(UserInDB):
    pass

class UserInterests(BaseModel):
    interests: List[str]

class SubscriptionUpdate(BaseModel):
    subscription_type: str
    promotion_code: Optional[str] = None

class UserSubscriptionInfo(BaseModel):
    subscription_type: str
    subscription_start_date: Optional[datetime] = None
    subscription_expiry_date: Optional[datetime] = None
    daily_limits: Dict[str, int]
    remaining_today: Dict[str, int]

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

class GuestUserResponse(BaseModel):
    id: int
    is_guest: bool = True
    token: str
    created_at: datetime

    class Config:
        from_attributes = True

class MergeAccountRequest(BaseModel):
    guest_id: int

class MergeAccountResponse(BaseModel):
    status: str
    real_user_id: int
    guest_id: int
    message: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    profile_picture: Optional[str] = None
    oauth_provider: Optional[str] = None
    subscription_type: Optional[str] = None
    subscription_start_date: Optional[datetime] = None
    subscription_expiry_date: Optional[datetime] = None
    is_guest: Optional[bool] = False
    
    @validator('created_at', 'subscription_start_date', 'subscription_expiry_date', pre=True)
    def format_datetime(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v
    
    class Config:
        from_attributes = True 