from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import CourseSection, UserSection, Card, section_cards, user_section_cards
from app.sections.schemas import UserSectionCreate, UserSectionUpdate
from typing import List, Optional, Dict, Any

# 获取系统模板章节列表
def get_sections(db: Session, skip: int = 0, limit: int = 100) -> List[CourseSection]:
    return db.query(CourseSection).filter(CourseSection.is_template == True).offset(skip).limit(limit).all()

# 获取单个系统模板章节
def get_section(db: Session, section_id: int) -> Optional[CourseSection]:
    return db.query(CourseSection).filter(CourseSection.id == section_id, CourseSection.is_template == True).first()

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

def create_section(db: Session, section_data: Dict[str, Any]) -> CourseSection:
    """
    Create a new course section
    
    Args:
        db: Database session
        section_data: Dictionary containing section data (title, description, etc.)
        
    Returns:
        The created CourseSection object
    """
    # Create section object from data
    db_section = CourseSection(
        title=section_data.get("title"),
        description=section_data.get("description"),
        order_index=section_data.get("order_index", 0),
        estimated_days=section_data.get("estimated_days"),
        is_template=True
    )
    
    db.add(db_section)
    db.commit()
    db.refresh(db_section)
    
    return db_section 