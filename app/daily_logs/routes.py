from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime, timedelta

from app.db import get_db
from app.models import User, DailyLog
from app.daily_logs.schemas import (
    DailyLogCreate,
    DailyLogResponse,
    DailyLogUpdate
)
from app.daily_logs.crud import (
    get_daily_log,
    get_user_daily_log,
    get_user_daily_logs,
    create_daily_log,
    update_daily_log,
    delete_daily_log,
    get_user_streak
)
from app.users.routes import get_current_active_user_unified

router = APIRouter()

@router.get("/daily-logs", response_model=List[DailyLogResponse])
def read_user_logs(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Get all daily logs for the current user with optional date range"""
    logs = get_user_daily_logs(
        db, 
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date
    )
    return logs

@router.get("/daily-logs/today", response_model=Optional[DailyLogResponse])
def read_today_log(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Get today's log for the current user if it exists"""
    today = date.today()
    log = get_user_daily_log(db, user_id=current_user.id, log_date=today)
    return log

@router.get("/daily-logs/{log_id}", response_model=DailyLogResponse)
def read_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Get a specific daily log by ID"""
    log = get_daily_log(db, log_id=log_id)
    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Daily log not found"
        )
    
    # Ensure user can only access their own logs
    if log.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return log

@router.post("/daily-logs", response_model=DailyLogResponse)
def create_log(
    log: DailyLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Create a new daily log for the current user"""
    return create_daily_log(db=db, user_id=current_user.id, log_data=log)

@router.put("/daily-logs/{log_id}", response_model=DailyLogResponse)
def update_log(
    log_id: int,
    log: DailyLogUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Update an existing daily log"""
    # Check if log exists and belongs to user
    existing_log = get_daily_log(db, log_id=log_id)
    if existing_log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Daily log not found"
        )
    
    if existing_log.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return update_daily_log(
        db=db, 
        log_id=log_id, 
        log_data=log.dict(exclude_unset=True)
    )

@router.delete("/daily-logs/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Delete a daily log"""
    # Check if log exists and belongs to user
    existing_log = get_daily_log(db, log_id=log_id)
    if existing_log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Daily log not found"
        )
    
    if existing_log.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    delete_daily_log(db=db, log_id=log_id)
    return {"detail": "Daily log deleted successfully"}

@router.get("/streak", response_model=dict)
def get_current_streak(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Get the current streak of consecutive days with logs"""
    streak = get_user_streak(db, user_id=current_user.id)
    return {"streak": streak}

@router.post("/daily-logs/check-in", response_model=DailyLogResponse)
def daily_check_in(
    completed_sections: Optional[List[int]] = None,
    notes: Optional[str] = None,
    study_time_minutes: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Quick check-in for today"""
    today = date.today()
    
    # Check if already checked in today
    existing_log = get_user_daily_log(db, user_id=current_user.id, log_date=today)
    if existing_log:
        # Update existing log
        update_data = {}
        if completed_sections is not None:
            update_data["completed_sections"] = completed_sections
        if notes is not None:
            update_data["notes"] = notes
        if study_time_minutes is not None:
            update_data["study_time_minutes"] = study_time_minutes
        
        return update_daily_log(db=db, log_id=existing_log.id, log_data=update_data)
    
    # Create new log for today
    log_data = DailyLogCreate(
        log_date=today,
        completed_sections=completed_sections,
        notes=notes,
        study_time_minutes=study_time_minutes
    )
    
    return create_daily_log(db=db, user_id=current_user.id, log_data=log_data) 