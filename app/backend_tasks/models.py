import enum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Enum as DBEnum, Float
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from app.db import Base
from datetime import datetime
from typing import Optional

class TaskStatusEnum(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    COMPLETED_WITH_ERRORS = "completed_with_errors"

class TaskStageEnum(str, enum.Enum):
    INITIALIZING = "initializing"
    EXTRACTING_GOALS = "extracting_goals"
    PLANNING_STRUCTURE = "planning_structure"
    GENERATING_CARDS = "generating_cards"
    SAVING_STRUCTURE = "saving_structure"
    STRUCTURE_SAVED = "structure_saved"
    FINISHED = "finished"
    QUEUED = "queued"

class UserTask(Base):
    __tablename__ = "backend_tasks"
    __table_args__ = {'extend_existing': True}

    task_id = Column(String(255), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    learning_path_id = Column(Integer, ForeignKey("learning_paths.id"), nullable=True, index=True)

    status = Column(DBEnum(TaskStatusEnum), nullable=False, default=TaskStatusEnum.PENDING, index=True)
    stage = Column(DBEnum(TaskStageEnum), nullable=True)

    progress = Column(Float, default=0.0)
    message = Column(Text, nullable=True)
    error_details = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User")
    learning_path = relationship("LearningPath")

    def __repr__(self):
        return f"<UserTask(task_id='{self.task_id}', status='{self.status}', user_id={self.user_id})>" 