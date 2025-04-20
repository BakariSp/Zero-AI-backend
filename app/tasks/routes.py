from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging

from app.db import get_db
from app.models import User # Adjust import
from app.auth import get_current_active_user # Adjust import
from . import crud, schemas
from app.tasks.models import UserTask, TaskStatusEnum, TaskStageEnum # Import UserTask model
from app.tasks.crud import get_user_task, get_user_tasks_by_user, get_latest_task_for_learning_path # Import CRUD function

router = APIRouter(
    tags=["Tasks"],
    responses={404: {"description": "Not found"}},
)

@router.get("/{task_id}/status", response_model=schemas.UserTaskResponse)
def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user) # Keep auth if needed
):
    """
    Get the status of a specific background task.
    """
    db_task = crud.get_user_task_by_task_id(db, task_id=task_id)
    if not db_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Optional: Add permission check - does current_user own this task?
    if db_task.user_id != current_user.id and not current_user.is_superuser:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this task")

    return db_task

@router.get("/users/me", response_model=List[schemas.UserTaskResponse])
def get_my_tasks(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a list of tasks initiated by the current user.
    """
    tasks = crud.get_user_tasks_by_user_id(db, user_id=current_user.id, skip=skip, limit=limit)
    return tasks

@router.get("/learning-paths/{learning_path_id}", response_model=schemas.UserTaskResponse)
def get_task_for_learning_path(
    learning_path_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user) # Keep auth
):
    """
    Get the latest task associated with a specific learning path.
    """
    db_task = crud.get_user_task_by_learning_path_id(db, learning_path_id=learning_path_id)
    if not db_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No task found for this learning path")

    # Optional: Check if user owns the task or the learning path
    if db_task.user_id != current_user.id and not current_user.is_superuser:
         # You might want a more complex check here involving learning path ownership
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this task")

    return db_task

@router.get("/tasks/{task_id}/status", response_model=schemas.UserTaskResponse)
async def read_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the status of a specific background task by its task_id.
    Ensures the user owns the task or is an admin.
    """
    db_task = get_user_task(db, task_id)
    if db_task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Check ownership or admin status
    if db_task.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this task")

    return db_task

@router.get("/tasks/users/me", response_model=List[schemas.UserTaskResponse])
async def read_user_tasks(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a list of tasks initiated by the current user.
    """
    tasks = get_user_tasks_by_user(db, user_id=current_user.id, skip=skip, limit=limit)
    return tasks

@router.get("/tasks/learning-paths/{learning_path_id}/latest", response_model=schemas.UserTaskResponse)
async def read_latest_task_for_learning_path(
    learning_path_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the status of the most recent task associated with a specific learning path.
    Ensures the user owns the task or is an admin.
    """
    db_task = get_latest_task_for_learning_path(db, learning_path_id=learning_path_id)

    if db_task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No task found for learning path ID {learning_path_id}"
        )

    # Check ownership or admin status before returning
    if db_task.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No accessible task found for learning path ID {learning_path_id}"
        )

    logging.info(f"Returning db_task: type={type(db_task)}, value={db_task}")
    return db_task