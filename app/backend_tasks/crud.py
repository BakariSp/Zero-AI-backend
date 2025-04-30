from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime, timezone

from . import schemas
from .models import UserTask, TaskStatusEnum

def create_user_task(db: Session, task_data: schemas.UserTaskCreate) -> UserTask:
    """Create a new system task"""
    db_task = UserTask(**task_data.model_dump())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

def get_user_task(db: Session, task_id: str) -> Optional[UserTask]:
    """Get a system task by its ID"""
    return db.query(UserTask).filter(UserTask.task_id == task_id).first()

def update_user_task(db: Session, task_id: str, task_update: schemas.UserTaskUpdate) -> Optional[UserTask]:
    """Update an existing system task"""
    db_task = get_user_task(db, task_id)
    if not db_task:
        return None

    update_data = task_update.model_dump(exclude_unset=True)

    # Set ended_at timestamp if the task is entering a terminal state
    terminal_states = [
        TaskStatusEnum.COMPLETED, 
        TaskStatusEnum.FAILED,
        TaskStatusEnum.TIMEOUT, 
        TaskStatusEnum.CANCELLED, 
        TaskStatusEnum.COMPLETED_WITH_ERRORS
    ]
    
    if 'status' in update_data and update_data['status'] in terminal_states and not db_task.ended_at:
        update_data['ended_at'] = datetime.now(timezone.utc)

    for key, value in update_data.items():
        setattr(db_task, key, value)

    db.commit()
    db.refresh(db_task)
    return db_task

def get_user_tasks_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[UserTask]:
    """Get all system tasks for a specific user"""
    return db.query(UserTask)\
             .filter(UserTask.user_id == user_id)\
             .order_by(desc(UserTask.created_at))\
             .offset(skip)\
             .limit(limit)\
             .all()

def get_latest_task_for_learning_path(db: Session, learning_path_id: int) -> Optional[UserTask]:
    """Get the most recent system task for a specific learning path"""
    return db.query(UserTask)\
             .filter(UserTask.learning_path_id == learning_path_id)\
             .order_by(desc(UserTask.created_at))\
             .first() 