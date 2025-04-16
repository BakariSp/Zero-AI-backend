from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy import insert

from app.models import Course, UserCourse, User, CourseSection, course_section_association
from app.courses.schemas import CourseCreate, CourseUpdate

def get_course(db: Session, course_id: int) -> Optional[Course]:
    return db.query(Course).filter(Course.id == course_id).first()

def get_courses(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    is_template: bool = True
) -> List[Course]:
    query = db.query(Course).filter(Course.is_template == is_template)
    return query.offset(skip).limit(limit).all()

def create_course(db: Session, course_data: CourseCreate) -> Course:
    db_course = Course(**course_data.dict())
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course

def update_course(
    db: Session, 
    course_id: int, 
    course_data: Dict[str, Any]
) -> Course:
    db_course = get_course(db, course_id)
    if not db_course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    for key, value in course_data.items():
        setattr(db_course, key, value)
    
    db.commit()
    db.refresh(db_course)
    return db_course

def delete_course(db: Session, course_id: int) -> bool:
    db_course = get_course(db, course_id)
    if not db_course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    db.delete(db_course)
    db.commit()
    return True

def get_user_courses(db: Session, user_id: int) -> List[UserCourse]:
    return db.query(UserCourse).filter(UserCourse.user_id == user_id).all()

def get_user_course(db: Session, user_id: int, course_id: int) -> Optional[UserCourse]:
    return db.query(UserCourse).filter(
        UserCourse.user_id == user_id,
        UserCourse.course_id == course_id
    ).first()

def assign_course_to_user(
    db: Session, 
    user_id: int, 
    course_id: int
) -> UserCourse:
    # Check if user already has this course
    existing = get_user_course(db, user_id, course_id)
    if existing:
        return existing
    
    # Create new user course
    db_user_course = UserCourse(
        user_id=user_id,
        course_id=course_id,
        progress=0.0
    )
    db.add(db_user_course)
    db.commit()
    db.refresh(db_user_course)
    return db_user_course

def update_user_course_progress(
    db: Session,
    user_id: int,
    course_id: int,
    progress: float
) -> UserCourse:
    db_user_course = get_user_course(db, user_id, course_id)
    if not db_user_course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User course not found"
        )
    
    db_user_course.progress = progress
    db.commit()
    db.refresh(db_user_course)
    return db_user_course

def add_section_to_course(
    db: Session, 
    course_id: int, 
    section_id: int, 
    order_index: int
) -> None:
    """
    Add a section to a course with specified order index
    
    Args:
        db: Database session
        course_id: ID of the course
        section_id: ID of the section to add
        order_index: Order index of the section in the course
    """
    # Check if course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise ValueError(f"Course with ID {course_id} not found")
    
    # Check if section exists
    section = db.query(CourseSection).filter(CourseSection.id == section_id).first()
    if not section:
        raise ValueError(f"Section with ID {section_id} not found")
    
    # Insert association with order_index
    stmt = insert(course_section_association).values(
        course_id=course_id,
        section_id=section_id,
        order_index=order_index
    )
    
    db.execute(stmt)
    db.commit()
    
    return None