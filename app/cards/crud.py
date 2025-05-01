from sqlalchemy.orm import Session
from sqlalchemy import func, select, update, insert, text
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
import logging

from app.models import Card, User, CourseSection, section_cards, LearningPath, UserLearningPath
from app.cards.schemas import CardCreate, CardUpdate
from app.users.crud import check_subscription_limits
from app.models import user_cards
from app.user_daily_usage.crud import increment_usage

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
        # Create card with all fields from CardCreate model
        db_card = Card(
            keyword=card_data.keyword,
            question=card_data.question,
            answer=card_data.answer,
            explanation=card_data.explanation,
            difficulty=card_data.difficulty,
            resources=card_data.resources,
            created_by=card_data.created_by,
            level=card_data.level,
            tags=card_data.tags
        )

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
    
    # Check if user has reached their subscription limit for cards
    has_reached_limit, remaining = check_subscription_limits(db, user_id, 'cards')
    if has_reached_limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You have reached your subscription limit for saved cards. "
                   f"Please upgrade your subscription to save more cards."
        )
    
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
    
    # Increment the daily usage count for cards
    try:
        # This will increment the cards_generated count and check daily limits
        increment_usage(db, user_id, "cards")
        logging.info(f"Incremented daily card usage for user {user_id}")
    except Exception as e:
        logging.error(f"Error incrementing card usage for user {user_id}: {str(e)}")
        # We don't want to fail the operation if the usage tracking fails
        # The card was already saved, so we'll continue
    
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

def remove_card_from_user_learning_path(db: Session, user_id: int, card_id: int, section_id: Optional[int] = None) -> bool:
    """
    Remove a card from sections in a user's learning path.
    If section_id is provided, only removes from that specific section.
    Otherwise, removes from all sections in user's learning paths.
    
    If the card is only associated with this user's sections and not with any other users or sections,
    the card will be completely deleted from the database.
    """
    import logging
    
    # First, verify the card exists
    card = get_card(db, card_id=card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    
    # Record the sections to remove the card from
    sections_to_remove_from = []
    
    if section_id:
        # Check if section exists in one of the user's learning paths
        section_query = db.query(CourseSection).join(
            LearningPath, CourseSection.learning_path_id == LearningPath.id
        ).join(
            UserLearningPath, UserLearningPath.learning_path_id == LearningPath.id
        ).filter(
            CourseSection.id == section_id,
            UserLearningPath.user_id == user_id
        )
        
        if db.query(section_query.exists()).scalar() is False:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Section not found or not accessible by user"
            )
        
        sections_to_remove_from = [section_id]
    else:
        # Get all section IDs from the user's learning paths
        user_section_ids = db.query(CourseSection.id).join(
            LearningPath, CourseSection.learning_path_id == LearningPath.id
        ).join(
            UserLearningPath, UserLearningPath.learning_path_id == LearningPath.id
        ).filter(
            UserLearningPath.user_id == user_id
        ).all()
        
        # Extract IDs from the result
        sections_to_remove_from = [section_id for (section_id,) in user_section_ids]
    
    # Remove the section-card associations
    if sections_to_remove_from:
        logging.info(f"Removing card {card_id} from sections: {sections_to_remove_from}")
        db.execute(
            section_cards.delete().where(
                section_cards.c.section_id.in_(sections_to_remove_from),
                section_cards.c.card_id == card_id
            )
        )
    
    # Check if this card is associated with any other sections
    other_section_count = db.query(section_cards).filter(
        section_cards.c.card_id == card_id
    ).count()
    
    # Check if this card is saved by any users
    saved_by_users_count = db.query(user_cards).filter(
        user_cards.c.card_id == card_id
    ).count()
    
    # If the card is not associated with any other sections or users, delete it completely
    if other_section_count == 0 and saved_by_users_count == 0:
        logging.info(f"Card {card_id} is not used elsewhere, deleting completely")
        db.query(Card).filter(Card.id == card_id).delete()
        logging.info(f"Card {card_id} deleted from the database")
    else:
        logging.info(f"Card {card_id} is still used in {other_section_count} sections and saved by {saved_by_users_count} users")
    
    db.commit()
    return True

def link_card_to_section(db: Session, card_id: int, section_id: int):
    """
    Links a card to a section by creating an entry in the section_cards association table.
    Uses the section_cards table defined in app.models.
    """
    # Import the section_cards association table
    from app.models import section_cards
    from sqlalchemy import text

    # Check if link already exists
    exists = db.execute(
        text("SELECT 1 FROM section_cards WHERE section_id = :section_id AND card_id = :card_id"),
        {"section_id": section_id, "card_id": card_id}
    ).fetchone()

    if not exists:
        # Get the next order index
        next_order = _get_next_card_order_in_section(db, section_id)
        
        # Add the association
        db.execute(
            text("INSERT INTO section_cards (section_id, card_id, order_index) VALUES (:section_id, :card_id, :order_index)"),
            {"section_id": section_id, "card_id": card_id, "order_index": next_order}
        )
        db.commit()
        logging.info(f"Linked card {card_id} to section {section_id} with order_index {next_order}.")
    else:
        logging.info(f"Card {card_id} already linked to section {section_id}.") 