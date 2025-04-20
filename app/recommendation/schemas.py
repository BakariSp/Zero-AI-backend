from pydantic import BaseModel, Field, ConfigDict
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
    created_at: datetime
    updated_at: datetime
    
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
    created_at: datetime
    updated_at: datetime
    
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
    created_at: datetime
    updated_at: datetime
    
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

class ChatPromptRequest(BaseModel):
    """Request model for generating a learning path from a chat prompt"""
    prompt: str

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

class TaskCreationResponse(BaseModel):
    task_id: str
    message: str

class SectionStructureInput(BaseModel):
    # id: str # Optional: Frontend ID if needed for mapping later
    title: str

class CourseStructureInput(BaseModel):
    # id: str # Optional: Frontend ID if needed for mapping later
    title: str
    sections: List[SectionStructureInput]

class LearningPathStructureRequest(BaseModel):
    prompt: Optional[str] = None # Original user prompt, if available
    title: str = Field(..., description="The overall title for the learning path")
    courses: List[CourseStructureInput]
    difficulty_level: str = "intermediate"
    estimated_days: Optional[int] = None # Optional: Add if frontend provides it

# Add a schema for the enhanced task status (optional but good practice)
class SectionGenerationStatus(BaseModel):
    status: str = "pending" # pending, generating, completed, failed
    cards_generated: int = 0
    error: Optional[str] = None

class EnhancedTaskStatus(BaseModel):
    task_id: str
    status: str # pending, running, completed, failed, timeout
    stage: str # e.g., saving_structure, generating_cards, finished
    progress: int # Overall progress percentage (0-100)
    message: Optional[str] = None
    learning_path_id: Optional[int] = None
    total_sections: Optional[int] = None
    sections_completed: Optional[int] = None
    total_cards_expected: Optional[int] = None # Expected total cards (sections * 4)
    cards_completed: Optional[int] = 0
    section_status: Optional[Dict[int, SectionGenerationStatus]] = None # Section-level status
    errors: List[str] = []
    error_details: Optional[str] = None
    created_at: datetime
    updated_at: datetime