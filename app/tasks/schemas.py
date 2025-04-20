from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from .models import TaskStatusEnum, TaskStageEnum # Import the enums

class UserTaskBase(BaseModel):
    task_id: str
    user_id: int
    learning_path_id: Optional[int] = None
    status: TaskStatusEnum
    stage: Optional[TaskStageEnum] = None
    progress: float = 0.0
    message: Optional[str] = None
    error_details: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

class UserTaskCreate(UserTaskBase):
    # Fields required for creation
    pass # Often task_id, user_id, status are enough initially

class UserTaskUpdate(BaseModel):
    # Fields allowed for update
    status: Optional[TaskStatusEnum] = None
    stage: Optional[TaskStageEnum] = None
    progress: Optional[float] = None
    message: Optional[str] = None
    error_details: Optional[str] = None
    learning_path_id: Optional[int] = None # Allow updating LP ID if needed
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

class UserTaskResponse(UserTaskBase):
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True # Use this for Pydantic v2+
        # orm_mode = True # Use this for Pydantic v1 