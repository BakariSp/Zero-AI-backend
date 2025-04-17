from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.sections.schemas import SectionResponse

class CourseBase(BaseModel):
    title: str
    description: Optional[str] = None
    estimated_days: Optional[int] = None
    is_template: Optional[bool] = True

class CourseCreate(CourseBase):
    pass

class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    estimated_days: Optional[int] = None
    is_template: Optional[bool] = None

class CourseResponse(CourseBase):
    id: int
    created_at: datetime
    updated_at: datetime
    sections: List[SectionResponse] = []
    
    class Config:
        from_attributes = True

class UserCourseBase(BaseModel):
    course_id: int

class UserCourseCreate(UserCourseBase):
    pass

class UserCourseUpdate(BaseModel):
    progress: Optional[float] = None
    completed_at: Optional[datetime] = None

class UserCourseResponse(UserCourseBase):
    id: int
    user_id: int
    progress: float
    start_date: datetime
    completed_at: Optional[datetime] = None
    course: CourseResponse
    
    class Config:
        from_attributes = True