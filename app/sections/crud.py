from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import CourseSection, UserSection, Card, section_cards, user_section_cards, user_cards
from app.sections.schemas import UserSectionCreate, UserSectionUpdate, SectionCreate, CardResponse
from typing import List, Optional, Dict, Any
import logging

# 获取系统模板章节列表
def get_sections(db: Session, skip: int = 0, limit: int = 100) -> List[CourseSection]:
    return db.query(CourseSection).filter(CourseSection.is_template == True).offset(skip).limit(limit).all()

# 获取单个系统模板章节
def get_section(db: Session, section_id: int, template_only: bool = False) -> Optional[CourseSection]:
    query = db.query(CourseSection).filter(CourseSection.id == section_id)
    if template_only:
        query = query.filter(CourseSection.is_template == True)
    return query.first()

# 获取用户自定义章节列表
def get_user_sections(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[UserSection]:
    return db.query(UserSection).filter(UserSection.user_id == user_id).offset(skip).limit(limit).all()

# 获取单个用户自定义章节
def get_user_section(db: Session, user_id: int, section_id: int) -> Optional[UserSection]:
    return db.query(UserSection).filter(UserSection.id == section_id, UserSection.user_id == user_id).first()

# 从头创建用户自定义章节
def create_user_section(db: Session, user_id: int, section_data: UserSectionCreate) -> UserSection:
    db_section = UserSection(
        user_id=user_id,
        title=section_data.title,
        description=section_data.description
    )
    db.add(db_section)
    db.commit()
    db.refresh(db_section)
    return db_section

# 复制模板章节到用户自定义章节
def copy_section_to_user(db: Session, user_id: int, section_id: int) -> UserSection:
    """
    复制一个模板章节到用户的自定义章节
    """
    # 获取原始章节
    original_section = db.query(CourseSection).filter(CourseSection.id == section_id).first()
    if not original_section:
        raise ValueError(f"Section with id {section_id} not found")
    
    # 创建用户章节
    user_section = UserSection(
        user_id=user_id,
        section_template_id=section_id,
        title=original_section.title,
        description=original_section.description
    )
    db.add(user_section)
    db.flush()  # 获取新生成的ID
    
    # 获取原始章节的卡片和顺序
    section_card_associations = db.query(section_cards).filter(
        section_cards.c.section_id == section_id
    ).all()
    
    # 复制卡片关联到用户章节
    for assoc in section_card_associations:
        db.execute(
            user_section_cards.insert().values(
                user_section_id=user_section.id,
                card_id=assoc.card_id,
                order_index=assoc.order_index,
                is_custom=False  # 这是从模板复制的，不是用户自定义的
            )
        )
    
    db.commit()
    db.refresh(user_section)
    return user_section

# 更新用户自定义章节
def update_user_section(db: Session, section: UserSection, section_data: UserSectionUpdate) -> UserSection:
    if section_data.title is not None:
        section.title = section_data.title
    if section_data.description is not None:
        section.description = section_data.description
    if section_data.progress is not None:
        section.progress = section_data.progress
    
    db.commit()
    db.refresh(section)
    return section

# 删除用户自定义章节
def delete_user_section(db: Session, section_id: int) -> None:
    # 首先删除关联的卡片
    db.execute(user_section_cards.delete().where(user_section_cards.c.user_section_id == section_id))
    
    # 然后删除章节
    db.query(UserSection).filter(UserSection.id == section_id).delete()
    db.commit()

# 向用户章节添加卡片
def add_card_to_user_section(db: Session, user_section_id: int, card_id: int, order_index: int, is_custom: bool = False) -> UserSection:
    # 检查卡片是否已经在章节中
    existing = db.query(user_section_cards).filter(
        user_section_cards.c.user_section_id == user_section_id,
        user_section_cards.c.card_id == card_id
    ).first()
    
    if existing:
        # 如果已存在，更新顺序
        db.execute(
            user_section_cards.update().where(
                user_section_cards.c.user_section_id == user_section_id,
                user_section_cards.c.card_id == card_id
            ).values(order_index=order_index)
        )
    else:
        # 如果不存在，添加新关联
        db.execute(
            user_section_cards.insert().values(
                user_section_id=user_section_id,
                card_id=card_id,
                order_index=order_index,
                is_custom=is_custom
            )
        )
    
    db.commit()
    return db.query(UserSection).filter(UserSection.id == user_section_id).first()

# 更新用户章节中卡片的顺序
def update_card_in_user_section(db: Session, user_section_id: int, card_id: int, order_index: int) -> UserSection:
    db.execute(
        user_section_cards.update().where(
            user_section_cards.c.user_section_id == user_section_id,
            user_section_cards.c.card_id == card_id
        ).values(order_index=order_index)
    )
    
    db.commit()
    return db.query(UserSection).filter(UserSection.id == user_section_id).first()

# 从用户章节中移除卡片
def remove_card_from_user_section(db: Session, user_section_id: int, card_id: int) -> UserSection:
    db.execute(
        user_section_cards.delete().where(
            user_section_cards.c.user_section_id == user_section_id,
            user_section_cards.c.card_id == card_id
        )
    )
    
    db.commit()
    return db.query(UserSection).filter(UserSection.id == user_section_id).first()

def add_card_to_section(db: Session, section_id: int, card_id: int, order_index: int) -> None:
    """
    Add a card to a course section with specified order index
    
    Args:
        db: Database session
        section_id: ID of the section
        card_id: ID of the card to add
        order_index: Order index of the card in the section
    """
    # Check if section exists
    section = db.query(CourseSection).filter(CourseSection.id == section_id).first()
    if not section:
        raise ValueError(f"Section with ID {section_id} not found")
    
    # Check if card exists
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise ValueError(f"Card with ID {card_id} not found")
    
    # Check if association already exists
    existing = db.query(section_cards).filter(
        section_cards.c.section_id == section_id,
        section_cards.c.card_id == card_id
    ).first()
    
    if existing:
        # Update order index if association exists
        db.execute(
            section_cards.update().where(
                section_cards.c.section_id == section_id,
                section_cards.c.card_id == card_id
            ).values(order_index=order_index)
        )
    else:
        # Create new association
        db.execute(
            section_cards.insert().values(
                section_id=section_id,
                card_id=card_id,
                order_index=order_index
            )
        )
    
    db.commit()
    
    return None

def create_section(db: Session, section_data: SectionCreate) -> CourseSection:
    """
    Create a new course section
    
    Args:
        db: Database session
        section_data: Pydantic model containing section data
        
    Returns:
        The created CourseSection object
    """
    # Create section object from Pydantic model attributes
    db_section = CourseSection(
        title=section_data.title,
        description=section_data.description,
        order_index=section_data.order_index if section_data.order_index is not None else 0,
        # estimated_days=section_data.estimated_days,
        is_template=True
    )
    
    db.add(db_section)
    db.commit()
    db.refresh(db_section)
    
    return db_section

# Update the progress of a user section
def update_user_section_progress(db: Session, user_id: int, section_id: int, progress: float) -> UserSection:
    """
    Update the progress of a user's section
    
    Args:
        db: Database session
        user_id: User ID
        section_id: Section ID
        progress: Progress value (0.0 to 100.0)
    
    Returns:
        Updated UserSection object
    """
    section = db.query(UserSection).filter(
        UserSection.id == section_id,
        UserSection.user_id == user_id
    ).first()
    
    if not section:
        raise ValueError(f"Section with ID {section_id} not found for user {user_id}")
    
    # Ensure progress is within valid range
    progress = max(0.0, min(100.0, progress))
    section.progress = progress
    
    db.commit()
    db.refresh(section)
    return section

# Utility function to format a UserSection with cards for response
def format_user_section_for_response(db: Session, user_section: UserSection) -> Dict[str, Any]:
    if not user_section:
        return {} 

    card_associations = db.query(
        Card,
        user_section_cards.c.order_index,
        user_section_cards.c.is_custom
    ).join(
        user_section_cards, user_section_cards.c.card_id == Card.id
    ).filter(
        user_section_cards.c.user_section_id == user_section.id
    ).order_by(user_section_cards.c.order_index).all()

    cards_for_response = []
    card_ids_in_section = [card.id for card, _, _ in card_associations]
    
    user_card_completion_map = {}
    if card_ids_in_section: # Only query if there are cards
        user_card_statuses = db.query(
            user_section_cards.c.card_id,
            user_section_cards.c.is_completed
        ).filter(
            user_section_cards.c.user_section_id == user_section.id,
            user_section_cards.c.card_id.in_(card_ids_in_section)
        ).all()
        user_card_completion_map = {card_id: is_completed for card_id, is_completed in user_card_statuses}

    for card, order_index, is_custom in card_associations:
        is_completed_status = user_card_completion_map.get(card.id, False) # Default to False if not found
        cards_for_response.append({
            "card": CardResponse.model_validate(card).model_dump(), 
            "order_index": order_index,
            "is_custom": is_custom,
            "is_completed": is_completed_status # ADDED is_completed status
        })
    
    section_order_index = 0 
    if user_section.section_template_id:
        # template_order_index = db.query(CourseSection.order_index).filter(CourseSection.id == user_section.section_template_id).scalar_one_or_none()
        # Compatibility fix for older SQLAlchemy if scalar_one_or_none() is not available:p
        result = db.query(CourseSection.order_index).filter(CourseSection.id == user_section.section_template_id).first()
        template_order_index = result[0] if result else None
        if template_order_index is not None:
            section_order_index = template_order_index

    return {
        "id": user_section.id,
        "user_id": user_section.user_id,
        "section_template_id": user_section.section_template_id,
        "title": user_section.title,
        "description": user_section.description,
        "progress": user_section.progress,
        "created_at": user_section.created_at.isoformat() if user_section.created_at else None,
        "updated_at": user_section.updated_at.isoformat() if user_section.updated_at else None,
        "order_index": section_order_index, 
        "cards": cards_for_response
    }

# Add a function to find a user section by either direct ID or template section ID
def find_user_section(db: Session, user_id: int, section_id: int) -> Optional[UserSection]:
    """
    Find a user section by either its ID or by template section ID.
    This helps handle cases where UserSection IDs don't match template section IDs.
    
    Args:
        db: Database session
        user_id: User ID
        section_id: Section ID to look up (could be UserSection ID or CourseSection ID)
        
    Returns:
        UserSection object if found, None otherwise
    """
    # First try to find by direct ID match (most efficient)
    user_section = get_user_section(db, user_id=user_id, section_id=section_id)
    
    # If not found, try to find by template section ID
    if not user_section:
        user_section = db.query(UserSection).filter(
            UserSection.user_id == user_id,
            UserSection.section_template_id == section_id
        ).first()
        
        if user_section:
            logging.info(f"Found UserSection {user_section.id} by template section ID {section_id}")
    
    return user_section 