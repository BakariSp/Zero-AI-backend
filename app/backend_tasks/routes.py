from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging

from app.db import get_db
from app.models import User
from app.auth import get_current_active_user
from . import crud, schemas

router = APIRouter(
    prefix="/tasks",
    tags=["System Tasks"],
    responses={404: {"description": "Not found"}}
)

@router.get("/{task_id}", response_model=schemas.UserTaskResponse)
def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the status of a specific background task.
    """
    db_task = crud.get_user_task(db, task_id=task_id)
    if not db_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Permission check
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
    Get a list of system tasks initiated by the current user.
    """
    tasks = crud.get_user_tasks_by_user(db, user_id=current_user.id, skip=skip, limit=limit)
    return tasks

@router.get("/learning-paths/{learning_path_id}", response_model=schemas.UserTaskResponse)
def get_task_for_learning_path(
    learning_path_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the latest task associated with a specific learning path.
    """
    db_task = crud.get_latest_task_for_learning_path(db, learning_path_id=learning_path_id)
    if not db_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No task found for this learning path")

    # Permission check
    if db_task.user_id != current_user.id and not current_user.is_superuser:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this task")

    logging.info(f"Returning db_task: type={type(db_task)}, value={db_task}")
    return db_task 