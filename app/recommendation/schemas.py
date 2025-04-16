from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

# Base models for database entities
# In app/recommendation/schemas.py
class CardBase(BaseModel):
    keyword: Optional[str] = None
    explanation: Optional[str] = None
    resources: Optional[List[Dict[str, str]]] = None
    level: Optional[str] = None
    tags: Optional[List[str]] = None
    created_by: Optional[str] = None
    
class CardResponse(BaseModel):
    id: int
    keyword: str
    explanation: Optional[str] = None
    example: Optional[str] = None
    resources: Optional[List[Dict[str, str]]] = None
    level: Optional[str] = None
    tags: Optional[List[str]] = None
    
    class Config:
        from_attributes = True

class SectionBase(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    
class SectionResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    order_index: int
    estimated_days: Optional[int]
    cards: List[CardResponse] = []
    
    class Config:
        from_attributes = True

class CourseBase(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    
class CourseResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    estimated_days: Optional[int]
    sections: List[SectionResponse] = []
    
    class Config:
        from_attributes = True

class LearningPathBase(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    difficulty_level: Optional[str] = None
    estimated_days: Optional[int] = None
    
class LearningPathResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    category: Optional[str]
    difficulty_level: Optional[str]
    estimated_days: Optional[int]
    courses: List[CourseResponse] = []
    sections: List[SectionResponse] = []  # For backwards compatibility
    
    class Config:
        from_attributes = True

# Response model for recommendations
class RecommendationResponse(BaseModel):
    learning_paths: List[LearningPathResponse] = []
    courses: List[CourseResponse] = []
    cards: List[CardResponse] = []

# New schemas for AI generation

class LearningPathRequest(BaseModel):
    """Request model for generating a learning path with AI"""
    interests: List[str] = Field(..., min_items=1, max_items=5)
    difficulty_level: str = Field(default="intermediate", description="Difficulty level: beginner, intermediate, advanced")
    estimated_days: int = Field(default=30, ge=1, le=90, description="Estimated days to complete the learning path")

class SectionWithKeywords(BaseModel):
    """Section with card keywords for the Learning Path Planner"""
    title: str
    description: Optional[str]
    order_index: int
    estimated_days: Optional[int]
    card_keywords: List[str]

class CourseWithSections(BaseModel):
    """Course with sections for the Learning Path Planner"""
    title: str
    description: Optional[str]
    order_index: int
    estimated_days: Optional[int]
    sections: List[SectionWithKeywords]

class LearningPathPlannerResponse(BaseModel):
    """Response model for the Learning Path Planner"""
    learning_path: Dict[str, Any]
    courses: List[Dict[str, Any]]
    message: Optional[str]

class CardGenerationStatus(BaseModel):
    """Status of card generation for a learning path"""
    learning_path_id: int
    total_sections: int
    sections_with_cards: int
    total_cards: int
    section_progress: float
    is_complete: bool 