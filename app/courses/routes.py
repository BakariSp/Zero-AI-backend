from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.db import get_db
from app.models import User, Course, UserCourse, UserLearningPath, LearningPath
from app.courses.schemas import (
    CourseCreate,
    CourseResponse,
    CourseUpdate,
    UserCourseCreate,
    UserCourseResponse,
    UserCourseUpdate
)
from app.courses.crud import (
    get_course,
    get_courses,
    create_course,
    update_course,
    delete_course,
    get_user_courses,
    get_user_course,
    assign_course_to_user,
    update_user_course_progress
)
from app.achievements.crud import check_completion_achievements
from app.progress.utils import update_learning_path_progress_based_on_courses
from app.users.routes import get_current_active_user_unified

router = APIRouter()

@router.get("/courses", response_model=List[CourseResponse])
def read_courses(
    skip: int = 0,
    limit: int = 100,
    is_template: bool = True,
    db: Session = Depends(get_db)
):
    """Get all course templates (public endpoint)"""
    courses = get_courses(db, skip=skip, limit=limit, is_template=is_template)
    return courses

@router.get("/courses/{course_id}", response_model=CourseResponse)
def read_course(
    course_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific course template (public endpoint)"""
    course = get_course(db, course_id=course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    return course

@router.post("/courses", response_model=CourseResponse)
def create_new_course(
    course: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Create a new course (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return create_course(db=db, course_data=course)

@router.put("/courses/{course_id}", response_model=CourseResponse)
def update_existing_course(
    course_id: int,
    course: CourseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Update an existing course (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return update_course(
        db=db, 
        course_id=course_id, 
        course_data=course.dict(exclude_unset=True)
    )

@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Delete a course (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    delete_course(db=db, course_id=course_id)

@router.get("/users/me/courses", response_model=List[UserCourseResponse])
def read_user_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Get all courses for the current user"""
    return get_user_courses(db=db, user_id=current_user.id)

@router.post("/users/me/courses", response_model=UserCourseResponse)
def add_course_to_user(
    user_course: UserCourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Add an existing course to the current user"""
    # Check if course exists
    course = get_course(db, course_id=user_course.course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    return assign_course_to_user(
        db=db, 
        user_id=current_user.id, 
        course_id=user_course.course_id
    )

@router.put("/users/me/courses/{course_id}", response_model=UserCourseResponse)
def update_user_course(
    course_id: int,
    user_course_update: UserCourseUpdate,
    update_learning_paths: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Update progress for a user's course"""
    user_course = get_user_course(db, user_id=current_user.id, course_id=course_id)
    if not user_course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found for this user"
        )
    
    # Check if course is being completed (either by progress or completed_at)
    course_completed = False
    old_progress = user_course.progress
    
    # Update progress if provided
    if user_course_update.progress is not None:
        user_course = update_user_course_progress(
            db=db,
            user_id=current_user.id,
            course_id=course_id,
            progress=user_course_update.progress
        )
        if user_course.progress >= 100.0:
            course_completed = True
    
    # Update completed_at if provided
    if user_course_update.completed_at is not None:
        user_course.completed_at = user_course_update.completed_at
        db.commit()
        db.refresh(user_course)
        course_completed = True
    
    # If progress has changed and update_learning_paths is True, update related learning paths
    if update_learning_paths and user_course_update.progress is not None and user_course_update.progress != old_progress:
        path_progresses = update_learning_path_progress_based_on_courses(
            db=db,
            user_id=current_user.id,
            course_id=course_id
        )
        if path_progresses:
            logging.info(f"Updated progress for {len(path_progresses)} learning paths")
    
    # Check for achievements if course was completed
    if course_completed:
        check_completion_achievements(db, user_id=current_user.id)
    
    return user_course

@router.get("/learning-paths/{path_id}/courses", response_model=List[CourseResponse])
def read_learning_path_courses(
    path_id: int,
    db: Session = Depends(get_db)
):
    """Get all courses for a specific learning path (public endpoint)"""
    # Implementation depends on your database structure
    # This is a placeholder
    learning_path = db.query(LearningPath).filter(LearningPath.id == path_id).first()
    if not learning_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning path not found"
        )
    
    return learning_path.courses

@router.get("/users/me/learning-paths/{path_id}/courses", response_model=List[UserCourseResponse])
def read_user_learning_path_courses(
    path_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Get all courses for a user's learning path"""
    # Implementation depends on your database structure
    # This is a placeholder
    user_path = db.query(UserLearningPath).filter(
        UserLearningPath.user_id == current_user.id,
        UserLearningPath.learning_path_id == path_id
    ).first()
    
    if not user_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning path not found for this user"
        )
    
    # Get all courses for this learning path
    learning_path = db.query(LearningPath).filter(LearningPath.id == path_id).first()
    
    # Get user's progress for each course
    result = []
    for course in learning_path.courses:
        user_course = get_user_course(db, user_id=current_user.id, course_id=course.id)
        if not user_course:
            # Create user course if it doesn't exist
            user_course = assign_course_to_user(db, user_id=current_user.id, course_id=course.id)
        result.append(user_course)
    
    return result