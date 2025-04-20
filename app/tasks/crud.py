from sqlalchemy.orm import Session
from sqlalchemy import desc # Import desc for ordering
from typing import List, Optional
from datetime import datetime, timezone
import logging

from . import models, schemas
from app.models import User # Assuming User model is needed for context/ownership checks

def create_user_task(db: Session, task_data: schemas.UserTaskCreate) -> models.UserTask:
    db_task = models.UserTask(
        task_id=task_data.task_id,
        user_id=task_data.user_id,
        learning_path_id=task_data.learning_path_id,
        status=task_data.status
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

def get_user_task_by_task_id(db: Session, task_id: str) -> Optional[models.UserTask]:
    return db.query(models.UserTask).filter(models.UserTask.task_id == task_id).first()

def update_user_task(db: Session, task_id: str, task_update: schemas.UserTaskUpdate) -> Optional[models.UserTask]:
    db_task = get_user_task_by_task_id(db, task_id)
    if not db_task:
        logging.error(f"Attempted to update non-existent task: {task_id}")
        return None

    update_data = task_update.model_dump(exclude_unset=True)

    # Set ended_at timestamp if the task is entering a terminal state
    terminal_states = [models.TaskStatusEnum.COMPLETED, models.TaskStatusEnum.FAILED, models.TaskStatusEnum.TIMEOUT, models.TaskStatusEnum.CANCELLED, models.TaskStatusEnum.COMPLETED_WITH_ERRORS]
    if 'status' in update_data and update_data['status'] in terminal_states and not db_task.ended_at:
        update_data['ended_at'] = datetime.now(timezone.utc)

    # Set updated_at timestamp
    update_data['updated_at'] = datetime.now(timezone.utc)

    for key, value in update_data.items():
        setattr(db_task, key, value)

    try:
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        logging.info(f"Updated task {task_id} with data: {update_data}")
        return db_task
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to update task {task_id}: {e}", exc_info=True)
        return None

def get_user_tasks_by_user_id(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[models.UserTask]:
    return db.query(models.UserTask)\
             .filter(models.UserTask.user_id == user_id)\
             .order_by(models.UserTask.created_at.desc())\
             .offset(skip)\
             .limit(limit)\
             .all()

def get_user_task_by_learning_path_id(db: Session, learning_path_id: int) -> Optional[models.UserTask]:
    """Gets the LATEST task associated with a learning path"""
    return db.query(models.UserTask)\
             .filter(models.UserTask.learning_path_id == learning_path_id)\
             .order_by(models.UserTask.created_at.desc())\
             .first()

def get_user_task(db: Session, task_id: str) -> Optional[models.UserTask]:
    return db.query(models.UserTask).filter(models.UserTask.task_id == task_id).first()

def get_user_tasks_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[models.UserTask]:
    return db.query(models.UserTask)\
             .filter(models.UserTask.user_id == user_id)\
             .order_by(desc(models.UserTask.created_at))\
             .offset(skip)\
             .limit(limit)\
             .all()

def create_user_task(db: Session, task: schemas.UserTaskCreate) -> models.UserTask:
    db_task = models.UserTask(**task.model_dump())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

def update_user_task(db: Session, task_id: str, task_update: schemas.UserTaskUpdate) -> Optional[models.UserTask]:
    db_task = get_user_task(db, task_id)
    if db_task:
        update_data = task_update.model_dump(exclude_unset=True) # Only update provided fields

        # Handle potential enum values if they are passed as strings
        if 'status' in update_data and isinstance(update_data['status'], str):
             update_data['status'] = models.TaskStatusEnum(update_data['status'])
        if 'stage' in update_data and isinstance(update_data['stage'], str):
             update_data['stage'] = models.TaskStageEnum(update_data['stage'])

        for key, value in update_data.items():
            setattr(db_task, key, value)

        # Special handling for terminal states to set ended_at
        terminal_states = [models.TaskStatusEnum.COMPLETED, models.TaskStatusEnum.FAILED, models.TaskStatusEnum.TIMEOUT, models.TaskStatusEnum.CANCELLED, models.TaskStatusEnum.COMPLETED_WITH_ERRORS]
        if db_task.status in terminal_states and db_task.ended_at is None:
             db_task.ended_at = models.datetime.now(models.timezone.utc)

        db.commit()
        db.refresh(db_task)
    return db_task

def get_latest_task_for_learning_path(db: Session, learning_path_id: int) -> Optional[models.UserTask]:
    """
    Retrieves the most recent task associated with a given learning_path_id.
    """
    return db.query(models.UserTask)\
             .filter(models.UserTask.learning_path_id == learning_path_id)\
             .order_by(desc(models.UserTask.created_at))\
             .first() 