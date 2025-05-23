from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timezone

from app.db import SessionLocal, get_db
from app.users.routes import get_current_active_user_unified
from app.models import User, CourseSection, UserSection, Card, Course, UserLearningPath, section_cards, user_section_cards, course_section_association, UserCourse
from app.sections import crud
from app.sections.schemas import (
    SectionResponse,
    UserSectionCreate,
    UserSectionUpdate,
    UserSectionResponse,
    CardInSectionCreate,
    CardInSectionUpdate,
    CardResponse
)
from app.sections.crud import format_user_section_for_response
from app.services.ai_generator import get_card_generator_agent, CardGeneratorAgent
from app.cards.crud import create_card as crud_create_card, update_user_card as update_card_completion, save_card_for_user, get_user_card_by_id
from app.cards.schemas import CardCreate
from app.setup import increment_user_resource_usage, get_user_remaining_resources
from app.progress.utils import update_course_progress_based_on_sections, update_learning_path_progress_based_on_courses, cascade_progress_update

# New Pydantic models for the refactored endpoint
# from pydantic import BaseModel

# class CardCompletionRequestBody(BaseModel):
#     is_completed: bool

# class UpdatedCardInfo(BaseModel):
#     id: int
#     is_completed: bool
#     # Add other fields if needed based on "..." in docs/progress_update.md

# class ProgressUpdateResponse(BaseModel):
#     updated_card: UpdatedCardInfo
#     updated_section_progress: float
#     updated_course_progress: float
#     updated_learning_path_progress: float

router = APIRouter(
    prefix="/sections",
    tags=["Sections"],
    responses={404: {"description": "Not found"}}
)

# 获取系统模板章节
@router.get("/", response_model=List[SectionResponse])
def get_sections(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """获取系统模板章节列表"""
    sections = crud.get_sections(db, skip=skip, limit=limit)
    return sections

# 获取单个系统模板章节详情
@router.get("/{section_id}", response_model=SectionResponse)
def get_section(
    section_id: int, 
    db: Session = Depends(get_db)
):
    """获取单个系统模板章节详情"""
    section = crud.get_section(db, section_id=section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Section not found"
        )
    return section

# 获取用户的自定义章节列表
@router.get("/users/me/sections", response_model=List[UserSectionResponse])
def get_user_sections(
    request: Request,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """获取当前用户的自定义章节列表"""
    sections = crud.get_user_sections(db, user_id=current_user.id, skip=skip, limit=limit)
    
    # Format each section using the utility function
    return [format_user_section_for_response(db, section) for section in sections]

# 获取单个用户自定义章节详情
@router.get("/users/me/sections/{section_id}", response_model=UserSectionResponse)
def get_user_section(
    section_id: int, # This section_id from URL is template_section_id
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """
    Get a single user section detail, where section_id is the TEMPLATE section ID.
    It fetches the user's personalized version of that template section.
    """
    # Query UserSection directly using section_id as template_section_id
    user_section = db.query(UserSection).filter(
        UserSection.user_id == current_user.id,
        UserSection.section_template_id == section_id # section_id from URL is template_id
    ).first()
    
    if not user_section:
        # Check if the template section itself exists to give a more precise error or context
        template_section_exists = db.query(CourseSection.id).filter(CourseSection.id == section_id).first()
        if not template_section_exists:
            logging.warning(f"/users/me/sections/{section_id}: Template section itself not found.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template section with ID {section_id} not found."
            )
        else:
            # Template exists, but user has no personalized version yet.
            # For a GET request for a *user* section, if the user-specific record doesn't exist,
            # it's appropriate to return 404. Creation should happen via POST/PUT or specific utility endpoints.
            logging.warning(f"/users/me/sections/{section_id}: UserSection for template ID {section_id} not found for user {current_user.id}. Template exists.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User-specific section for template ID {section_id} not found. User has not interacted with this section yet or it hasn't been explicitly created."
            )

    # Format the section using the utility function
    # This function needs to correctly fetch cards associated with user_section.id via user_section_cards
    return format_user_section_for_response(db, user_section)

# 基于模板创建用户自定义章节
@router.post("/users/me/sections", response_model=UserSectionResponse)
def create_user_section(
    section_data: UserSectionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """创建用户自定义章节，可以基于模板或从头创建"""
    if section_data.section_template_id:
        # 基于模板创建
        return crud.copy_section_to_user(db, user_id=current_user.id, section_id=section_data.section_template_id)
    else:
        # 从头创建
        return crud.create_user_section(db, user_id=current_user.id, section_data=section_data)

# 更新用户自定义章节
@router.put("/users/me/sections/{section_id}", response_model=UserSectionResponse)
def update_user_section(
    section_id: int,
    section_data: UserSectionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """更新用户自定义章节信息"""
    section = crud.find_user_section(db, user_id=current_user.id, section_id=section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User section not found"
        )
    
    return crud.update_user_section(db, section=section, section_data=section_data)

# 更新用户章节进度
@router.put("/users/me/sections/{section_id}/progress", response_model=UserSectionResponse)
def update_user_section_progress(
    section_id: int,
    progress: float,
    request: Request,
    update_related: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """
    Update the progress of a user's section
    
    Args:
        section_id: ID of the section
        progress: Progress value (0.0 to 100.0)
        update_related: Whether to update related courses and learning paths
    
    Returns:
        Updated UserSection object
    """
    try:
        # First find the section (by ID or template ID)
        section = crud.find_user_section(db, user_id=current_user.id, section_id=section_id)
        if not section:
            raise ValueError(f"Section with ID {section_id} not found for user {current_user.id}")
        
        # Store the old progress to check if it changed
        old_progress = section.progress
        
        # Then update the progress of the found section
        section.progress = max(0.0, min(100.0, progress))
        db.commit()
        db.refresh(section)
        
        # If progress changed and update_related is True, update related courses and learning paths
        if update_related and old_progress != section.progress:
            # Update courses containing this section
            course_progresses = update_course_progress_based_on_sections(db, current_user.id, section.id)
            if course_progresses:
                logging.info(f"Updated progress for {len(course_progresses)} courses")
                
                # Get courses that were updated
                # We'll need their IDs to update learning paths
                template_section_id = section.section_template_id
                if template_section_id:
                    course_ids = db.query(course_section_association.c.course_id).filter(
                        course_section_association.c.section_id == template_section_id
                    ).all()
                    course_ids = [course_id for (course_id,) in course_ids]
                    
                    # Update learning paths containing these courses
                    for course_id in course_ids:
                        path_progresses = update_learning_path_progress_based_on_courses(db, current_user.id, course_id)
                        if path_progresses:
                            logging.info(f"Updated progress for {len(path_progresses)} learning paths")
        
        # Format the section data to match the UserSectionResponse model
        # This adds the required order_index field and properly formats cards
        formatted_section = {
            "id": section.id,
            "user_id": section.user_id,
            "section_template_id": section.section_template_id,
            "title": section.title,
            "description": section.description,
            "progress": section.progress,
            "created_at": section.created_at,
            "updated_at": section.updated_at,
            "order_index": 0,  # Default value, as UserSection doesn't have this field
            "cards": []
        }
        
        # Format the cards if there are any
        if section.cards:
            # Get card ordering information from the user_section_cards table
            cards_with_order = db.query(Card, user_section_cards.c.order_index, user_section_cards.c.is_custom).join(
                user_section_cards,
                user_section_cards.c.card_id == Card.id
            ).filter(
                user_section_cards.c.user_section_id == section.id
            ).order_by(user_section_cards.c.order_index).all()
            
            for card, order_index, is_custom in cards_with_order:
                formatted_section["cards"].append({
                    "card": card,
                    "order_index": order_index,
                    "is_custom": is_custom
                })
        
        return formatted_section
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logging.error(f"Error updating section progress: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update section progress"
        )

# 删除用户自定义章节
@router.delete("/users/me/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_section(
    section_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """删除用户自定义章节"""
    section = crud.find_user_section(db, user_id=current_user.id, section_id=section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User section not found"
        )
    
    crud.delete_user_section(db, section_id=section.id)
    return {"detail": "Section deleted successfully"}

# 向用户章节添加卡片
@router.post("/users/me/sections/{section_id}/cards", response_model=UserSectionResponse)
def add_card_to_section(
    section_id: int,
    card_data: CardInSectionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """向用户自定义章节添加卡片"""
    section = crud.find_user_section(db, user_id=current_user.id, section_id=section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User section not found"
        )
    
    return crud.add_card_to_user_section(
        db, 
        user_section_id=section.id,  # Use the actual section.id
        card_id=card_data.card_id, 
        order_index=card_data.order_index,
        is_custom=card_data.is_custom
    )

# 更新用户章节中卡片的顺序
@router.put("/users/me/sections/{section_id}/cards/{card_id}", response_model=UserSectionResponse)
def update_card_in_section(
    section_id: int,
    card_id: int,
    card_data: CardInSectionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """更新用户章节中卡片的顺序"""
    section = crud.find_user_section(db, user_id=current_user.id, section_id=section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User section not found"
        )
    
    return crud.update_card_in_user_section(
        db, 
        user_section_id=section.id,  # Use the actual section.id
        card_id=card_id, 
        order_index=card_data.order_index
    )

# 从用户章节中移除卡片
@router.delete("/users/me/sections/{section_id}/cards/{card_id}", response_model=UserSectionResponse)
def remove_card_from_section(
    section_id: int,
    card_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """从用户章节中移除卡片"""
    section = crud.find_user_section(db, user_id=current_user.id, section_id=section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User section not found"
        )
    
    return crud.remove_card_from_user_section(db, user_section_id=section.id, card_id=card_id)

@router.post("/course-sections", response_model=SectionResponse)
def create_course_section(
    data: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Create a section for a course"""
    try:
        # Extract data
        course_id = data.get("course_id")
        section_data = data.get("section_data")
        order_index = data.get("order_index", 0)  # Get order_index from the top level
        
        # Validate input data
        if not course_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="course_id is required"
            )
        
        if not section_data or not section_data.get("title"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="section_data with title is required"
            )
        
        # Check if course exists
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course with id {course_id} not found"
            )
        
        # Create section
        db_section = CourseSection(
            title=section_data.get("title"),
            description=section_data.get("description"),
            order_index=section_data.get("order_index", 0),
            estimated_days=section_data.get("estimated_days"),
            is_template=True
        )
        
        db.add(db_section)
        db.flush()
        
        # Create association between course and section
        # Using the SQLAlchemy core to directly insert into the association table
        from sqlalchemy import text
        
        stmt = text(
            "INSERT INTO course_section_association (course_id, section_id, order_index) VALUES (:course_id, :section_id, :order_index)"
        )
        db.execute(stmt, {"course_id": course_id, "section_id": db_section.id, "order_index": order_index})
        db.commit()
        db.refresh(db_section)
        
        return db_section
    
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"Error creating course section: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create section: {str(e)}"
        )

@router.post("/sections/{section_id}/generate-test-cards", response_model=List[CardResponse], tags=["Sections", "AI Generation"])
async def generate_test_cards_for_section(
    section_id: int,
    num_cards: int = Query(5, ge=1, le=10), # Default 5, min 1, max 10
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified) # Add auth if needed
):
    """
    Generates a specified number of test flashcards for a given section's topic
    using the fine-tuned AI model, without saving them permanently.
    Primarily for testing the AI generation for a specific section topic.
    """
    db_section = db.query(CourseSection).filter(CourseSection.id == section_id).first()
    if not db_section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    # Get course title for context if available
    course_title = db_section.course.title if db_section.course else "Unknown Course"
    # Use section difficulty if available, otherwise default
    difficulty = db_section.difficulty if db_section.difficulty else "intermediate"

    try:
        # --- FIX: Use the helper function to get the initialized agent ---
        try:
            agent = get_card_generator_agent()
        except RuntimeError as e:
             # Handle case where agent wasn't initialized (e.g., missing config)
             logging.error(f"Failed to get CardGeneratorAgent: {e}")
             raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"AI Service Unavailable: {e}")
        # --- END FIX ---

        logging.info(f"Generating {num_cards} test cards for section '{db_section.title}' (ID: {section_id}) with difficulty '{difficulty}'")

        # Use the agent's method to generate cards
        card_data_list: List[CardCreate] = await agent.generate_multiple_cards_from_topic(
            topic=db_section.title,
            num_cards=num_cards,
            course_title=course_title,
            difficulty=difficulty
        )

        if not card_data_list:
            logging.warning(f"AI returned no test cards for section: {db_section.title} (ID: {section_id})")
            # Return empty list or raise an error? Returning empty list for now.
            return []

        # Convert CardCreate objects to CardResponse objects for the response
        # We are NOT saving these to the DB in this test endpoint
        response_cards = []
        for i, card_data in enumerate(card_data_list):
            # Create a temporary CardResponse-like structure
            # We don't have a real DB ID or timestamps here
            response_cards.append(
                CardResponse(
                    id=-(i+1), # Use negative temp ID
                    keyword=card_data.keyword,
                    question=card_data.question,
                    answer=card_data.answer,
                    explanation=card_data.explanation,
                    difficulty=card_data.difficulty,
                    level=card_data.difficulty, # Map difficulty to level if needed
                    resources=[], # No resources for test cards
                    tags=[], # No tags for test cards
                    created_at=datetime.now(timezone.utc), # Use current time
                    updated_at=datetime.now(timezone.utc)  # Use current time
                )
            )

        return response_cards

    except ValueError as ve:
         logging.error(f"Value error during AI test card generation for section {section_id}: {ve}", exc_info=True)
         raise HTTPException(
             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
             detail=f"Failed to process AI response: {str(ve)}"
         )
    except Exception as e:
        logging.error(f"Failed to generate test cards for section {section_id}: {e}", exc_info=True)
        # Use standard 500 for unexpected errors
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate test cards: {str(e)}")

# Utility endpoint to fix missing user sections
@router.post("/users/me/fix-missing-sections", status_code=status.HTTP_200_OK)
def fix_missing_sections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """
    Utility endpoint to fix missing user sections by creating them from template sections.
    This is useful when a user has learning paths but the corresponding user sections are missing.
    """
    # Get all learning paths associated with the user
    user_learning_paths = db.query(UserLearningPath).filter(
        UserLearningPath.user_id == current_user.id
    ).all()
    
    if not user_learning_paths:
        return {"message": "No learning paths found for user"}
    
    created_sections = 0
    
    # For each learning path
    for ulp in user_learning_paths:
        # Get all template sections in this learning path
        template_sections = db.query(CourseSection).filter(
            CourseSection.learning_path_id == ulp.learning_path_id
        ).all()
        
        for template_section in template_sections:
            # Check if a user section already exists for this template
            existing_user_section = db.query(UserSection).filter(
                UserSection.user_id == current_user.id,
                UserSection.section_template_id == template_section.id
            ).first()
            
            if not existing_user_section:
                # Create a new user section with ID matching the template section ID
                # Don't use SQLAlchemy's auto-increment - explicitly set the ID
                user_section = UserSection(
                    id=template_section.id,  # Explicitly set the ID to match the template section
                    user_id=current_user.id,
                    section_template_id=template_section.id,
                    title=template_section.title,
                    description=template_section.description,
                    progress=0.0
                )
                
                # Before adding, check if an ID conflict exists
                existing_id_conflict = db.query(UserSection).filter(
                    UserSection.id == template_section.id
                ).first()
                
                if existing_id_conflict:
                    # There's already a user section with this ID - use auto-increment instead
                    # We'll have to handle this mismatch in the application code
                    logging.warning(f"ID conflict: UserSection ID {template_section.id} already exists. Using auto-increment instead.")
                    
                    # Remove the explicit ID so SQLAlchemy will use auto-increment
                    user_section = UserSection(
                        user_id=current_user.id,
                        section_template_id=template_section.id,
                        title=template_section.title,
                        description=template_section.description,
                        progress=0.0
                    )
                
                # Add and flush to get the ID
                db.add(user_section)
                db.flush()
                
                # Get cards for this template section
                card_associations = db.query(section_cards).filter(
                    section_cards.c.section_id == template_section.id
                ).all()
                
                # Associate cards with the user section
                for assoc in card_associations:
                    db.execute(
                        user_section_cards.insert().values(
                            user_section_id=user_section.id,
                            card_id=assoc.card_id,
                            order_index=assoc.order_index,
                            is_custom=False
                        )
                    )
                
                created_sections += 1
    
    db.commit()
    
    return {
        "message": f"Successfully created {created_sections} missing user sections",
        "created_count": created_sections
    }

# Utility endpoint to fix card completion status
@router.post("/users/me/sections/{section_id}/fix-completion", status_code=status.HTTP_200_OK)
def fix_section_card_completion(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """
    Utility endpoint to fix inconsistencies between section progress and card completion status.
    If a section has 100% progress, this ensures all cards are marked as completed.
    """
    try:
        # Find the section
        section = crud.find_user_section(db, user_id=current_user.id, section_id=section_id)
        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Section {section_id} not found"
            )
        
        # Only proceed if section has 100% progress
        if section.progress < 100.0:
            return {
                "message": f"Section {section_id} does not have 100% progress (current: {section.progress}%)",
                "cards_fixed": 0
            }
        
        # Get all cards in this section
        cards_query = """
        SELECT 
            usc.card_id
        FROM 
            user_section_cards usc
        WHERE 
            usc.user_section_id = :section_id
        """
        
        cards = db.execute(text(cards_query), {"section_id": section_id}).fetchall()
        card_ids = [card.card_id for card in cards]
        
        if not card_ids:
            return {
                "message": f"Section {section_id} has no cards",
                "cards_fixed": 0
            }
        
        # Get cards that are not marked as completed
        incomplete_cards_query = """
        SELECT 
            uc.card_id
        FROM 
            user_cards uc
        WHERE 
            uc.user_id = :user_id
            AND uc.card_id IN :card_ids
            AND (uc.is_completed = 0 OR uc.is_completed IS NULL)
        """
        
        incomplete_cards = db.execute(
            text(incomplete_cards_query), 
            {"user_id": current_user.id, "card_ids": tuple(card_ids) if len(card_ids) > 1 else f"({card_ids[0]})"}
        ).fetchall()
        
        incomplete_card_ids = [card.card_id for card in incomplete_cards]
        
        # Find cards that don't have user_cards entries at all
        existing_entries = db.query(user_cards.c.card_id).filter(
            user_cards.c.user_id == current_user.id,
            user_cards.c.card_id.in_(card_ids)
        ).all()
        existing_card_ids = set(card_id for (card_id,) in existing_entries)
        
        missing_card_ids = [c_id for c_id in card_ids if c_id not in existing_card_ids]
        
        # Create entries for missing cards
        for card_id in missing_card_ids:
            try:
                db.execute(
                    text("""
                    INSERT INTO user_cards (
                        user_id, card_id, is_completed, saved_at
                    )
                    VALUES (
                        :user_id, :card_id, :is_completed, NOW()
                    )
                    """),
                    {
                        "user_id": current_user.id, 
                        "card_id": card_id,
                        "is_completed": True  # Mark as completed since section is 100%
                    }
                )
            except Exception as e:
                logging.error(f"Error creating user_card entry for card {card_id}: {e}")
        
        # Update incomplete cards to be completed
        for card_id in incomplete_card_ids:
            update_query = """
            UPDATE user_cards
            SET is_completed = 1
            WHERE user_id = :user_id AND card_id = :card_id
            """
            
            db.execute(text(update_query), {"user_id": current_user.id, "card_id": card_id})
        
        # Commit all changes
        db.commit()
        
        total_fixed = len(incomplete_card_ids) + len(missing_card_ids)
        
        return {
            "message": f"Successfully fixed {total_fixed} cards in section {section_id}",
            "cards_fixed": total_fixed,
            "incomplete_cards_fixed": len(incomplete_card_ids),
            "missing_cards_created": len(missing_card_ids)
        }
        
    except Exception as e:
        logging.error(f"Error fixing section card completion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fix card completion status: {str(e)}"
        )
