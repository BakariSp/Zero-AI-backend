from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from sqlalchemy.sql import text

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
    remove_card_from_user,
    remove_card_from_user_learning_path
)
from app.services.ai_generator import (
    generate_card_with_ai,
    get_card_generator_agent
)
from app.setup import increment_user_resource_usage, get_user_remaining_resources

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
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
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
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
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
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
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

@router.delete("/users/me/learning-paths/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_card_from_learning_path(
    card_id: int,
    section_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Remove a card from a section in the user's learning path.
    This doesn't delete the card entirely, just removes the association with the section.
    """
    try:
        # Check if the request has the correct authentication
        if current_user is None:
            logging.error(f"No user found for card deletion: card_id={card_id}, section_id={section_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        logging.info(f"User {current_user.id} is deleting card {card_id} from section {section_id}")
        remove_card_from_user_learning_path(db, user_id=current_user.id, card_id=card_id, section_id=section_id)
        return {"detail": "Card removed from learning path successfully"}
    except HTTPException as e:
        # Re-raise HTTP exceptions
        logging.error(f"HTTP exception during card deletion: {e.detail}")
        raise e
    except Exception as e:
        # Log any unexpected errors
        logging.error(f"Error removing card {card_id} from learning path: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove card: {str(e)}"
        )

# Add a duplicate route for the path that's actually being used by the frontend
# This ensures backward compatibility
@router.delete("/learning-paths/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_card_from_learning_path_alt_path(
    card_id: int,
    section_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Alternative path for removing a card from a learning path.
    This is a duplicate of the above endpoint to handle a different URL pattern.
    """
    try:
        # Check if the request has the correct authentication
        if current_user is None:
            logging.error(f"No user found for card deletion (alt path): card_id={card_id}, section_id={section_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        logging.info(f"User {current_user.id} is deleting card {card_id} from section {section_id} (alt path)")
        remove_card_from_user_learning_path(db, user_id=current_user.id, card_id=card_id, section_id=section_id)
        return {"detail": "Card removed from learning path successfully"}
    except HTTPException as e:
        # Re-raise HTTP exceptions
        logging.error(f"HTTP exception during card deletion (alt path): {e.detail}")
        raise e
    except Exception as e:
        # Log any unexpected errors
        logging.error(f"Error removing card {card_id} from learning path (alt path): {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove card: {str(e)}"
        )

@router.post("/generate-card", response_model=CardResponse)
async def generate_ai_card(
    request: GenerateCardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Generate a card using AI based on a keyword, potentially linking to a section."""
    try:
        # Check user's daily usage limit for cards
        resources = get_user_remaining_resources(db, current_user.id)
        
        # Check if user has reached their daily limit
        if resources["cards"]["remaining"] <= 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Daily limit reached for cards. Your limit is {resources['cards']['limit']} cards per day."
            )
        
        # Get agent instance and call method (Preferred)
        try:
            card_generator = get_card_generator_agent()
        except RuntimeError as e:
             raise HTTPException(status_code=503, detail=f"AI Service Unavailable: {e}")

        card_data: CardCreate = await card_generator.generate_card(
             keyword=request.keyword,
             context=request.context,
             # Pass titles and difficulty from the request
             section_title=request.section_title,
             course_title=request.course_title,
             difficulty=request.difficulty or "intermediate" # Use request difficulty or default
        )

        # Create the card in the database, passing section_id for linking
        # The crud function handles checking for duplicates and linking
        card = create_card(db=db, card_data=card_data, section_id=request.section_id)
        
        # Increment user's daily usage for cards
        increment_user_resource_usage(db, current_user.id, "cards")

        # Return using CardResponse schema
        return CardResponse.from_orm(card) # Use from_orm for Pydantic v2+
        
    except Exception as e:
        logging.error(f"Error generating card: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate card: {str(e)}"
        ) 