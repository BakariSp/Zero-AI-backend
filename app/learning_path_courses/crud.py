from sqlalchemy.orm import Session
from app.db import Base
from app.models import LearningPath, Course, learning_path_courses
from sqlalchemy import insert

def add_course_to_learning_path(
    db: Session, 
    learning_path_id: int, 
    course_id: int, 
    order_index: int
) -> None:
    """
    Add a course to a learning path with specified order index
    
    Args:
        db: Database session
        learning_path_id: ID of the learning path
        course_id: ID of the course to add
        order_index: Order index of the course in the learning path
    """
    # Check if learning path exists
    learning_path = db.query(LearningPath).filter(LearningPath.id == learning_path_id).first()
    if not learning_path:
        raise ValueError(f"Learning path with ID {learning_path_id} not found")
    
    # Check if course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise ValueError(f"Course with ID {course_id} not found")
    
    # Insert association with order_index
    stmt = insert(learning_path_courses).values(
        learning_path_id=learning_path_id,
        course_id=course_id,
        order_index=order_index
    )
    
    db.execute(stmt)
    db.commit()
    
    return None 