import enum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Enum as DBEnum, Date, Time
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db import Base

class DailyTaskStatusEnum(str, enum.Enum):
    TODO = "TODO"
    DONE = "DONE"
    SKIPPED = "SKIPPED"

class DailyTask(Base):
    __tablename__ = "daily_tasks"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="Task", index=True)
    
    # Made foreign keys nullable for standalone tasks
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=True, index=True)
    section_id = Column(Integer, ForeignKey("course_sections.id"), nullable=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)
    learning_path_id = Column(Integer, ForeignKey("learning_paths.id"), nullable=True, index=True)
    
    scheduled_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    status = Column(DBEnum(DailyTaskStatusEnum, name="dailytaskstatusenum", native_enum=True, create_constraint=True), nullable=False, default=DailyTaskStatusEnum.TODO, index=True)
    note = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="daily_tasks")
    card = relationship("Card", back_populates="daily_tasks", foreign_keys=[card_id])
    section = relationship("CourseSection", back_populates="daily_tasks", foreign_keys=[section_id])
    course = relationship("Course", back_populates="daily_tasks", foreign_keys=[course_id])
    learning_path = relationship("LearningPath", back_populates="daily_tasks", foreign_keys=[learning_path_id])

    def __repr__(self):
        return f"<DailyTask(id={self.id}, user_id={self.user_id}, title='{self.title}', scheduled_date='{self.scheduled_date}')>" 