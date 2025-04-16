from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
from fastapi import HTTPException, status

from app.models import DailyLog, User
from app.daily_logs.schemas import DailyLogCreate, DailyLogUpdate

def get_daily_log(db: Session, log_id: int) -> Optional[DailyLog]:
    return db.query(DailyLog).filter(DailyLog.id == log_id).first()

def get_user_daily_log(db: Session, user_id: int, log_date: date) -> Optional[DailyLog]:
    return db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
        func.date(DailyLog.log_date) == log_date
    ).first()

def get_user_daily_logs(
    db: Session, 
    user_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List[DailyLog]:
    query = db.query(DailyLog).filter(DailyLog.user_id == user_id)
    
    if start_date:
        query = query.filter(func.date(DailyLog.log_date) >= start_date)
    
    if end_date:
        query = query.filter(func.date(DailyLog.log_date) <= end_date)
    
    return query.order_by(DailyLog.log_date.desc()).all()

def create_daily_log(db: Session, user_id: int, log_data: DailyLogCreate) -> DailyLog:
    # Check if log for this date already exists
    existing_log = get_user_daily_log(db, user_id, log_data.log_date)
    if existing_log:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Daily log for this date already exists"
        )
    
    # Create new log
    db_log = DailyLog(
        user_id=user_id,
        log_date=log_data.log_date,
        completed_sections=log_data.completed_sections,
        notes=log_data.notes,
        study_time_minutes=log_data.study_time_minutes
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

def update_daily_log(
    db: Session, 
    log_id: int, 
    log_data: Dict[str, Any]
) -> DailyLog:
    db_log = get_daily_log(db, log_id)
    if not db_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Daily log not found"
        )
    
    for key, value in log_data.items():
        setattr(db_log, key, value)
    
    db.commit()
    db.refresh(db_log)
    return db_log

def delete_daily_log(db: Session, log_id: int) -> bool:
    db_log = get_daily_log(db, log_id)
    if not db_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Daily log not found"
        )
    
    db.delete(db_log)
    db.commit()
    return True

def get_user_streak(db: Session, user_id: int) -> int:
    """Calculate the current streak of consecutive days with logs"""
    today = date.today()
    streak = 0
    current_date = today
    
    while True:
        log = get_user_daily_log(db, user_id, current_date)
        if not log:
            break
        
        streak += 1
        current_date = current_date - timedelta(days=1)
    
    return streak 