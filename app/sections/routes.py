from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timezone

from app.db import SessionLocal
from app.auth.jwt import get_current_active_user
from app.models import User, CourseSection, UserSection, Card, Course
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
from app.services.ai_generator import get_card_generator_agent, CardGeneratorAgent
from app.cards.crud import create_card as crud_create_card
from app.cards.schemas import CardCreate

router = APIRouter()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 获取系统模板章节
@router.get("/sections", response_model=List[SectionResponse])
def get_sections(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """获取系统模板章节列表"""
    sections = crud.get_sections(db, skip=skip, limit=limit)
    return sections

# 获取单个系统模板章节详情
@router.get("/sections/{section_id}", response_model=SectionResponse)
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
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取当前用户的自定义章节列表"""
    sections = crud.get_user_sections(db, user_id=current_user.id, skip=skip, limit=limit)
    return sections

# 获取单个用户自定义章节详情
@router.get("/users/me/sections/{section_id}", response_model=UserSectionResponse)
def get_user_section(
    section_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取单个用户自定义章节详情"""
    section = crud.get_user_section(db, user_id=current_user.id, section_id=section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User section not found"
        )
    return section

# 基于模板创建用户自定义章节
@router.post("/users/me/sections", response_model=UserSectionResponse)
def create_user_section(
    section_data: UserSectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """更新用户自定义章节信息"""
    section = crud.get_user_section(db, user_id=current_user.id, section_id=section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User section not found"
        )
    
    return crud.update_user_section(db, section=section, section_data=section_data)

# 删除用户自定义章节
@router.delete("/users/me/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """删除用户自定义章节"""
    section = crud.get_user_section(db, user_id=current_user.id, section_id=section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User section not found"
        )
    
    crud.delete_user_section(db, section_id=section_id)
    return {"detail": "Section deleted successfully"}

# 向用户章节添加卡片
@router.post("/users/me/sections/{section_id}/cards", response_model=UserSectionResponse)
def add_card_to_section(
    section_id: int,
    card_data: CardInSectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """向用户自定义章节添加卡片"""
    section = crud.get_user_section(db, user_id=current_user.id, section_id=section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User section not found"
        )
    
    return crud.add_card_to_user_section(
        db, 
        user_section_id=section_id, 
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """更新用户章节中卡片的顺序"""
    section = crud.get_user_section(db, user_id=current_user.id, section_id=section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User section not found"
        )
    
    return crud.update_card_in_user_section(
        db, 
        user_section_id=section_id, 
        card_id=card_id, 
        order_index=card_data.order_index
    )

# 从用户章节中移除卡片
@router.delete("/users/me/sections/{section_id}/cards/{card_id}", response_model=UserSectionResponse)
def remove_card_from_section(
    section_id: int,
    card_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """从用户章节中移除卡片"""
    section = crud.get_user_section(db, user_id=current_user.id, section_id=section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User section not found"
        )
    
    return crud.remove_card_from_user_section(db, user_section_id=section_id, card_id=card_id)


@router.post("/course-sections", response_model=SectionResponse)
def create_course_section(
    data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
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

@router.post("/sections/{section_id}/generate-test-cards", status_code=status.HTTP_201_CREATED)
async def generate_test_cards_for_section(
    section_id: int,
    num_cards: int = 4, # Default number of cards to generate
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user) # Add auth if needed
):
    """
    (For Testing) Generates a specified number of cards for a given section ID based on its title.
    """
    # Optional: Add permission check (e.g., superuser only)
    # if not current_user.is_superuser:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    section = crud.get_section(db, section_id=section_id)
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    # Assuming learning path difficulty is stored somewhere or use a default
    # You might want to fetch the associated Learning Path to get its difficulty
    # For now, using a default.
    difficulty = "intermediate"

    try:
        # --- FIX: Use the helper function to get the initialized agent ---
        try:
            agent = get_card_generator_agent()
        except RuntimeError as e:
             # Handle case where agent wasn't initialized (e.g., missing config)
             logging.error(f"Failed to get CardGeneratorAgent: {e}")
             raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"AI Service Unavailable: {e}")
        # --- END FIX ---

        logging.info(f"Generating {num_cards} test cards for section '{section.title}' (ID: {section_id}) with difficulty '{difficulty}'")

        # Call the generator without course_title
        generated_card_data: List[CardCreate] = await agent.generate_multiple_cards_from_topic(
            topic=section.title,
            num_cards=num_cards,
            # course_title=None, # Explicitly None or just omit
            difficulty=difficulty
        )

        created_cards = []
        # card_order = 1 # Start card order from 1 for this batch - Using helper now

        for card_data in generated_card_data:
            try:
                # Create card (create_card handles duplicates by keyword)
                card_db = crud_create_card(db, card_data=card_data)

                # Add card to section with order
                # Use the helper to get the next available order index for this section
                from app.cards.crud import _get_next_card_order_in_section
                next_order = _get_next_card_order_in_section(db, section_id)
                # Use the correct crud function for adding card to section
                crud.add_card_to_section(db, section_id, card_db.id, next_order)
                created_cards.append(card_db)
                logging.info(f"  Created/Linked Card ID {card_db.id} ('{card_db.keyword}') to Section {section_id} with order {next_order}")

            except Exception as card_err:
                logging.error(f"Error processing/saving card '{getattr(card_data, 'keyword', 'N/A')}' for section {section_id}: {card_err}", exc_info=True)
                # Decide how to handle partial failures (e.g., continue, rollback, return error)

        return {"message": f"Generated and linked {len(created_cards)} cards for section {section_id}", "card_ids": [c.id for c in created_cards]}

    except Exception as e:
        logging.error(f"Failed to generate test cards for section {section_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/{section_id}/generate-test-cards", response_model=List[CardResponse], tags=["Sections", "AI Generation"])
async def generate_test_cards_for_section(
    section_id: int,
    num_cards: int = Query(5, ge=1, le=10), # Default 5, min 1, max 10
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user) # Add auth if needed
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
