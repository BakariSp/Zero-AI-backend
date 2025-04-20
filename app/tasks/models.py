import enum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Enum as DBEnum, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db import Base
from app.models import User # Assuming your User model is here
from app.models import LearningPath # Assuming your LearningPath model is here
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column

class TaskStatusEnum(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled" # Added if needed
    COMPLETED_WITH_ERRORS = "completed_with_errors" # Add this line

class TaskStageEnum(str, enum.Enum):
    INITIALIZING = "initializing"
    EXTRACTING_GOALS = "extracting_goals"
    PLANNING_STRUCTURE = "planning_structure"
    GENERATING_CARDS = "generating_cards"
    SAVING_STRUCTURE = "saving_structure"
    STRUCTURE_SAVED = "structure_saved"
    FINISHED = "finished"
    QUEUED = "queued" # Added if needed

class UserTask(Base):
    __tablename__ = "user_tasks"

    task_id = Column(String(255), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    learning_path_id = Column(Integer, ForeignKey("learning_paths.id"), nullable=True, index=True)

    status = Column(DBEnum(TaskStatusEnum), nullable=False, default=TaskStatusEnum.PENDING, index=True)
    stage = Column(DBEnum(TaskStageEnum), nullable=True) # Optional stage tracking

    progress = Column(Float, default=0.0) # Progress percentage
    message = Column(Text, nullable=True) # User-facing message
    error_details = Column(Text, nullable=True) # Detailed error/traceback

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now()) # Track updates

    started_at = Column(DateTime(timezone=True), nullable=True) # Assuming you might have this
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships (optional but recommended)
    user = relationship("User")
    learning_path = relationship("LearningPath")

    def __repr__(self):
        return f"<UserTask(task_id='{self.task_id}', status='{self.status}', user_id={self.user_id})>" 