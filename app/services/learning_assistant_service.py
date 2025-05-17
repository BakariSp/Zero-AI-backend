from typing import Dict, List, Any, Optional
import logging
from fastapi import HTTPException

from app.services.ai_generator import (
    get_learning_assistant_agent, 
    LearningAssistantAgent,
    CardCreate
)
from app.cards.schemas import CardCreate as CardCreateSchema
from app.cards.crud import create_card, get_card
from app.sections.crud import get_section
from app.user_daily_usage.crud import increment_usage
from sqlalchemy import func
from sqlalchemy.sql import text
from app.models import UserSection, user_section_cards

class LearningAssistantService:
    """
    Service to handle user questions during learning and generate related cards
    """

    def __init__(self):
        try:
            # Get the learning assistant agent
            self.agent = get_learning_assistant_agent()
            logging.info("Successfully initialized LearningAssistantService")
        except Exception as e:
            logging.error(f"Failed to initialize LearningAssistantService: {e}")
            self.agent = None

    async def process_learning_question(
        self,
        db,  # Database session
        user_query: str,
        card_id: Optional[int] = None,
        section_id: Optional[int] = None,
        difficulty_level: str = "intermediate",
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process a user question during learning, retrieve context, and generate response with related card
        
        Args:
            db: Database session
            user_query: User's question or prompt
            card_id: ID of the card the user is currently viewing
            section_id: ID of the section the user is currently in
            difficulty_level: Desired difficulty level
            user_id: ID of the current user (optional)
            
        Returns:
            Dict with answer, related card, and status information
        """
        try:
            if not self.agent:
                raise RuntimeError("LearningAssistantAgent not initialized. Check Azure OpenAI configuration.")
            
            # Gather context information
            current_card_data = None
            section_title = None
            course_title = None
            
            # Get card data if card_id is provided
            if card_id:
                card_db = get_card(db, card_id)
                if card_db:
                    current_card_data = {
                        "id": card_db.id,
                        "keyword": card_db.keyword,
                        "question": card_db.question, 
                        "answer": card_db.answer,
                        "explanation": card_db.explanation,
                        "difficulty": card_db.difficulty
                    }
                    
                    # Get section info if the card has sections and no section_id was provided
                    if not section_id and hasattr(card_db, 'sections') and card_db.sections:
                        # Get the first section for simplicity
                        section_id = card_db.sections[0].id
            
            # Get section and course titles if section_id is provided
            if section_id:
                section_db = get_section(db, section_id)
                if section_db:
                    section_title = section_db.title
                    
                    # Get course title if the section has a course
                    if section_db.courses and len(section_db.courses) > 0:
                        course_title = section_db.courses[0].title
            
            # Process the question using the agent
            response = await self.agent.answer_question(
                user_query=user_query,
                current_card_data=current_card_data,
                section_title=section_title,
                course_title=course_title,
                difficulty_level=difficulty_level
            )
            
            # If a related card was generated and there's a user, increment their card usage
            # This ensures we count card generation even if it's not added to a section yet
            if response.get("related_card") and user_id:
                try:
                    # Increment the user's daily usage for cards
                    increment_usage(db, user_id, "cards")
                    logging.info(f"Incremented daily card usage for user {user_id} for generated card")
                except Exception as e:
                    logging.error(f"Error incrementing card usage for user {user_id}: {str(e)}")
                    # We don't want to fail the operation if usage tracking fails
            
            # Structure the response with additional metadata
            result = {
                "answer": response.get("answer", "Sorry, I couldn't generate an answer."),
                "related_card": response.get("related_card", {}),
                "context": {
                    "current_card_id": card_id,
                    "section_id": section_id,
                    "section_title": section_title,
                    "course_title": course_title
                },
                "status": {
                    "success": True,
                    "has_related_card": bool(response.get("related_card"))
                }
            }
            
            return result
            
        except Exception as e:
            logging.error(f"Error processing learning question: {e}", exc_info=True)
            # Return an error response that the frontend can handle
            return {
                "answer": "Sorry, I encountered an error while processing your question. Please try again.",
                "related_card": None,
                "context": {
                    "current_card_id": card_id,
                    "section_id": section_id
                },
                "status": {
                    "success": False,
                    "error_message": str(e)
                }
            }
    
    async def add_related_card_to_section(
        self,
        db,  # Database session
        card_data: Dict[str, Any],
        section_id: int,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Add a generated related card to a section
        
        Args:
            db: Database session
            card_data: Card data from the learning assistant
            section_id: ID of the section to add the card to
            user_id: Optional user ID for tracking who added the card
            
        Returns:
            The created card with ID and status information
        """
        try:
            # Validate section exists
            section = get_section(db, section_id)
            if not section:
                raise HTTPException(status_code=404, detail=f"Section with ID {section_id} not found")
            
            # Create the card schema from the data
            card_create = CardCreateSchema(
                keyword=card_data.get("keyword"),
                question=card_data.get("question"),
                answer=card_data.get("answer"),
                explanation=card_data.get("explanation"),
                difficulty=card_data.get("difficulty", "intermediate"),
                resources=card_data.get("resources", []),
                created_by=f"User {user_id}" if user_id else "Learning Assistant"
            )
            
            # Create the card in the database and link it to the section
            created_card = create_card(
                db=db, 
                card_data=card_create, 
                section_id=section_id
            )
            
            # If a user is specified, increment their daily usage count for cards
            if user_id:
                user_section = db.query(UserSection).filter(
                    UserSection.user_id == user_id,
                    UserSection.section_template_id == section_id
                ).first()

                if not user_section:
                    raise HTTPException(status_code=404, detail="UserSection not found for this user and section")

                # ✅ 获取当前最大 order_index
                max_order_index = db.query(func.max(user_section_cards.c.order_index)).filter(
                    user_section_cards.c.user_section_id == user_section.id
                ).scalar() or 0

                # ✅ 插入 user_section_cards
                db.execute(
                    user_section_cards.insert().values(
                        user_section_id=user_section.id,
                        card_id=created_card.id,
                        order_index=max_order_index + 1,
                        is_custom=True
                    )
                )
                db.commit()

                # ✅ 插入 user_cards 记录（未完成状态）
                db.execute(
                    text("""
                    INSERT INTO user_cards (user_id, card_id, is_completed, saved_at)
                    VALUES (:user_id, :card_id, false, NOW())
                    """),
                    {"user_id": user_id, "card_id": created_card.id}
                )

            # ✅ 使用统计逻辑
            if user_id:
                try:
                    increment_usage(db, user_id, "cards")
                    logging.info(f"Incremented daily card usage for user {user_id}")
                except Exception as e:
                    logging.error(f"Error incrementing card usage for user {user_id}: {str(e)}")

            db.commit()

            # Return the created card with additional information
            return {
                "card": {
                    "id": created_card.id,
                    "keyword": created_card.keyword,
                    "question": created_card.question,
                    "answer": created_card.answer,
                    "explanation": created_card.explanation,
                    "difficulty": created_card.difficulty,
                    "section_id": section_id
                },
                "status": {
                    "success": True,
                    "message": f"Card successfully added to section '{section.title}'"
                }
            }
            
        except HTTPException as he:
            # Re-raise HTTP exceptions for proper API responses
            raise he
        except Exception as e:
            logging.error(f"Error adding related card to section: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to add card to section: {str(e)}"
            )
    
    async def generate_cards_for_topic(
        self,
        topic: str,
        num_cards: int = 3,
        section_id: Optional[int] = None,
        course_title: Optional[str] = None,
        difficulty_level: str = "intermediate",
        user_id: Optional[int] = None,
        db = None
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple cards for a specific topic
        
        Args:
            topic: The topic to generate cards for
            num_cards: Number of cards to generate
            section_id: Optional section ID for context
            course_title: Optional course title for context
            difficulty_level: Desired difficulty level
            user_id: Optional user ID for tracking usage
            db: Database session for tracking usage
            
        Returns:
            List of generated card data
        """
        try:
            if not self.agent:
                raise RuntimeError("LearningAssistantAgent not initialized. Check Azure OpenAI configuration.")
            
            # Use the CardGeneratorAgent's method if the agent has it
            if hasattr(self.agent, "generate_multiple_cards_from_topic"):
                cards = await self.agent.generate_multiple_cards_from_topic(
                    topic=topic,
                    num_cards=num_cards,
                    course_title=course_title,
                    difficulty=difficulty_level
                )
                
                # If a user is specified and db session is provided, increment their daily usage count for each card generated
                if user_id and db and cards:
                    try:
                        # Use a single increment with count=len(cards) to avoid multiple DB queries
                        increment_usage(db, user_id, "cards", count=len(cards))
                        logging.info(f"Incremented daily card usage for user {user_id} by {len(cards)}")
                    except Exception as e:
                        logging.error(f"Error incrementing card usage for user {user_id}: {str(e)}")
                        # We don't want to fail the operation if the usage tracking fails
                
                # Convert CardCreate objects to dicts if needed
                return [card.dict() if hasattr(card, "dict") else card for card in cards]
            
            # Fallback to generating one card at a time if needed
            cards = []
            for i in range(num_cards):
                # Generate a specific aspect of the topic for variety
                subtopic = f"{topic} - aspect {i+1}" if i > 0 else topic
                card = await self.agent.generate_related_card(
                    keyword=subtopic,
                    section_title=None,  # We're using topic directly
                    course_title=course_title,
                    difficulty_level=difficulty_level
                )
                cards.append(card)
                
                # Track individual card generation if user_id is provided and db session is available
                if user_id and db:
                    try:
                        increment_usage(db, user_id, "cards", count=1)
                        logging.info(f"Incremented daily card usage for user {user_id}")
                    except Exception as e:
                        logging.error(f"Error incrementing card usage for user {user_id}: {str(e)}")
                        # Continue even if tracking fails
            
            return cards
            
        except Exception as e:
            logging.error(f"Error generating cards for topic: {e}", exc_info=True)
            # Return at least one minimal valid card as fallback
            return [{
                "keyword": topic,
                "question": f"What is {topic}?",
                "answer": f"This is a concept related to the requested topic.",
                "explanation": "More information would normally be provided here.",
                "difficulty": difficulty_level,
                "resources": []
            }] 