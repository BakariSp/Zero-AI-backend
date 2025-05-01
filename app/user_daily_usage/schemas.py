from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime

class UserDailyUsageBase(BaseModel):
    """Base schema for user daily usage data"""
    usage_date: date = Field(...)
    paths_generated: int = Field(0, ge=0)
    cards_generated: int = Field(0, ge=0)
    paths_daily_limit: int = Field(5, ge=0)
    cards_daily_limit: int = Field(20, ge=0)

class UserDailyUsageCreate(UserDailyUsageBase):
    """Schema for creating a new daily usage record"""
    user_id: int = Field(...)

class UserDailyUsageUpdate(BaseModel):
    """Schema for updating a daily usage record"""
    paths_generated: Optional[int] = Field(None, ge=0)
    cards_generated: Optional[int] = Field(None, ge=0)
    paths_daily_limit: Optional[int] = Field(None, ge=0)
    cards_daily_limit: Optional[int] = Field(None, ge=0)

class UserDailyUsageResponse(UserDailyUsageBase):
    """Schema for returning a daily usage record"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True 