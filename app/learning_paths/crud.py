from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
import logging
from datetime import datetime

from app.models import LearningPath, CourseSection, UserLearningPath, User, Course, learning_path_courses, course_section_association
from app.backend_tasks.models import UserTask
from app.learning_paths.schemas import LearningPathCreate, CourseSectionCreate
from sqlalchemy.orm import joinedload, selectinload
from app.users.crud import check_subscription_limits
from app.user_daily_usage.crud import increment_usage
from sqlalchemy import func

def get_learning_path(db: Session, path_id: int) -> Optional[LearningPath]:
    return db.query(LearningPath).filter(LearningPath.id == path_id).first()

def get_learning_paths(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    category: Optional[str] = None
) -> List[LearningPath]:
    query = db.query(LearningPath)
    
    if category:
        query = query.filter(LearningPath.category == category)
    
    return query.offset(skip).limit(limit).all()

def create_learning_path(db: Session, path_data: LearningPathCreate) -> LearningPath:
    # Extract sections data if present
    sections_data = path_data.sections if hasattr(path_data, "sections") else None
    
    # Create path without sections first
    path_dict = path_data.dict(exclude={"sections"})
    db_path = LearningPath(**path_dict)
    db.add(db_path)
    db.commit()
    db.refresh(db_path)
    
    # Add sections if provided
    if sections_data:
        for section_data in sections_data:
            db_section = CourseSection(**section_data.dict(), learning_path_id=db_path.id)
            db.add(db_section)
        
        db.commit()
        db.refresh(db_path)
    
    return db_path

def update_learning_path(
    db: Session, 
    path_id: int, 
    path_data: Dict[str, Any]
) -> LearningPath:
    db_path = get_learning_path(db, path_id)
    if not db_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning path not found"
        )
    
    for key, value in path_data.items():
        setattr(db_path, key, value)
    
    db.commit()
    db.refresh(db_path)
    return db_path

def delete_learning_path(db: Session, path_id: int) -> bool:
    db_path = get_learning_path(db, path_id)
    if not db_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning path not found"
        )
    
    # Delete associated UserTasks first to avoid foreign key constraint errors
    db.query(UserTask).filter(UserTask.learning_path_id == path_id).delete(synchronize_session=False)
    
    # Now delete the LearningPath
    db.delete(db_path)
    db.commit()
    return True

def get_user_learning_paths(db: Session, user_id: int) -> List[UserLearningPath]:
    user_paths = (
        db.query(UserLearningPath)
        .options(
            selectinload(UserLearningPath.learning_path)
            .selectinload(LearningPath.courses)
            .selectinload(Course.sections)
            .selectinload(CourseSection.cards)
        )
        .filter(UserLearningPath.user_id == user_id)
        .order_by(UserLearningPath.created_at.desc())
        .all()
    )

    return [path for path in user_paths if path.learning_path]

def get_user_learning_path(db: Session, user_id: int, path_id: int) -> Optional[UserLearningPath]:
    return db.query(UserLearningPath).filter(
        UserLearningPath.user_id == user_id,
        UserLearningPath.learning_path_id == path_id
    ).first()

def assign_learning_path_to_user(db: Session, user_id: int, learning_path_id: int) -> UserLearningPath:
    """
    Assign a learning path to a user. This creates an association without copying the path.
    This is used for paths the user has access to but doesn't own a copy of.
    """
    # Check if association already exists
    existing = db.query(UserLearningPath).filter(
        UserLearningPath.user_id == user_id,
        UserLearningPath.learning_path_id == learning_path_id
    ).first()
    
    if existing:
        return existing
    
    # Create new association
    user_path = UserLearningPath(
        user_id=user_id,
        learning_path_id=learning_path_id,
        progress=0.0,
        start_date=datetime.now(),
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    db.add(user_path)
    db.commit()
    db.refresh(user_path)
    
    return user_path

def update_user_learning_path_progress(
    db: Session,
    user_id: int,
    path_id: int,
    progress: float
) -> UserLearningPath:
    db_user_path = get_user_learning_path(db, user_id, path_id)
    if not db_user_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User learning path not found"
        )
    
    db_user_path.progress = progress
    db.commit()
    db.refresh(db_user_path)
    return db_user_path

def get_user_learning_path_by_ids(db: Session, user_id: int, learning_path_id: int) -> Optional[UserLearningPath]:
    """Retrieve a specific UserLearningPath assignment."""
    return db.query(UserLearningPath).filter(
        UserLearningPath.user_id == user_id,
        UserLearningPath.learning_path_id == learning_path_id
    ).first()

def clone_learning_path_for_user(
    db: Session, 
    user_id: int, 
    learning_path_id: int
) -> UserLearningPath:
    """
    Clone a learning path and its structure for a user.
    
    This creates a personal copy of the learning path for the user, including:
    - A new learning path record
    - Copies of all associated courses
    - Copies of all course sections
    - All relationships between courses and sections
    - Duplicates of all cards associated with each section (so users don't share cards)
    
    Returns the new UserLearningPath association.
    """
    # Get the original learning path with all related data
    original_path = db.query(LearningPath).filter(LearningPath.id == learning_path_id).first()
    
    if not original_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Learning path with ID {learning_path_id} not found"
        )
    
    # Check if user already has this learning path cloned
    user_paths = db.query(UserLearningPath).join(
        LearningPath, UserLearningPath.learning_path_id == LearningPath.id
    ).filter(
        UserLearningPath.user_id == user_id,
        LearningPath.title == original_path.title
    ).all()
    
    if user_paths:
        # Already has a clone, return the existing one
        return user_paths[0]
    
    # Start a transaction to ensure atomicity
    try:
        # Create a copy of the learning path
        new_path = LearningPath(
            title=original_path.title,
            description=original_path.description,
            category=original_path.category,
            difficulty_level=original_path.difficulty_level,
            estimated_days=original_path.estimated_days,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            is_template=False  # This is now a user's personal copy
        )
        db.add(new_path)
        db.flush()  # Get the new path ID
        
        # Get all courses related to the original path
        courses_query = db.query(Course).join(
            learning_path_courses,
            learning_path_courses.c.course_id == Course.id
        ).filter(
            learning_path_courses.c.learning_path_id == original_path.id
        ).order_by(learning_path_courses.c.order_index)
        
        original_courses = courses_query.all()
        
        # Clone each course and maintain order
        for i, original_course in enumerate(original_courses):
            # Create a copy of the course
            new_course = Course(
                title=original_course.title,
                description=original_course.description,
                estimated_days=original_course.estimated_days,
                is_template=False,  # User's personal copy
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(new_course)
            db.flush()  # Get the new course ID
            
            # Associate the new course with the new learning path
            db.execute(
                learning_path_courses.insert().values(
                    learning_path_id=new_path.id,
                    course_id=new_course.id,
                    order_index=i  # Maintain original order
                )
            )
            
            # Get sections related to this course
            sections_query = db.query(CourseSection).join(
                course_section_association,
                course_section_association.c.section_id == CourseSection.id
            ).filter(
                course_section_association.c.course_id == original_course.id
            ).order_by(course_section_association.c.order_index)
            
            original_sections = sections_query.all()
            
            # Clone each section and maintain order
            for j, original_section in enumerate(original_sections):
                # Create a copy of the section
                new_section = CourseSection(
                    learning_path_id=new_path.id,  # Link to the new learning path
                    title=original_section.title,
                    description=original_section.description,
                    order_index=j,  # Maintain original order within the course
                    estimated_days=original_section.estimated_days,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    is_template=False  # User's personal copy
                )
                db.add(new_section)
                db.flush()  # Get the new section ID
                
                # Associate the new section with the new course
                db.execute(
                    course_section_association.insert().values(
                        course_id=new_course.id,
                        section_id=new_section.id,
                        order_index=j  # Maintain original order
                    )
                )
                
                # Get cards associated with the original section
                from app.models import section_cards, Card
                
                cards_query = db.query(Card).join(
                    section_cards,
                    section_cards.c.card_id == Card.id
                ).filter(
                    section_cards.c.section_id == original_section.id
                ).order_by(section_cards.c.order_index)
                
                original_cards = cards_query.all()
                
                # Clone each card and maintain the original order
                for k, original_card in enumerate(original_cards):
                    # Create a duplicate of the card
                    new_card = Card(
                        keyword=original_card.keyword,
                        question=original_card.question,
                        answer=original_card.answer,
                        explanation=original_card.explanation,
                        difficulty=original_card.difficulty,
                        resources=original_card.resources[:] if original_card.resources else [],
                        level=original_card.level,
                        tags=original_card.tags[:] if original_card.tags else None,
                        created_by=f"Cloned for user {user_id} from card {original_card.id}",
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    db.add(new_card)
                    db.flush()  # Get the new card ID
                    
                    # Get the original order_index
                    order_data = db.query(section_cards.c.order_index).filter(
                        section_cards.c.section_id == original_section.id,
                        section_cards.c.card_id == original_card.id
                    ).first()
                    
                    order_index = order_data[0] if order_data else k
                    
                    # Create the association between the new card and the new section
                    db.execute(
                        section_cards.insert().values(
                            section_id=new_section.id,
                            card_id=new_card.id,
                            order_index=order_index
                        )
                    )
        
        # Create the user learning path association
        user_path = UserLearningPath(
            user_id=user_id,
            learning_path_id=new_path.id,
            progress=0.0,
            start_date=datetime.now(),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(user_path)
        
        # Commit the transaction
        db.commit()
        db.refresh(user_path)
        
        # Return the new user learning path association
        return user_path
    
    except Exception as e:
        db.rollback()
        logging.error(f"Error cloning learning path: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clone learning path: {str(e)}"
        ) 