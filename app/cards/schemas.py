from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class CardBase(BaseModel):
    keyword: str
    explanation: str
    resources: Optional[List[Dict[str, str]]] = None
    level: Optional[str] = "basic"
    tags: Optional[List[str]] = None
    created_by: Optional[str] = None

class CardCreate(CardBase):
    pass

class CardUpdate(BaseModel):
    keyword: Optional[str] = None
    explanation: Optional[str] = None
    resources: Optional[List[Dict[str, str]]] = None
    level: Optional[str] = None
    tags: Optional[List[str]] = None

class CardResponse(CardBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True
        from_attributes = True

class UserCardBase(BaseModel):
    card_id: int

class UserCardCreate(UserCardBase):
    pass

class UserCardUpdate(BaseModel):
    is_completed: Optional[bool] = None
    expanded_example: Optional[str] = None
    notes: Optional[str] = None
    difficulty_rating: Optional[int] = None
    depth_preference: Optional[str] = None

class UserCardResponse(BaseModel):
    card_id: int
    user_id: int
    is_completed: bool
    expanded_example: Optional[str] = None
    notes: Optional[str] = None
    saved_at: datetime
    difficulty_rating: Optional[int] = None
    depth_preference: Optional[str] = None
    recommended_by: Optional[str] = None
    card: CardResponse
    
    class Config:
        from_attributes = True

class GenerateCardRequest(BaseModel):
    keyword: str
    context: Optional[str] = None
    section_id: Optional[int] = None 