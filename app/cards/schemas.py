from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class CardBase(BaseModel):
    keyword: str
    question: Optional[str] = None
    answer: Optional[str] = None
    explanation: Optional[str] = None
    resources: Optional[List[Dict[str, str]]] = None
    level: Optional[str] = "intermediate"
    tags: Optional[List[str]] = None
    created_by: Optional[str] = None
    difficulty: Optional[str] = "intermediate"

class CardCreate(CardBase):
    keyword: str
    question: str
    answer: str
    explanation: str
    difficulty: str

class CardUpdate(BaseModel):
    keyword: Optional[str] = None
    question: Optional[str] = None
    answer: Optional[str] = None
    explanation: Optional[str] = None
    resources: Optional[List[Dict[str, str]]] = None
    level: Optional[str] = None
    difficulty: Optional[str] = None
    tags: Optional[List[str]] = None

class Resource(BaseModel):
    url: HttpUrl # Use HttpUrl for validation
    title: str

class CardResponse(CardBase):
    id: int
    created_at: datetime
    updated_at: datetime
    resources: List[Resource] = Field(default_factory=list)
    keyword: str
    question: Optional[str] = None
    answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: Optional[str] = None
    level: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    
    class Config:
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
    section_title: Optional[str] = None
    course_title: Optional[str] = None
    difficulty: Optional[str] = None

class CardResponseSchema(BaseModel):
    id: int
    keyword: str
    question: str
    answer: str
    explanation: Optional[str] = None
    difficulty: Optional[str] = None
    resources: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True 