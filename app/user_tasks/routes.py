from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.db import get_db
from app.models import User
from app.auth import get_current_active_user
from . import crud, schemas

router = APIRouter(
    prefix="/calendar",
    tags=["Calendar Tasks"],
    responses={404: {"description": "Not found"}}
)

@router.get("/tasks", response_model=List[schemas.DailyTaskResponse])
async def get_calendar_tasks(
    user_id: int,
    start: date,
    end: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all tasks for a user within a specified date range.
    This endpoint is compatible with calendar views.
    """
    # For OPTIONS requests
    if current_user is None:
        return []
        
    # Authorization check - only allow users to view their own tasks
    if user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view tasks for this user"
        )
    
    tasks = crud.get_daily_tasks_by_user_date_range(
        db=db,
        user_id=user_id,
        start_date=start,
        end_date=end
    )
    
    return tasks

@router.patch("/tasks/{task_id}", response_model=schemas.DailyTaskResponse)
async def update_calendar_task(
    task_id: int,
    task_update: schemas.DailyTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update a daily task's scheduled time or status.
    Access this endpoint at: PATCH /api/calendar/tasks/{task_id}
    """
    # For OPTIONS requests, current_user might be None, so we return early
    if current_user is None:
        # This is just a safeguard; OPTIONS requests should be handled by middleware
        return None
        
    # First, get the task to check ownership
    task = crud.get_daily_task(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Authorization check
    if task.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this task"
        )
    
    # Update the task
    updated_task = crud.update_daily_task(db, task_id, task_update)
    if not updated_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Failed to update task"
        )
    
    return updated_task

@router.delete("/tasks/{task_id}", response_model=dict)
async def delete_calendar_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a daily task.
    Access this endpoint at: DELETE /api/calendar/tasks/{task_id}
    """
    # For OPTIONS requests, current_user might be None, so we return early
    if current_user is None:
        # This is just a safeguard; OPTIONS requests should be handled by middleware
        return {"success": True, "message": "OPTIONS request handled"}
        
    # First, get the task to check ownership
    task = crud.get_daily_task(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Authorization check
    if task.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this task"
        )
    
    # Delete the task
    success = crud.delete_daily_task(db, task_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Failed to delete task"
        )
    
    return {
        "success": True,
        "message": f"Task {task_id} successfully deleted"
    }

@router.post("/sections/{section_id}/reschedule", response_model=List[schemas.DailyTaskResponse])
async def reschedule_section(
    section_id: int,
    reschedule_data: schemas.RescheduleSection,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Reschedule all tasks in a section to be evenly distributed across a new date range.
    """
    # For OPTIONS requests
    if current_user is None:
        return []
        
    # Perform the rescheduling operation
    tasks = crud.reschedule_section_tasks(
        db=db,
        section_id=section_id,
        user_id=current_user.id,
        new_start_date=reschedule_data.new_start_date,
        new_end_date=reschedule_data.new_end_date
    )
    
    if not tasks:
        return []
    
    return tasks

@router.post("/tasks/shift", response_model=dict)
async def shift_future_tasks(
    shift_request: schemas.ShiftTasksRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Shift all future tasks after a certain date by a specified number of days.
    """
    # For OPTIONS requests
    if current_user is None:
        return {"success": True, "message": "OPTIONS request handled"}
        
    # Authorization check
    if shift_request.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to shift tasks for this user"
        )
    
    # Perform the shift operation
    num_tasks_shifted = crud.shift_future_tasks(
        db=db,
        user_id=shift_request.user_id,
        from_date=shift_request.from_date,
        days_shift=shift_request.days
    )
    
    return {
        "success": True,
        "tasks_shifted": num_tasks_shifted,
        "message": f"Successfully shifted {num_tasks_shifted} tasks by {shift_request.days} days"
    }

@router.post("/tasks", response_model=schemas.DailyTaskResponse)
async def create_calendar_task(
    task: schemas.DailyTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Manually add a new daily task to the calendar.
    For standalone tasks, you can omit card_id, section_id, course_id, and learning_path_id.
    """
    # For OPTIONS requests
    if current_user is None:
        return schemas.DailyTaskResponse(
            id=0,
            user_id=0,
            task_description="OPTIONS request",
            scheduled_date=date.today(),
            status="pending"
        )
        
    # Authorization check
    if task.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create tasks for this user"
        )
    
    # Validate card_id if provided
    if task.card_id is not None and task.card_id == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid card_id: Card with ID 0 does not exist. Please provide a valid card_id or omit it for standalone tasks."
        )
    
    try:
        # Create the new task
        new_task = crud.create_daily_task(db, task)
        return new_task
    except Exception as e:
        # Handle database errors 
        detail = "Failed to create task"
        if "foreign key constraint fails" in str(e):
            detail = "Foreign key constraint violation. If you're creating a task linked to learning content, make sure all referenced IDs exist in the database."
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )

@router.get("/me", response_model=List[schemas.DailyTaskResponse])
def get_my_tasks(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a paginated list of tasks scheduled for the current user.
    """
    # For OPTIONS requests
    if current_user is None:
        return []
        
    tasks = crud.get_daily_tasks_by_user_id(db, user_id=current_user.id, skip=skip, limit=limit)
    return tasks

@router.post("/me", response_model=List[schemas.DailyTaskResponse])
def create_my_tasks(
    task: schemas.DailyTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a task for the current user.
    This endpoint automatically sets the user_id to the current user.
    For standalone tasks, you can omit card_id, section_id, course_id, and learning_path_id.
    """
    # For OPTIONS requests
    if current_user is None:
        return [schemas.DailyTaskResponse(
            id=0,
            user_id=0,
            task_description="OPTIONS request",
            scheduled_date=date.today(),
            status="pending"
        )]
        
    # Override the user_id to ensure it's the current user
    task.user_id = current_user.id
    
    # Validate card_id if provided
    if task.card_id is not None and task.card_id == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid card_id: Card with ID 0 does not exist. Please provide a valid card_id or omit it for standalone tasks."
        )
    
    try:
        # Create the new task
        new_task = crud.create_daily_task(db, task)
        return [new_task]  # Return as a list to match the response model
    except Exception as e:
        # Handle database errors 
        detail = "Failed to create task"
        if "foreign key constraint fails" in str(e):
            detail = "Foreign key constraint violation. If you're creating a task linked to learning content, make sure all referenced IDs exist in the database."
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )

@router.delete("/me/{task_id}", response_model=dict)
def delete_my_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a task belonging to the current user.
    This endpoint automatically ensures the task belongs to the current user.
    """
    # For OPTIONS requests
    if current_user is None:
        return {"success": True, "message": "OPTIONS request handled"}
        
    # Get the task
    task = crud.get_daily_task(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Ensure the task belongs to the current user
    if task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this task"
        )
    
    # Delete the task
    success = crud.delete_daily_task(db, task_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Failed to delete task"
        )
    
    return {
        "success": True,
        "message": f"Task {task_id} successfully deleted"
    }

@router.patch("/me/{task_id}", response_model=schemas.DailyTaskResponse)
def update_my_task(
    task_id: int,
    task_update: schemas.DailyTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update a task belonging to the current user.
    This endpoint automatically ensures the task belongs to the current user.
    """
    # For OPTIONS requests
    if current_user is None:
        return schemas.DailyTaskResponse(
            id=0,
            user_id=0,
            task_description="OPTIONS request",
            scheduled_date=date.today(),
            status="pending"
        )
        
    # Get the task
    task = crud.get_daily_task(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Ensure the task belongs to the current user
    if task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this task"
        )
    
    # Update the task
    updated_task = crud.update_daily_task(db, task_id, task_update)
    if not updated_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Failed to update task"
        )
    
    return updated_task 