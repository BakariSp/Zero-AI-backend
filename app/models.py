from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Table, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy.sql import func
from app.db import Base
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy import event

# Define your models here
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # OAuth related fields
    oauth_provider = Column(String(50), nullable=True)  # 'google', 'github', etc.
    oauth_id = Column(String(255), nullable=True)       # ID from the provider
    
    # Additional user info
    full_name = Column(String(100), nullable=True)
    profile_picture = Column(String(255), nullable=True)
    
    # Add relationships if needed
    # items = relationship("Item", back_populates="owner") 
    
    # New fields for interests and learning paths
    interests = Column(JSON, nullable=True)  # Store interests as JSON array
    
    # Relationships
    learning_paths = relationship("UserLearningPath", back_populates="user")
    saved_cards = relationship("Card", secondary="user_cards", back_populates="saved_by_users")
    achievements = relationship("Achievement", secondary="user_achievements", back_populates="achieved_by_users")
    daily_logs = relationship("DailyLog", back_populates="user")
    courses = relationship("UserCourse", back_populates="user")
    custom_sections = relationship("UserSection", back_populates="user")

# --- Define Association Tables FIRST ---

# User-Card association table
user_cards = Table(
    'user_cards',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('card_id', Integer, ForeignKey('cards.id'), primary_key=True),
    Column('is_completed', Boolean, default=False),
    Column('expanded_example', Text, nullable=True),
    Column('notes', Text, nullable=True),
    Column('saved_at', DateTime, default=func.now()),
    Column('difficulty_rating', Integer, nullable=True),  # 1~5
    Column('depth_preference', String(20), nullable=True),  # "basic" or "advanced"
    Column('recommended_by', String(100), nullable=True)  # AI Planner / System
)

# User-Achievement association table
user_achievements = Table(
    'user_achievements',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('achievement_id', Integer, ForeignKey('achievements.id'), primary_key=True),
    Column('achieved_at', DateTime, default=func.now())
)

# Association table for courses and sections
course_section_association = Table(
    'course_section_association',
    Base.metadata,
    Column('course_id', Integer, ForeignKey('courses.id'), primary_key=True),
    Column('section_id', Integer, ForeignKey('course_sections.id'), primary_key=True),
    Column('order_index', Integer, nullable=False)
)

# Association table for learning paths and courses
learning_path_courses = Table(
    'learning_path_courses',
    Base.metadata,
    Column('learning_path_id', Integer, ForeignKey('learning_paths.id'), primary_key=True),
    Column('course_id', Integer, ForeignKey('courses.id'), primary_key=True),
    Column('order_index', Integer, nullable=False)
)

# Section-Card association table
section_cards = Table(
    'section_cards',
    Base.metadata,
    Column('section_id', Integer, ForeignKey('course_sections.id'), primary_key=True),
    Column('card_id', Integer, ForeignKey('cards.id'), primary_key=True),
    Column('order_index', Integer, nullable=False)
)

# User-Section-Card association table
user_section_cards = Table(
    'user_section_cards',
    Base.metadata,
    Column('user_section_id', Integer, ForeignKey('user_sections.id'), primary_key=True),
    Column('card_id', Integer, ForeignKey('cards.id'), primary_key=True),
    Column('order_index', Integer, nullable=False),
    Column('is_custom', Boolean, default=False)  # 用户自己加的
)

# --- Define Main Models AFTER Association Tables ---

class LearningPath(Base):
    __tablename__ = "learning_paths"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), index=True)
    difficulty_level = Column(String(50), nullable=True)
    estimated_days = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    is_template = Column(Boolean, default=True)

    # Relationships
    sections = relationship("CourseSection", back_populates="learning_path", cascade="all, delete-orphan")
    user_paths = relationship("UserLearningPath", back_populates="learning_path", cascade="all, delete-orphan")
    courses = relationship("Course", secondary="learning_path_courses", back_populates="learning_paths")

class CourseSection(Base):
    __tablename__ = "course_sections"

    id = Column(Integer, primary_key=True, index=True)
    learning_path_id = Column(Integer, ForeignKey("learning_paths.id"))
    title = Column(String(255))
    description = Column(Text, nullable=True)
    order_index = Column(Integer)
    estimated_days = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    is_template = Column(Boolean, default=True)

    # Relationships
    learning_path = relationship("LearningPath", back_populates="sections")
    cards = relationship("Card", secondary="section_cards", back_populates="sections", order_by=section_cards.c.order_index)
    courses = relationship("Course", secondary="course_section_association", back_populates="sections")

class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(255), index=True, nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    explanation = Column(Text, nullable=True)
    difficulty = Column(String(50), nullable=True)
    resources = Column(MutableList.as_mutable(JSON), default=lambda: [])  # Use lambda to ensure a new list each time
    level = Column(String(20), nullable=True)
    tags = Column(JSON, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    sections = relationship("CourseSection", secondary="section_cards", back_populates="cards")
    saved_by_users = relationship("User", secondary="user_cards", back_populates="saved_cards")
    user_sections = relationship("UserSection", secondary="user_section_cards", back_populates="cards")
    
    # Add a property to handle None values for resources
    @property
    def safe_resources(self):
        return self.resources if self.resources is not None else []

@event.listens_for(Card, 'load')
def receive_load(target, context):
    if target.resources is None:
        target.resources = []

class UserLearningPath(Base):
    __tablename__ = "user_learning_paths"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    learning_path_id = Column(Integer, ForeignKey("learning_paths.id"))
    progress = Column(Float, default=0.0)  # 0.0 to 100.0
    start_date = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="learning_paths")
    learning_path = relationship("LearningPath", back_populates="user_paths")

class DailyLog(Base):
    __tablename__ = "daily_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    log_date = Column(DateTime, default=func.now())
    completed_sections = Column(JSON, nullable=True)  # Store section IDs as JSON array
    notes = Column(Text, nullable=True)
    study_time_minutes = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="daily_logs")

class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    description = Column(Text)
    badge_image = Column(String(255), nullable=True)
    achievement_type = Column(String(50))  # e.g., "streak", "completion", "milestone"
    criteria = Column(JSON)  # Store criteria as JSON
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    achieved_by_users = relationship("User", secondary="user_achievements", back_populates="achievements") 

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True)
    description = Column(Text, nullable=True)
    estimated_days = Column(Integer, nullable=True)
    is_template = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    sections = relationship("CourseSection", secondary="course_section_association", back_populates="courses")
    learning_paths = relationship("LearningPath", secondary="learning_path_courses", back_populates="courses")
    user_courses = relationship("UserCourse", back_populates="course")

# User course progress tracking
class UserCourse(Base):
    __tablename__ = "user_courses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    progress = Column(Float, default=0.0)  # 0.0 to 100.0
    start_date = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="courses")
    course = relationship("Course", back_populates="user_courses")

# 在现有模型之后添加

class UserSection(Base):
    __tablename__ = "user_sections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    section_template_id = Column(Integer, ForeignKey("course_sections.id"), nullable=True)  # 来源模板
    title = Column(String(255))
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="custom_sections")
    section_template = relationship("CourseSection")
    cards = relationship("Card", secondary="user_section_cards", back_populates="user_sections")