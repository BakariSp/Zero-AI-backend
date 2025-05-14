from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, text
from typing import List, Dict, Any, Optional
from datetime import date, datetime
from fastapi import HTTPException, status

from app.models import Achievement, User, user_achievements, user_cards, UserCourse, UserLearningPath, UserSection
from app.achievements.schemas import AchievementCreate, AchievementUpdate

def get_achievement(db: Session, achievement_id: int) -> Optional[Achievement]:
    return db.query(Achievement).filter(Achievement.id == achievement_id).first()

def get_achievements(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    achievement_type: Optional[str] = None
) -> List[Achievement]:
    query = db.query(Achievement)
    
    if achievement_type:
        query = query.filter(Achievement.achievement_type == achievement_type)
    
    return query.offset(skip).limit(limit).all()

def create_achievement(db: Session, achievement_data: AchievementCreate) -> Achievement:
    db_achievement = Achievement(**achievement_data.dict())
    db.add(db_achievement)
    db.commit()
    db.refresh(db_achievement)
    return db_achievement

def update_achievement(
    db: Session, 
    achievement_id: int, 
    achievement_data: Dict[str, Any]
) -> Achievement:
    db_achievement = get_achievement(db, achievement_id)
    if not db_achievement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Achievement not found"
        )
    
    for key, value in achievement_data.items():
        setattr(db_achievement, key, value)
    
    db.commit()
    db.refresh(db_achievement)
    return db_achievement

def delete_achievement(db: Session, achievement_id: int) -> bool:
    db_achievement = get_achievement(db, achievement_id)
    if not db_achievement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Achievement not found"
        )
    
    db.delete(db_achievement)
    db.commit()
    return True

def get_user_achievements(db: Session, user_id: int) -> List[Dict[str, Any]]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get all achievements earned by the user with achievement date
    result = []
    
    achievements_with_dates = db.query(
        Achievement, 
        user_achievements.c.achieved_at
    ).join(
        user_achievements, 
        user_achievements.c.achievement_id == Achievement.id
    ).filter(
        user_achievements.c.user_id == user_id
    ).all()
    
    for achievement, achieved_at in achievements_with_dates:
        achievement_data = {
            "achievement": achievement,
            "achieved_at": achieved_at
        }
        result.append(achievement_data)
    
    return result

def award_achievement_to_user(
    db: Session, 
    user_id: int, 
    achievement_id: int
) -> Dict[str, Any]:
    # Check if achievement exists
    achievement = get_achievement(db, achievement_id)
    if not achievement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Achievement not found"
        )
    
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if user already has this achievement
    is_awarded = db.execute(
        text("""
        SELECT 1 FROM user_achievements 
        WHERE user_id = :user_id AND achievement_id = :achievement_id
        """),
        {"user_id": user_id, "achievement_id": achievement_id}
    ).fetchone()
    
    if is_awarded:
        # Achievement already awarded, return existing data
        assoc_data = db.execute(
            text("""
            SELECT achieved_at 
            FROM user_achievements 
            WHERE user_id = :user_id AND achievement_id = :achievement_id
            """),
            {"user_id": user_id, "achievement_id": achievement_id}
        ).fetchone()
        
        return {
            "achievement": achievement,
            "achieved_at": assoc_data.achieved_at
        }
    
    # Award achievement to user
    now = datetime.now()
    db.execute(
        text("""
        INSERT INTO user_achievements (user_id, achievement_id, achieved_at)
        VALUES (:user_id, :achievement_id, :achieved_at)
        """),
        {
            "user_id": user_id, 
            "achievement_id": achievement_id,
            "achieved_at": now
        }
    )
    db.commit()
    
    return {
        "achievement": achievement,
        "achieved_at": now
    }

def check_streak_achievements(db: Session, user_id: int, streak: int) -> List[Dict[str, Any]]:
    """Check and award streak-based achievements"""
    # Get all streak achievements that the user doesn't have yet
    streak_achievements = db.query(Achievement).filter(
        Achievement.achievement_type == "streak",
        ~Achievement.id.in_(
            db.query(user_achievements.c.achievement_id)
            .filter(user_achievements.c.user_id == user_id)
            .subquery()
        )
    ).all()
    
    awarded = []
    for achievement in streak_achievements:
        # Check if streak meets the criteria
        required_streak = achievement.criteria.get("streak_days", 0)
        if streak >= required_streak:
            # Award the achievement
            award_data = award_achievement_to_user(
                db=db,
                user_id=user_id,
                achievement_id=achievement.id
            )
            awarded.append(award_data)
    
    return awarded

def check_completion_achievements(db: Session, user_id: int) -> List[Dict[str, Any]]:
    """Check and award completion-based achievements"""
    # Get all completion achievements that the user doesn't have yet
    completion_achievements = db.query(Achievement).filter(
        Achievement.achievement_type == "completion",
        ~Achievement.id.in_(
            db.query(user_achievements.c.achievement_id)
            .filter(user_achievements.c.user_id == user_id)
            .subquery()
        )
    ).all()
    
    # Get user counts of different completions
    # 1. Count cards completed
    completed_cards_count = db.query(func.count(user_cards.c.card_id)).filter(
        user_cards.c.user_id == user_id,
        user_cards.c.is_completed == True
    ).scalar() or 0
    
    # 2. Count completed courses
    completed_courses_count = db.query(func.count(UserCourse.id)).filter(
        UserCourse.user_id == user_id,
        UserCourse.completed_at.isnot(None)
    ).scalar() or 0
    
    # 3. Count courses with progress at 100%
    completed_courses_by_progress = db.query(func.count(UserCourse.id)).filter(
        UserCourse.user_id == user_id,
        UserCourse.progress >= 100.0
    ).scalar() or 0
    
    # Use the higher of the two course completion counts
    completed_courses_count = max(completed_courses_count, completed_courses_by_progress)
    
    # 4. Count completed learning paths
    completed_paths_count = db.query(func.count(UserLearningPath.id)).filter(
        UserLearningPath.user_id == user_id,
        UserLearningPath.completed_at.isnot(None)
    ).scalar() or 0
    
    # 5. Count learning paths with progress at 100%
    completed_paths_by_progress = db.query(func.count(UserLearningPath.id)).filter(
        UserLearningPath.user_id == user_id,
        UserLearningPath.progress >= 100.0
    ).scalar() or 0
    
    # Use the higher of the two learning path completion counts
    completed_paths_count = max(completed_paths_count, completed_paths_by_progress)
    
    # 6. Count user sections (custom sections created)
    custom_sections_count = db.query(func.count(UserSection.id)).filter(
        UserSection.user_id == user_id
    ).scalar() or 0
    
    # Process achievements
    awarded = []
    for achievement in completion_achievements:
        # Get criteria
        criteria_type = achievement.criteria.get("type", "")
        threshold = achievement.criteria.get("count", 0)
        
        should_award = False
        
        # Check different criteria types
        if criteria_type == "cards_completed" and completed_cards_count >= threshold:
            should_award = True
        elif criteria_type == "courses_completed" and completed_courses_count >= threshold:
            should_award = True
        elif criteria_type == "learning_paths_completed" and completed_paths_count >= threshold:
            should_award = True
        elif criteria_type == "custom_sections_created" and custom_sections_count >= threshold:
            should_award = True
        
        # Award achievement if criteria met
        if should_award:
            award_data = award_achievement_to_user(
                db=db,
                user_id=user_id,
                achievement_id=achievement.id
            )
            awarded.append(award_data)
    
    return awarded 