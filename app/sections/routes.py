from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

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
    CardInSectionUpdate
)

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
