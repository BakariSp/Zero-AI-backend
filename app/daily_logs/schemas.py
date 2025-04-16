from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, date

class DailyLogBase(BaseModel):
    log_date: date
    completed_sections: Optional[List[int]] = None
    notes: Optional[str] = None
    study_time_minutes: Optional[int] = None

class DailyLogCreate(DailyLogBase):
    pass

class DailyLogUpdate(BaseModel):
    completed_sections: Optional[List[int]] = None
    notes: Optional[str] = None
    study_time_minutes: Optional[int] = None

class DailyLogResponse(DailyLogBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True 