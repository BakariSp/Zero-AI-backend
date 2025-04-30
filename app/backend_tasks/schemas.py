from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from .models import TaskStatusEnum, TaskStageEnum

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
    pass

class UserTaskUpdate(BaseModel):
    # Fields allowed for update
    status: Optional[TaskStatusEnum] = None
    stage: Optional[TaskStageEnum] = None
    progress: Optional[float] = None
    message: Optional[str] = None
    error_details: Optional[str] = None
    learning_path_id: Optional[int] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

class UserTaskResponse(UserTaskBase):
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True 