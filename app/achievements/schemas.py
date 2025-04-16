from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class AchievementBase(BaseModel):
    title: str
    description: str
    badge_image: Optional[str] = None
    achievement_type: str
    criteria: Dict[str, Any]

class AchievementCreate(AchievementBase):
    pass

class AchievementUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    badge_image: Optional[str] = None
    achievement_type: Optional[str] = None
    criteria: Optional[Dict[str, Any]] = None

class AchievementResponse(AchievementBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class UserAchievementResponse(BaseModel):
    achievement: AchievementResponse
    achieved_at: datetime
    
    class Config:
        from_attributes = True 