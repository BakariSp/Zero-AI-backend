"""
Script to seed achievement data in the database.
Run this script to add default achievements to track learning progress.
"""

from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import Achievement
from app.achievements.schemas import AchievementCreate
from app.achievements.crud import create_achievement

def seed_achievements():
    """Seed sample achievements into the database"""
    db = SessionLocal()
    try:
        # Define streak achievements
        streak_achievements = [
            AchievementCreate(
                title="3-Day Streak",
                description="Log in and study for 3 consecutive days",
                badge_image="/assets/badges/streak-3.png",
                achievement_type="streak",
                criteria={"streak_days": 3}
            ),
            AchievementCreate(
                title="7-Day Streak",
                description="Log in and study for 7 consecutive days",
                badge_image="/assets/badges/streak-7.png",
                achievement_type="streak",
                criteria={"streak_days": 7}
            ),
            AchievementCreate(
                title="30-Day Streak",
                description="Log in and study for 30 consecutive days",
                badge_image="/assets/badges/streak-30.png",
                achievement_type="streak",
                criteria={"streak_days": 30}
            )
        ]
        
        # Define card completion achievements
        card_achievements = [
            AchievementCreate(
                title="Card Collector",
                description="Complete 10 learning cards",
                badge_image="/assets/badges/cards-10.png",
                achievement_type="completion",
                criteria={"type": "cards_completed", "count": 10}
            ),
            AchievementCreate(
                title="Memory Master",
                description="Complete 50 learning cards",
                badge_image="/assets/badges/cards-50.png",
                achievement_type="completion",
                criteria={"type": "cards_completed", "count": 50}
            ),
            AchievementCreate(
                title="Knowledge Guru",
                description="Complete 100 learning cards",
                badge_image="/assets/badges/cards-100.png",
                achievement_type="completion",
                criteria={"type": "cards_completed", "count": 100}
            )
        ]
        
        # Define course completion achievements
        course_achievements = [
            AchievementCreate(
                title="Course Beginner",
                description="Complete your first course",
                badge_image="/assets/badges/course-1.png",
                achievement_type="completion",
                criteria={"type": "courses_completed", "count": 1}
            ),
            AchievementCreate(
                title="Course Explorer",
                description="Complete 3 courses",
                badge_image="/assets/badges/course-3.png",
                achievement_type="completion",
                criteria={"type": "courses_completed", "count": 3}
            ),
            AchievementCreate(
                title="Course Expert",
                description="Complete 10 courses",
                badge_image="/assets/badges/course-10.png",
                achievement_type="completion",
                criteria={"type": "courses_completed", "count": 10}
            )
        ]
        
        # Define learning path achievements
        path_achievements = [
            AchievementCreate(
                title="Path Finder",
                description="Complete your first learning path",
                badge_image="/assets/badges/path-1.png",
                achievement_type="completion",
                criteria={"type": "learning_paths_completed", "count": 1}
            ),
            AchievementCreate(
                title="Path Voyager",
                description="Complete 3 learning paths",
                badge_image="/assets/badges/path-3.png",
                achievement_type="completion",
                criteria={"type": "learning_paths_completed", "count": 3}
            )
        ]
        
        # Define custom section achievements
        section_achievements = [
            AchievementCreate(
                title="Section Creator",
                description="Create your first custom learning section",
                badge_image="/assets/badges/section-1.png",
                achievement_type="completion",
                criteria={"type": "custom_sections_created", "count": 1}
            ),
            AchievementCreate(
                title="Section Architect",
                description="Create 5 custom learning sections",
                badge_image="/assets/badges/section-5.png",
                achievement_type="completion",
                criteria={"type": "custom_sections_created", "count": 5}
            )
        ]
        
        # Combine all achievements
        all_achievements = (
            streak_achievements + 
            card_achievements + 
            course_achievements + 
            path_achievements +
            section_achievements
        )
        
        # Insert achievements, skipping if title already exists
        for achievement_data in all_achievements:
            # Check if achievement with this title already exists
            existing = db.query(Achievement).filter(
                Achievement.title == achievement_data.title
            ).first()
            
            if not existing:
                create_achievement(db, achievement_data)
                print(f"Created achievement: {achievement_data.title}")
            else:
                print(f"Achievement already exists: {achievement_data.title}")
        
        print("Achievements seeding completed!")
        
    finally:
        db.close()

if __name__ == "__main__":
    seed_achievements() 