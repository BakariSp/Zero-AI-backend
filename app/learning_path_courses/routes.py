from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db import get_db
from app.models import User, LearningPath, Course, learning_path_courses
from app.learning_paths.crud import get_learning_path
from app.courses.crud import get_course
from app.users.routes import get_current_active_user_unified

router = APIRouter()

@router.get("/learning-path-courses", response_model=List[dict])
def get_learning_path_courses(
    learning_path_id: Optional[int] = None,
    course_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Get all associations between learning paths and courses"""
    query = db.query(
        learning_path_courses.c.learning_path_id,
        learning_path_courses.c.course_id,
        learning_path_courses.c.order_index
    )
    
    if learning_path_id:
        query = query.filter(learning_path_courses.c.learning_path_id == learning_path_id)
    
    if course_id:
        query = query.filter(learning_path_courses.c.course_id == course_id)
    
    results = query.all()
    return [
        {
            "learning_path_id": result.learning_path_id,
            "course_id": result.course_id,
            "order_index": result.order_index
        }
        for result in results
    ]

@router.post("/learning-path-courses", response_model=dict)
def add_course_to_learning_path(
    learning_path_id: int,
    course_id: int,
    order_index: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Add a course to a learning path (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if learning path exists
    learning_path = get_learning_path(db, path_id=learning_path_id)
    if not learning_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning path not found"
        )
    
    # Check if course exists
    course = get_course(db, course_id=course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if association already exists
    existing = db.query(learning_path_courses).filter(
        learning_path_courses.c.learning_path_id == learning_path_id,
        learning_path_courses.c.course_id == course_id
    ).first()
    
    if existing:
        # Update order index if association exists
        db.execute(
            learning_path_courses.update().where(
                learning_path_courses.c.learning_path_id == learning_path_id,
                learning_path_courses.c.course_id == course_id
            ).values(order_index=order_index)
        )
    else:
        # Create new association
        db.execute(
            learning_path_courses.insert().values(
                learning_path_id=learning_path_id,
                course_id=course_id,
                order_index=order_index
            )
        )
    
    db.commit()
    
    return {
        "learning_path_id": learning_path_id,
        "course_id": course_id,
        "order_index": order_index
    }

@router.delete("/learning-path-courses", status_code=status.HTTP_204_NO_CONTENT)
def remove_course_from_learning_path(
    learning_path_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Remove a course from a learning path (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if association exists
    existing = db.query(learning_path_courses).filter(
        learning_path_courses.c.learning_path_id == learning_path_id,
        learning_path_courses.c.course_id == course_id
    ).first()
    
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not associated with this learning path"
        )
    
    # Remove association
    db.execute(
        learning_path_courses.delete().where(
            learning_path_courses.c.learning_path_id == learning_path_id,
            learning_path_courses.c.course_id == course_id
        )
    )
    
    db.commit()
    
    return {"detail": "Course removed from learning path successfully"} 