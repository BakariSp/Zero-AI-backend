from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.cards.schemas import CardResponse, CardBase, Resource


# 章节中的卡片
class CardInSection(BaseModel):
    card: CardResponse
    order_index: int
    is_custom: Optional[bool] = False

# 添加卡片到章节
class CardInSectionCreate(BaseModel):
    card_id: int
    order_index: int
    is_custom: Optional[bool] = False

# 更新章节中的卡片
class CardInSectionUpdate(BaseModel):
    order_index: int

# 基础章节模式
class SectionBase(BaseModel):
    title: str
    description: Optional[str] = None
    order_index: int

class SectionCreate(SectionBase):
    pass # Inherits fields from SectionBase

class Section(SectionBase):
    id: int
    course_id: int # Assuming a section belongs to a course

    class Config:
        orm_mode = True # or from_attributes = True for Pydantic v2

# 系统模板章节响应
class SectionCardResponse(BaseModel):
    order_index: int
    card: CardResponse

    class Config:
        from_attributes = True

class SectionResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    order_index: int
    cards: List[CardResponse] = []
    learning_path_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# 用户自定义章节创建
class UserSectionCreate(SectionBase):
    section_template_id: Optional[int] = None  # 如果基于模板创建，则提供模板ID

# 用户自定义章节更新
class UserSectionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

# 用户自定义章节响应
class UserSectionResponse(SectionBase):
    id: int
    user_id: int
    section_template_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    cards: Optional[List[CardInSection]] = None

    class Config:
        from_attributes = True 