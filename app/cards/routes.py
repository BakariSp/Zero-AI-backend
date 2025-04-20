from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.db import SessionLocal
from app.auth.jwt import get_current_active_user
from app.models import User, Card
from app.cards.schemas import (
    CardCreate,
    CardResponse,
    CardUpdate,
    UserCardCreate,
    UserCardResponse,
    UserCardUpdate,
    GenerateCardRequest
)
from app.cards.crud import (
    get_card,
    get_cards,
    get_card_by_keyword,
    create_card,
    update_card,
    delete_card,
    get_section_cards,
    get_user_saved_cards,
    save_card_for_user,
    update_user_card,
    remove_card_from_user
)
from app.services.ai_generator import (
    generate_card_with_ai,
    get_card_generator_agent
)

router = APIRouter()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/cards", response_model=List[CardResponse])
def read_cards(
    skip: int = 0,
    limit: int = 100,
    keyword: Optional[str] = None,
    section_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all cards with optional filters"""
    cards = get_cards(
        db, 
        skip=skip, 
        limit=limit, 
        keyword=keyword,
        section_id=section_id
    )
    return cards

@router.get("/cards/{card_id}", response_model=CardResponse)
def read_card(
    card_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific card by ID"""
    card = get_card(db, card_id=card_id)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    return card

@router.post("/cards", response_model=CardResponse)
def create_new_card(
    card: CardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new card (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return create_card(db=db, card_data=card)

@router.put("/cards/{card_id}", response_model=CardResponse)
def update_existing_card(
    card_id: int,
    card: CardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update an existing card (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return update_card(
        db=db, 
        card_id=card_id, 
        card_data=card.dict(exclude_unset=True)
    )

@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_card(
    card_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a card (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    delete_card(db=db, card_id=card_id)
    return {"detail": "Card deleted successfully"}

@router.get("/sections/{section_id}/cards", response_model=List[CardResponse])
def read_section_cards(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all cards for a specific course section"""
    cards = get_section_cards(db, section_id=section_id)
    return cards

@router.get("/users/me/cards", response_model=List[UserCardResponse])
def read_user_saved_cards(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all cards saved by the current user"""
    user_cards = get_user_saved_cards(db, user_id=current_user.id)
    return user_cards

@router.post("/users/me/cards", response_model=UserCardResponse)
def save_card(
    user_card: UserCardCreate,
    expanded_example: Optional[str] = None,
    difficulty_rating: Optional[int] = None,
    depth_preference: Optional[str] = None,
    recommended_by: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Save a card for the current user"""
    return save_card_for_user(
        db=db, 
        user_id=current_user.id, 
        card_id=user_card.card_id,
        expanded_example=expanded_example,
        difficulty_rating=difficulty_rating,
        depth_preference=depth_preference,
        recommended_by=recommended_by
    )

@router.put("/users/me/cards/{card_id}", response_model=UserCardResponse)
def update_saved_card(
    card_id: int,
    user_card: UserCardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update a saved card for the current user"""
    return update_user_card(
        db=db,
        user_id=current_user.id,
        card_id=card_id,
        is_completed=user_card.is_completed,
        expanded_example=user_card.expanded_example,
        notes=user_card.notes,
        difficulty_rating=user_card.difficulty_rating,
        depth_preference=user_card.depth_preference
    )

@router.delete("/users/me/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_saved_card(
    card_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Remove a saved card for the current user"""
    remove_card_from_user(db=db, user_id=current_user.id, card_id=card_id)
    return {"detail": "Card removed successfully"}

@router.post("/generate-card", response_model=CardResponse)
async def generate_ai_card(
    request: GenerateCardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Generate a card using AI based on a keyword, potentially linking to a section."""
    try:
        # Check if card with this keyword already exists
        # Note: create_card in crud.py now handles checking existence and linking
        # existing_card = get_card_by_keyword(db, request.keyword)
        # if existing_card:
        #     logging.info(f"Card with keyword '{request.keyword}' already exists (ID: {existing_card.id}). Will link if section provided.")
            # The create_card function will handle returning the existing card
            # and linking it to the section if necessary.

        # --- Option 1: Use legacy wrapper (if updated correctly) ---
        # card_data: CardCreate = await generate_card_with_ai(
        #     keyword=request.keyword,
        #     context=request.context,
        #     # Pass section/course/difficulty if available in request or defaults
        #     section_title=None, # Example: Get from request if needed
        #     course_title=None,  # Example: Get from request if needed
        #     difficulty="intermediate" # Example: Get from request or default
        # )

        # --- Option 2: Get agent instance and call method (Preferred) ---
        try:
            card_generator = get_card_generator_agent()
        except RuntimeError as e:
             raise HTTPException(status_code=503, detail=f"AI Service Unavailable: {e}")

        card_data: CardCreate = await card_generator.generate_card(
             keyword=request.keyword,
             context=request.context,
             # Pass section/course/difficulty if available in request or defaults
             section_title=None, # Example: Get from request if needed
             course_title=None,  # Example: Get from request if needed
             difficulty="intermediate" # Example: Get from request or default
        )
        # --- End Option 2 ---


        # Create the card in the database, passing section_id for linking
        # The crud function handles checking for duplicates and linking
        card = create_card(db=db, card_data=card_data, section_id=request.section_id)

        # Return using CardResponse schema
        return CardResponse.from_orm(card) # Use from_orm for Pydantic v2+

    except ValueError as ve:
         # Catch specific errors like JSON parsing or missing fields from AI
         logging.error(f"Value error during AI card generation: {ve}", exc_info=True)
         raise HTTPException(
             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, # 422 or 500 depending on context
             detail=f"Failed to process AI response: {str(ve)}"
         )
    except RuntimeError as rte:
         # Catch agent initialization errors
         logging.error(f"Runtime error during AI card generation: {rte}", exc_info=True)
         raise HTTPException(
             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
             detail=f"AI Service Unavailable: {str(rte)}"
         )
    except Exception as e:
        logging.error(f"Unexpected error generating card: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate card: {str(e)}"
        ) 