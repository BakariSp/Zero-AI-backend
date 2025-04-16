# app/recommendation/crud.py
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models import LearningPath, Course, Card, User

def get_recommended_learning_paths(
    db: Session, 
    user_id: Optional[int] = None,
    limit: int = 3
) -> List[LearningPath]:
    """Get recommended learning paths, potentially personalized for a user"""
    # Basic implementation - just get the most recent
    query = db.query(LearningPath).order_by(LearningPath.created_at.desc())
    
    # Here you could add personalization logic based on user_id
    # if user_id:
    #     user = db.query(User).filter(User.id == user_id).first()
    #     if user and user.interests:
    #         # Filter or order by user interests
    
    return query.limit(limit).all()

def get_recommended_courses(
    db: Session, 
    user_id: Optional[int] = None,
    limit: int = 3
) -> List[Course]:
    """Get recommended courses, potentially personalized for a user"""
    query = db.query(Course).order_by(Course.created_at.desc())
    return query.limit(limit).all()

def get_recommended_cards(
    db: Session, 
    user_id: Optional[int] = None,
    limit: int = 10
) -> List[Card]:
    """Get recommended cards, potentially personalized for a user"""
    # Based on your actual Card model fields from app/cards/schemas.py
    # Your Card model has 'keyword' and 'explanation' fields instead of 'title' and 'content'
    query = db.query(Card).order_by(Card.created_at.desc())
    return query.limit(limit).all()