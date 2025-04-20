from sqlalchemy.orm import Session
from sqlalchemy import func, select, update, insert
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
import logging

from app.models import Card, User, CourseSection, section_cards
from app.cards.schemas import CardCreate, CardUpdate

# Helper function to get the next order index
def _get_next_card_order_in_section(db: Session, section_id: int) -> int:
    max_order = db.execute(
        select(func.max(section_cards.c.order_index))
        .where(section_cards.c.section_id == section_id)
    ).scalar()
    return (max_order or 0) + 1

def get_card(db: Session, card_id: int) -> Optional[Card]:
    return db.query(Card).filter(Card.id == card_id).first()

def get_cards(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    keyword: Optional[str] = None,
    section_id: Optional[int] = None
) -> List[Card]:
    query = db.query(Card)
    
    if keyword:
        query = query.filter(Card.keyword.ilike(f"%{keyword}%"))
    
    if section_id:
        query = query.join(section_cards).filter(section_cards.c.section_id == section_id)
    
    return query.offset(skip).limit(limit).all()

def get_card_by_keyword(db: Session, keyword: str) -> Optional[Card]:
    return db.query(Card).filter(Card.keyword.ilike(keyword)).first()

def create_card(db: Session, card_data: CardCreate, section_id: Optional[int] = None, owner_id: Optional[int] = None) -> Card:
    """
    Creates a new card in the database or returns an existing one based on keyword.
    Links the card to a section if section_id is provided.
    """
    # Check if a card with the same keyword already exists
    existing_card = db.query(Card).filter(Card.keyword == card_data.keyword).first()

    if existing_card:
        logging.info(f"Card with keyword '{card_data.keyword}' already exists (ID: {existing_card.id}).")
        # Link to section if section_id is provided and not already linked
        if section_id:
            link_card_to_section(db, card_id=existing_card.id, section_id=section_id)
        return existing_card
    else:
        logging.info(f"Creating new card with keyword '{card_data.keyword}'.")
        # --- FIX: Use direct field names from CardCreate ---
        db_card = Card(
            keyword=card_data.keyword,
            question=card_data.question,      # Use question directly
            answer=card_data.answer,        # Use answer directly
            explanation=card_data.explanation, # Use explanation directly
            difficulty=card_data.difficulty
            # owner_id=owner_id             # Removed owner_id assignment
            # Add any other necessary fields from your Card model
        )
        # --- END FIX ---

        db.add(db_card)
        db.commit()
        db.refresh(db_card)

        # Link to section if section_id is provided
        if section_id:
            link_card_to_section(db, card_id=db_card.id, section_id=section_id)

        return db_card

def update_card(db: Session, card_id: int, card_data: Dict[str, Any]) -> Card:
    db_card = get_card(db, card_id)
    if not db_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    
    for key, value in card_data.items():
        setattr(db_card, key, value)
    
    db.commit()
    db.refresh(db_card)
    return db_card

def delete_card(db: Session, card_id: int) -> bool:
    db_card = get_card(db, card_id)
    if not db_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    
    db.delete(db_card)
    db.commit()
    return True

def get_section_cards(db: Session, section_id: int) -> List[Card]:
    """Get all cards associated with a specific course section"""
    section = db.query(CourseSection).filter(CourseSection.id == section_id).first()
    if not section:
        # It's good practice to handle the case where the section doesn't exist.
        # You could raise an HTTPException here, or let the route handle it.
        # Returning an empty list might also be valid depending on requirements.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section with id {section_id} not found"
        )
    # Access the 'cards' relationship defined in the CourseSection model
    return section.cards

def get_user_saved_cards(db: Session, user_id: int) -> List[Dict[str, Any]]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get all cards saved by the user with additional info from the association table
    result = []
    for card_assoc in db.query(User.saved_cards).filter(User.id == user_id).all():
        for card in card_assoc:
            # Get the association data
            assoc_data = db.execute(
                """
                SELECT is_completed, expanded_example, notes, saved_at,
                       difficulty_rating, depth_preference, recommended_by
                FROM user_cards 
                WHERE user_id = :user_id AND card_id = :card_id
                """,
                {"user_id": user_id, "card_id": card.id}
            ).fetchone()
            
            card_data = {
                "card": card,
                "is_completed": assoc_data.is_completed,
                "expanded_example": assoc_data.expanded_example,
                "notes": assoc_data.notes,
                "saved_at": assoc_data.saved_at,
                "difficulty_rating": assoc_data.difficulty_rating,
                "depth_preference": assoc_data.depth_preference,
                "recommended_by": assoc_data.recommended_by
            }
            result.append(card_data)
    
    return result

def save_card_for_user(
    db: Session, 
    user_id: int, 
    card_id: int,
    expanded_example: Optional[str] = None,
    difficulty_rating: Optional[int] = None,
    depth_preference: Optional[str] = None,
    recommended_by: Optional[str] = None
) -> Dict[str, Any]:
    # Check if card exists
    card = get_card(db, card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if card is already saved by user
    is_saved = db.execute(
        """
        SELECT 1 FROM user_cards 
        WHERE user_id = :user_id AND card_id = :card_id
        """,
        {"user_id": user_id, "card_id": card_id}
    ).fetchone()
    
    if is_saved:
        # Card is already saved, return existing data
        assoc_data = db.execute(
            """
            SELECT is_completed, expanded_example, notes, saved_at, 
                   difficulty_rating, depth_preference, recommended_by
            FROM user_cards 
            WHERE user_id = :user_id AND card_id = :card_id
            """,
            {"user_id": user_id, "card_id": card_id}
        ).fetchone()
        
        return {
            "card": card,
            "is_completed": assoc_data.is_completed,
            "expanded_example": assoc_data.expanded_example,
            "notes": assoc_data.notes,
            "saved_at": assoc_data.saved_at,
            "difficulty_rating": assoc_data.difficulty_rating,
            "depth_preference": assoc_data.depth_preference,
            "recommended_by": assoc_data.recommended_by
        }
    
    # Save card for user
    db.execute(
        """
        INSERT INTO user_cards (
            user_id, card_id, is_completed, expanded_example, notes, saved_at,
            difficulty_rating, depth_preference, recommended_by
        )
        VALUES (
            :user_id, :card_id, :is_completed, :expanded_example, :notes, :saved_at,
            :difficulty_rating, :depth_preference, :recommended_by
        )
        """,
        {
            "user_id": user_id, 
            "card_id": card_id,
            "is_completed": False,
            "expanded_example": expanded_example,
            "notes": None,
            "saved_at": func.now(),
            "difficulty_rating": difficulty_rating,
            "depth_preference": depth_preference,
            "recommended_by": recommended_by
        }
    )
    db.commit()
    
    # Get the newly created association
    assoc_data = db.execute(
        """
        SELECT is_completed, expanded_example, notes, saved_at,
               difficulty_rating, depth_preference, recommended_by
        FROM user_cards 
        WHERE user_id = :user_id AND card_id = :card_id
        """,
        {"user_id": user_id, "card_id": card_id}
    ).fetchone()
    
    return {
        "card": card,
        "is_completed": assoc_data.is_completed,
        "expanded_example": assoc_data.expanded_example,
        "notes": assoc_data.notes,
        "saved_at": assoc_data.saved_at,
        "difficulty_rating": assoc_data.difficulty_rating,
        "depth_preference": assoc_data.depth_preference,
        "recommended_by": assoc_data.recommended_by
    }

def update_user_card(
    db: Session,
    user_id: int,
    card_id: int,
    is_completed: Optional[bool] = None,
    expanded_example: Optional[str] = None,
    notes: Optional[str] = None,
    difficulty_rating: Optional[int] = None,
    depth_preference: Optional[str] = None
) -> Dict[str, Any]:
    # Check if card is saved by user
    is_saved = db.execute(
        """
        SELECT 1 FROM user_cards 
        WHERE user_id = :user_id AND card_id = :card_id
        """,
        {"user_id": user_id, "card_id": card_id}
    ).fetchone()
    
    if not is_saved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not saved by user"
        )
    
    # Update the association
    update_dict = {}
    if is_completed is not None:
        update_dict["is_completed"] = is_completed
    if expanded_example is not None:
        update_dict["expanded_example"] = expanded_example
    if notes is not None:
        update_dict["notes"] = notes
    if difficulty_rating is not None:
        update_dict["difficulty_rating"] = difficulty_rating
    if depth_preference is not None:
        update_dict["depth_preference"] = depth_preference
    
    if update_dict:
        update_str = ", ".join([f"{k} = :{k}" for k in update_dict.keys()])
        update_dict.update({"user_id": user_id, "card_id": card_id})
        
        db.execute(
            f"""
            UPDATE user_cards 
            SET {update_str}
            WHERE user_id = :user_id AND card_id = :card_id
            """,
            update_dict
        )
        db.commit()
    
    # Get the updated association
    card = get_card(db, card_id)
    assoc_data = db.execute(
        """
        SELECT is_completed, expanded_example, notes, saved_at,
               difficulty_rating, depth_preference, recommended_by
        FROM user_cards 
        WHERE user_id = :user_id AND card_id = :card_id
        """,
        {"user_id": user_id, "card_id": card_id}
    ).fetchone()
    
    return {
        "card": card,
        "is_completed": assoc_data.is_completed,
        "expanded_example": assoc_data.expanded_example,
        "notes": assoc_data.notes,
        "saved_at": assoc_data.saved_at,
        "difficulty_rating": assoc_data.difficulty_rating,
        "depth_preference": assoc_data.depth_preference,
        "recommended_by": assoc_data.recommended_by
    }

def remove_card_from_user(db: Session, user_id: int, card_id: int) -> bool:
    # Check if card is saved by user
    is_saved = db.execute(
        """
        SELECT 1 FROM user_cards 
        WHERE user_id = :user_id AND card_id = :card_id
        """,
        {"user_id": user_id, "card_id": card_id}
    ).fetchone()
    
    if not is_saved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not saved by user"
        )
    
    # Remove the association
    db.execute(
        """
        DELETE FROM user_cards 
        WHERE user_id = :user_id AND card_id = :card_id
        """,
        {"user_id": user_id, "card_id": card_id}
    )
    db.commit()
    
    return True

# You might need a helper function like this (adapt to your models)
# def get_next_card_order_in_section(db: Session, section_id: int) -> int:
#    max_order = db.query(func.max(card_section.c.order_index))\
#                  .filter(card_section.c.section_id == section_id)\
#                  .scalar()
#    return (max_order or 0) + 1 

# Add the link_card_to_section function if it doesn't exist or is elsewhere
# (Assuming you have a SectionCardLink association table/model)
def link_card_to_section(db: Session, card_id: int, section_id: int):
    from app.models.associations import SectionCardLink # Adjust import as needed

    # Check if the link already exists
    exists = db.query(SectionCardLink).filter_by(section_id=section_id, card_id=card_id).first()
    if not exists:
        link = SectionCardLink(section_id=section_id, card_id=card_id)
        db.add(link)
        db.commit()
        logging.info(f"Linked card {card_id} to section {section_id}.")
    else:
        logging.info(f"Card {card_id} already linked to section {section_id}.") 