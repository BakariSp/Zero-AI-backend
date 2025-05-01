from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db import get_db
from app.services.learning_assistant_service import LearningAssistantService
from app.auth.jwt import get_current_user_optional

router = APIRouter(
    prefix="/learning-assistant",
    tags=["learning-assistant"],
    responses={404: {"description": "Not found"}},
)

# Initialize the service
learning_assistant_service = LearningAssistantService()

# Request models
class QuestionRequest(BaseModel):
    query: str
    card_id: Optional[int] = None
    section_id: Optional[int] = None
    difficulty_level: Optional[str] = "intermediate"

class AddCardRequest(BaseModel):
    card_data: Dict[str, Any]
    section_id: int

class GenerateCardsRequest(BaseModel):
    topic: str
    num_cards: Optional[int] = 3
    section_id: Optional[int] = None
    course_title: Optional[str] = None
    difficulty_level: Optional[str] = "intermediate"

@router.post("/ask", response_model=Dict[str, Any])
async def ask_question(
    request: QuestionRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional)
):
    """
    Process a learning question from a user and return an answer with a related card
    """
    try:
        user_id = current_user.id if current_user else None
        
        result = await learning_assistant_service.process_learning_question(
            db=db,
            user_query=request.query,
            card_id=request.card_id,
            section_id=request.section_id,
            difficulty_level=request.difficulty_level
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add-card", response_model=Dict[str, Any])
async def add_card_to_section(
    request: AddCardRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional)
):
    """
    Add a generated card to a section
    """
    try:
        user_id = current_user.id if current_user else None
        
        result = await learning_assistant_service.add_related_card_to_section(
            db=db,
            card_data=request.card_data,
            section_id=request.section_id,
            user_id=user_id
        )
        
        return result
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-cards", response_model=List[Dict[str, Any]])
async def generate_cards(
    request: GenerateCardsRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional)
):
    """
    Generate multiple cards for a specific topic
    """
    try:
        user_id = current_user.id if current_user else None
        
        cards = await learning_assistant_service.generate_cards_for_topic(
            topic=request.topic,
            num_cards=request.num_cards,
            section_id=request.section_id,
            course_title=request.course_title,
            difficulty_level=request.difficulty_level,
            user_id=user_id,
            db=db
        )
        
        return cards
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 