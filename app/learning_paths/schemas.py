from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.courses.schemas import CourseResponse, UserCourseResponse
from app.sections.schemas import SectionResponse

class CourseSectionBase(BaseModel):
    title: str
    description: Optional[str] = None
    order_index: int
    estimated_days: Optional[int] = None

class CourseSectionCreate(CourseSectionBase):
    pass

class CourseSectionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    order_index: Optional[int] = None
    estimated_days: Optional[int] = None

# New model for card progress status
class CardProgressStatus(BaseModel):
    id: int
    is_completed: bool
    title: Optional[str] = None

    class Config:
        from_attributes = True

# For user-specific section with progress info
class UserSectionInfo(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    progress: float = 0.0
    cards: List[CardProgressStatus] = []
    user_section_id: Optional[int] = None
    section_template_id: Optional[int] = None
    
    class Config:
        from_attributes = True

# For user-specific course with progress info
class UserCourseInfo(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    progress: float = 0.0
    completed_at: Optional[datetime] = None
    sections: List[UserSectionInfo] = []
    
    class Config:
        from_attributes = True

class LearningPathBase(BaseModel):
    title: str
    description: Optional[str] = None
    category: str
    difficulty_level: Optional[str] = None
    estimated_days: Optional[int] = None
    is_template: Optional[bool] = True

class LearningPathCreate(LearningPathBase):
    sections: Optional[List[CourseSectionCreate]] = None

class LearningPathUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    difficulty_level: Optional[str] = None
    estimated_days: Optional[int] = None

class CourseSectionResponse(CourseSectionBase):
    id: int
    learning_path_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Add a minimal Course response schema if one doesn't exist in imported schemas
class CourseBaseResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    estimated_days: Optional[int] = None
    
    class Config:
        from_attributes = True

class LearningPathResponse(LearningPathBase):
    id: int
    sections: List[CourseSectionResponse] = []
    created_at: datetime
    updated_at: datetime
    courses: List[UserCourseInfo] = []

    class Config:
        from_attributes = True

class UserLearningPathBase(BaseModel):
    learning_path_id: int

class UserLearningPathCreate(UserLearningPathBase):
    pass

class UserLearningPathUpdate(BaseModel):
    progress: Optional[float] = None
    completed_at: Optional[datetime] = None

class UserLearningPathResponse(UserLearningPathBase):
    id: int
    user_id: int
    progress: float
    start_date: datetime
    completed_at: Optional[datetime] = None
    learning_path: LearningPathResponse

    class Config:
        from_attributes = True

class GenerateLearningPathRequest(BaseModel):
    interests: List[str]
    difficulty_level: Optional[str] = "intermediate"
    estimated_days: Optional[int] = 30
    existing_items: List[str] = []
    class Config:
        from_attributes = True 

class GenerateDetailsFromOutlineRequest(BaseModel):
    titles: List[str]
    difficulty_level: str = "intermediate"
    estimated_days: int = 30

class GenerateCourseTitleRequest(BaseModel):
    interests: List[str]
    difficulty_level: str = "beginner"
    estimated_days: int = 30
    existing_items: List[str] = []

class LearningPathBasicInfo(BaseModel):
    id: int
    title: Optional[str]
    description: Optional[str]

    class Config:
        from_attributes = True