from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, timedelta

from . import schemas
from .models import DailyTask

def get_daily_task(db: Session, task_id: int) -> Optional[DailyTask]:
    """Get a daily task by its ID"""
    return db.query(DailyTask).filter(DailyTask.id == task_id).first()

def get_daily_tasks_by_user_date_range(
    db: Session, 
    user_id: int, 
    start_date: date, 
    end_date: date
) -> List[DailyTask]:
    """Get all daily tasks for a user within a date range"""
    return db.query(DailyTask).filter(
        DailyTask.user_id == user_id,
        DailyTask.scheduled_date >= start_date,
        DailyTask.scheduled_date <= end_date
    ).order_by(DailyTask.scheduled_date, DailyTask.start_time).all()

def create_daily_task(db: Session, task: schemas.DailyTaskCreate) -> DailyTask:
    """Create a new daily task"""
    db_task = DailyTask(**task.model_dump())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

def update_daily_task(db: Session, task_id: int, task_update: schemas.DailyTaskUpdate) -> Optional[DailyTask]:
    """Update an existing daily task"""
    db_task = get_daily_task(db, task_id)
    if not db_task:
        return None
    
    # Update fields that are provided
    update_data = task_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_task, key, value)
    
    db.commit()
    db.refresh(db_task)
    return db_task

def delete_daily_task(db: Session, task_id: int) -> bool:
    """Delete a daily task"""
    db_task = get_daily_task(db, task_id)
    if not db_task:
        return False
    db.delete(db_task)
    db.commit()
    return True

def reschedule_section_tasks(
    db: Session, 
    section_id: int, 
    user_id: int,
    new_start_date: date, 
    new_end_date: date
) -> List[DailyTask]:
    """Reschedule all tasks in a section to be evenly distributed across a new date range"""
    # Get all tasks for the section
    tasks = db.query(DailyTask).filter(
        DailyTask.section_id == section_id,
        DailyTask.user_id == user_id
    ).order_by(DailyTask.scheduled_date, DailyTask.start_time).all()
    
    if not tasks:
        return []
    
    # Calculate the number of days in the range
    days_range = (new_end_date - new_start_date).days
    if days_range <= 0:
        days_range = 1  # At minimum, schedule all on the same day
    
    # Distribute tasks evenly
    num_tasks = len(tasks)
    
    # If we have more tasks than days, some days will have multiple tasks
    # If we have fewer tasks than days, some days will have no tasks
    for i, task in enumerate(tasks):
        # Calculate which day this task should be on
        if days_range >= num_tasks:
            # If we have more days than tasks, space them out evenly
            day_offset = i * (days_range / num_tasks)
        else:
            # If we have more tasks than days, distribute multiple per day
            day_offset = i // (num_tasks / days_range)
            
        new_date = new_start_date + timedelta(days=int(day_offset))
        task.scheduled_date = new_date
    
    db.commit()
    return tasks

def shift_future_tasks(db: Session, user_id: int, from_date: date, days_shift: int) -> int:
    """Shift all tasks after from_date by a certain number of days"""
    if days_shift == 0:
        return 0
    
    # Find all tasks that need to be shifted
    tasks = db.query(DailyTask).filter(
        DailyTask.user_id == user_id,
        DailyTask.scheduled_date >= from_date
    ).all()
    
    # Shift each task
    for task in tasks:
        task.scheduled_date = task.scheduled_date + timedelta(days=days_shift)
    
    db.commit()
    return len(tasks)

def get_daily_tasks_by_user_id(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[DailyTask]:
    """Gets a paginated list of daily tasks for a specific user."""
    return db.query(DailyTask)\
             .filter(DailyTask.user_id == user_id)\
             .order_by(DailyTask.scheduled_date.desc(), DailyTask.start_time.desc())\
             .offset(skip)\
             .limit(limit)\
             .all() 