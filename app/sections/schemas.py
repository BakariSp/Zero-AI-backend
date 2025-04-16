from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

# 基础卡片模式
class CardBase(BaseModel):
    keyword: str
    explanation: Optional[str] = None
    resources: Optional[Dict[str, Any]] = None
    level: Optional[str] = None
    tags: Optional[List[str]] = None

class CardResponse(CardBase):
    id: int
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

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

# 系统模板章节响应
class SectionResponse(SectionBase):
    id: int
    learning_path_id: Optional[int] = None
    order_index: Optional[int] = None
    estimated_days: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    is_template: bool = True
    cards: Optional[List[CardInSection]] = None

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