from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status

from app.models import Card, User, CourseSection
from app.cards.schemas import CardCreate, CardUpdate

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
        query = query.filter(Card.section_id == section_id)
    
    return query.offset(skip).limit(limit).all()

def get_card_by_keyword(db: Session, keyword: str) -> Optional[Card]:
    return db.query(Card).filter(func.lower(Card.keyword) == func.lower(keyword)).first()

def create_card(db: Session, card_data: CardCreate) -> Card:
    # Check if card with this keyword already exists
    existing_card = get_card_by_keyword(db, card_data.keyword)
    if existing_card:
        return existing_card
    
    # Create new card
    db_card = Card(**card_data.dict())
    db.add(db_card)
    db.commit()
    db.refresh(db_card)
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
    return db.query(Card).filter(Card.section_id == section_id).all()

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