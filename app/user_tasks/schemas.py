from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date, time
from .models import DailyTaskStatusEnum

class DailyTaskBase(BaseModel):
    user_id: int = Field(..., description="ID of the user this task belongs to")
    title: str = Field("Task", description="Title of the task")
    scheduled_date: date = Field(..., description="Date when this task is scheduled")
    start_time: Optional[time] = Field(None, description="Optional start time for the task")
    end_time: Optional[time] = Field(None, description="Optional end time for the task")
    status: DailyTaskStatusEnum = Field(DailyTaskStatusEnum.TODO, description="Task status (TODO, DONE, SKIPPED)")
    note: Optional[str] = Field(None, description="Optional user note for this task")
    # Foreign key fields made optional for standalone tasks
    card_id: Optional[int] = Field(None, description="ID of the card this task is associated with. Optional for standalone tasks.")
    section_id: Optional[int] = Field(None, description="ID of the section this task belongs to. Optional for standalone tasks.")
    course_id: Optional[int] = Field(None, description="ID of the course this task belongs to. Optional for standalone tasks.")
    learning_path_id: Optional[int] = Field(None, description="ID of the learning path this task belongs to. Optional for standalone tasks.")

class DailyTaskCreate(DailyTaskBase):
    """
    Schema for creating a new daily task.
    For learning-related tasks, all foreign key fields must reference existing records.
    For standalone tasks, the foreign key fields (card_id, section_id, etc.) can be omitted.
    """
    pass

class DailyTaskUpdate(BaseModel):
    """
    Schema for updating an existing task. Only include the fields you want to update.
    """
    title: Optional[str] = Field(None, description="New task title")
    scheduled_date: Optional[date] = Field(None, description="New scheduled date")
    start_time: Optional[time] = Field(None, description="New start time")
    end_time: Optional[time] = Field(None, description="New end time")
    status: Optional[DailyTaskStatusEnum] = Field(None, description="New task status")
    note: Optional[str] = Field(None, description="New user note")
    card_id: Optional[int] = Field(None, description="New card association")
    section_id: Optional[int] = Field(None, description="New section association")
    course_id: Optional[int] = Field(None, description="New course association")
    learning_path_id: Optional[int] = Field(None, description="New learning path association")

class DailyTaskResponse(BaseModel):
    """
    Schema for task responses, including system fields.
    """
    id: int
    user_id: int
    title: str
    scheduled_date: date
    start_time: Optional[time]
    end_time: Optional[time]
    status: DailyTaskStatusEnum
    note: Optional[str]
    card_id: Optional[int]
    section_id: Optional[int]
    course_id: Optional[int]
    learning_path_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class RescheduleSection(BaseModel):
    """
    Schema for rescheduling all tasks in a section to a new date range.
    """
    new_start_date: date = Field(..., description="New starting date for the section's tasks")
    new_end_date: date = Field(..., description="New ending date for the section's tasks")

class ShiftTasksRequest(BaseModel):
    """
    Schema for shifting all tasks after a certain date by a number of days.
    """
    user_id: int = Field(..., description="ID of the user whose tasks should be shifted")
    from_date: date = Field(..., description="Date from which tasks should be shifted")
    days: int = Field(..., description="Number of days to shift tasks by (positive or negative)")

class CurrentUserDailyTaskCreate(BaseModel):
    """
    Schema for creating a task for the current user without requiring user_id.
    """
    title: str = Field("Task", description="Title of the task")
    scheduled_date: date = Field(..., description="Date when this task is scheduled")
    start_time: Optional[time] = Field(None, description="Optional start time for the task")
    end_time: Optional[time] = Field(None, description="Optional end time for the task")
    status: DailyTaskStatusEnum = Field(DailyTaskStatusEnum.TODO, description="Task status (TODO, DONE, SKIPPED)")
    note: Optional[str] = Field(None, description="Optional user note for this task")
    # Foreign key fields made optional for standalone tasks
    card_id: Optional[int] = Field(None, description="ID of the card this task is associated with. Optional for standalone tasks.")
    section_id: Optional[int] = Field(None, description="ID of the section this task belongs to. Optional for standalone tasks.")
    course_id: Optional[int] = Field(None, description="ID of the course this task belongs to. Optional for standalone tasks.")
    learning_path_id: Optional[int] = Field(None, description="ID of the learning path this task belongs to. Optional for standalone tasks.") 