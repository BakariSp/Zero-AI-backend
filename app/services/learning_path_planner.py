from typing import List, Dict, Any, Optional
import logging
import asyncio
from sqlalchemy.orm import Session

from app.services.ai_generator import (
    LearningPathPlannerAgent, 
    CardGeneratorAgent, 
    ParallelCardGeneratorManager,
    get_learning_path_planner_agent,  # Import the helper function
    general_client,
    GENERAL_DEPLOYMENT
)
from app.learning_paths.schemas import LearningPathCreate
from app.courses.schemas import CourseCreate
from app.learning_paths.crud import create_learning_path, assign_learning_path_to_user
from app.cards.crud import create_card, save_card_for_user
from app.courses.crud import create_course, add_section_to_course
from app.sections.crud import create_section, add_card_to_section
from app.utils.url_validator import get_valid_resources  # Import the URL validator
from openai import AsyncOpenAI
import os

class LearningPathPlannerService:
    """Service to handle the full learning path planning workflow"""
    
    def __init__(self):
        # Use the helper function to get the initialized agent
        try:
            self.planner_agent = get_learning_path_planner_agent()
            self.card_manager = ParallelCardGeneratorManager()
            logging.info("Successfully initialized LearningPathPlannerService with AI agents")
        except RuntimeError as e:
            logging.error(f"Failed to initialize LearningPathPlannerService: {e}")
            # You can either raise the error or set the agents to None and handle it later
            self.planner_agent = None
            self.card_manager = None

    async def generate_learning_path(self, interests, difficulty_level, estimated_days):
        """Generate a learning path with the planner agent"""
        if not self.planner_agent:
            raise RuntimeError("LearningPathPlannerAgent not initialized. Check Azure OpenAI configuration.")
        
        # Continue with the existing code
        return await self.planner_agent.generate_learning_path(
            interests=interests,
            difficulty_level=difficulty_level,
            estimated_days=estimated_days
        )

    async def generate_complete_learning_path(
        self,
        db: Session,
        interests: List[str],
        user_id: Optional[int] = None,
        difficulty_level: str = "intermediate",
        estimated_days: int = 30
    ) -> Dict[str, Any]:
        """
        Generate a complete learning path with courses, sections, and card keywords
        
        Workflow:
        1. Learning Path Planner Agent generates path structure with courses, sections, and keywords
        2. Create the learning path, courses, and sections in the database
        3. Return structured data including card keywords for further card generation
        """
        try:
            # 1. Generate learning path plan with the agent
            plan_data = await self.planner_agent.generate_learning_path(
                interests=interests,
                difficulty_level=difficulty_level,
                estimated_days=estimated_days
            )
            
            # 2. Extract components
            learning_path_data = plan_data.get("learning_path", {})
            courses_data = plan_data.get("courses", [])
            
            # 3. Create learning path in database
            learning_path_create = LearningPathCreate(
                title=learning_path_data.get("title"),
                description=learning_path_data.get("description"),
                category=learning_path_data.get("category", interests[0]),
                difficulty_level=learning_path_data.get("difficulty_level", difficulty_level),
                estimated_days=learning_path_data.get("estimated_days", estimated_days),
                sections=[]  # We'll add sections through courses
            )
            
            learning_path_db = create_learning_path(db, learning_path_create)
            
            # 4. Process courses and their sections
            result_courses = []
            for i, course_data in enumerate(courses_data):
                # Create course
                course_create = CourseCreate(
                    title=course_data.get("title"),
                    description=course_data.get("description"),
                    estimated_days=course_data.get("estimated_days", 7),
                )
                
                course_db = create_course(db, course_create)
                
                # Add course to learning path with correct order
                from app.learning_path_courses.crud import add_course_to_learning_path
                add_course_to_learning_path(db, learning_path_db.id, course_db.id, i+1)
                
                # Process sections for this course
                result_sections = []
                for j, section_data in enumerate(course_data.get("sections", [])):
                    # Extract card keywords before creating section
                    keywords = section_data.pop("card_keywords", [])
                    
                    # Add order index to section data
                    section_data["order_index"] = j + 1
                    
                    # Create section
                    section_db = create_section(db, section_data)
                    
                    # Add section to course with correct order
                    add_section_to_course(db, course_db.id, section_db.id, j+1)
                    
                    # Add section to result with keywords for later card generation
                    result_sections.append({
                        "section_id": section_db.id,
                        "title": section_db.title,
                        "keywords": keywords
                    })
                
                # Add course to result
                result_courses.append({
                    "course_id": course_db.id,
                    "title": course_db.title,
                    "sections": result_sections
                })
            
            # 5. Create a structured result with all the IDs for later processing
            result = {
                "learning_path": {
                    "id": learning_path_db.id,
                    "title": learning_path_db.title,
                    "description": learning_path_db.description
                },
                "courses": result_courses
            }
            
            # 6. If user_id is provided, assign the learning path to the user
            if user_id:
                assign_learning_path_to_user(db, user_id, learning_path_db.id)
                
            return result
            
        except Exception as e:
            logging.error(f"Error in generate_complete_learning_path: {e}")
            raise
    
    async def generate_cards_for_learning_path(
        self,
        db: Session,
        learning_path_structure: Dict[str, Any],
        progress_callback: Optional[callable] = None,
        cards_per_section: int = 4, # Define how many cards per section
        user_id: Optional[int] = None  # Add user_id parameter
    ) -> List[Dict[str, Any]]:
        """
        Generate a fixed number of cards for each section in a learning path structure.
        Uses generate_multiple_cards_from_topic based on section title.
        
        Args:
            db: Database session
            learning_path_structure: Structure of learning path with courses and sections
            progress_callback: Optional callback for progress updates
            cards_per_section: Number of cards to generate per section
            user_id: Optional user ID to associate cards with in user_cards table
        """
        section_tasks = []
        section_contexts = [] # To store section_id for linking cards later

        # Extract difficulty from the overall path structure if available
        path_difficulty = learning_path_structure.get("learning_path", {}).get("difficulty_level", "intermediate")

        # 1. Create one task per SECTION
        for course in learning_path_structure.get("courses", []):
            course_title = course.get("title")
            for section in course.get("sections", []):
                section_title = section.get("title")
                section_id = section.get("section_id")
                # Original keywords are no longer the primary input for card generation here
                # keywords = section.get("keywords", [])

                if not section_title or not section_id:
                    logging.warning(f"Skipping section due to missing title or ID in course '{course_title}'. Title: '{section_title}', ID: {section_id}")
                    continue

                # Create a task to generate multiple cards for this section's topic
                task = self.card_manager.card_generator.generate_multiple_cards_from_topic(
                    topic=section_title,
                    num_cards=cards_per_section,
                    course_title=course_title,
                    difficulty=path_difficulty # Pass difficulty
                )
                section_tasks.append(task)
                # Store context needed after gather
                section_contexts.append({
                    "section_id": section_id,
                    "section_title": section_title, # Keep title for logging/debugging
                    "course_title": course_title     # Store course title for resource validation
                })

        # 2. Execute all section tasks in parallel
        # Each result in 'batch_results' will be a list of CardCreate objects for a section
        batch_results = await asyncio.gather(*section_tasks, return_exceptions=True)

        # 3. Process results and create cards in DB
        result_cards = []
        total_cards_processed = 0
        card_order_in_section = {} # Track order within each section

        for i, batch_result in enumerate(batch_results):
            section_id = section_contexts[i]["section_id"]
            section_title = section_contexts[i]["section_title"]
            course_title = section_contexts[i]["course_title"]

            if isinstance(batch_result, Exception):
                logging.error(f"Card generation task failed for section {section_id} ('{section_title}'): {batch_result}")
                # Optionally report partial failure via progress_callback or task status
                if progress_callback:
                     # You might need a more sophisticated progress update mechanism
                     # This simple version just notes the failure for the whole section batch
                     pass # Or call progress_callback(section_id, "failed", 0, str(batch_result)) if adapted
                continue # Skip this batch

            if not isinstance(batch_result, list):
                 logging.error(f"Unexpected result type for section {section_id}: {type(batch_result)}. Expected list.")
                 continue

            # Ensure the card_order_in_section counter starts at 0 for each new section
            if section_id not in card_order_in_section:
                card_order_in_section[section_id] = 0

            # Process each card generated in the batch for this section
            for card_index, card_data in enumerate(batch_result):
                 # Validate card_data structure (should be CardCreate compatible)
                 if not card_data or not hasattr(card_data, 'keyword') or not card_data.keyword:
                      logging.warning(f"Skipping invalid/incomplete card data in batch for section {section_id}: {card_data}")
                      continue

                 try:
                     # NEW: Validate and enhance resources using Google Search API
                     if hasattr(card_data, 'resources'):
                         # Check if we need to convert to dict for processing
                         card_dict = card_data.dict() if hasattr(card_data, 'dict') else card_data
                         
                         # Create search context from card and section data
                         context = f"{section_title} - {course_title}"
                         
                         # Validate and enhance resources
                         validated_resources = await asyncio.to_thread(
                             get_valid_resources,
                             keyword=card_data.keyword,
                             context=context,
                             existing_resources=card_dict.get('resources', [])
                         )
                         
                         # Update card resources with validated ones
                         if hasattr(card_data, 'resources'):
                             card_data.resources = validated_resources
                         else:
                             # If card_data is a dict
                             card_dict['resources'] = validated_resources
                             card_data = card_dict
                     
                     # Create the card with validated resources
                     card_db = create_card(db, card_data) # Assuming create_card handles CardCreate schema

                     # Associate card with section
                     current_order = card_order_in_section[section_id]
                     add_card_to_section(db, section_id, card_db.id, current_order + 1)
                     card_order_in_section[section_id] += 1 # Increment order for the next card in this section

                     # Associate card with user in user_cards table if user_id provided
                     if user_id:
                         try:
                             save_card_for_user(
                                 db=db, 
                                 user_id=user_id, 
                                 card_id=card_db.id,
                                 recommended_by="Learning Path Generator"
                             )
                             logging.info(f"Associated card {card_db.id} with user {user_id} in user_cards table")
                         except Exception as user_card_err:
                             logging.error(f"Failed to associate card {card_db.id} with user {user_id}: {user_card_err}", exc_info=True)

                     # Add to result list
                     result_cards.append({
                         "card_id": card_db.id,
                         "keyword": card_db.keyword,
                         "section_id": section_id
                     })

                     # Update progress if callback provided
                     total_cards_processed += 1
                     if progress_callback:
                          progress_callback(total_cards_processed)
                 except Exception as e:
                     logging.error(f"Error creating card for section {section_id}: {e}", exc_info=True)
                     continue # Skip this card on error but continue with others
        
        logging.info(f"Successfully created {total_cards_processed} cards across {len(section_tasks)} sections")
        return result_cards

    async def generate_cards_for_structured_path(
        self,
        db: Session,
        learning_path_structure: Dict[str, Any],
        cards_per_section: int,
        progress_callback: Optional[callable] = None,
        user_id: Optional[int] = None  # Add user_id parameter
    ):
        """
        Generate cards for a learning path with predefined course/section structure
        
        Args:
            db: Database session
            learning_path_structure: Structure of learning path with courses and sections
            cards_per_section: Number of cards to generate per section
            progress_callback: Optional callback for progress updates
            user_id: Optional user ID to associate cards with in user_cards table
        """
        # Get path data for context
        path_id = learning_path_structure.get("id")
        path_title = learning_path_structure.get("title")
        path_difficulty = learning_path_structure.get("difficulty_level", "intermediate")

        # Get total sections for progress tracking
        total_sections = sum(len(course.get("sections", [])) 
                           for course in learning_path_structure.get("courses", []))
        sections_processed = 0
        cards_processed = 0

        # Store results
        all_created_cards = []

        # Configure concurrency (adjust as needed)
        # semaphore = asyncio.Semaphore(5) # Limit concurrent section processing

        # Process each section
        async def process_section(section_data):
            # async with semaphore: # Uncomment if using semaphore
            nonlocal sections_processed, cards_processed
            
            try:
                section_id = section_data.get("id")
                section_title = section_data.get("title")
                course_title = section_data.get("course_title", "")  # Get course title if available
                
                logging.info(f"Generating cards for section {section_id}: {section_title}")
                
                # Generate cards for this section
                cards = await self.card_manager.card_generator.generate_multiple_cards_from_topic(
                    topic=section_title,
                    num_cards=cards_per_section,
                    course_title=course_title,
                    difficulty=path_difficulty
                )
                
                created_cards = []
                
                for card in cards:
                    try:
                        # NEW: Validate and enhance resources using Google Search API
                        if hasattr(card, 'resources'):
                            # Check if we need to convert to dict for processing
                            card_dict = card.dict() if hasattr(card, 'dict') else card
                            
                            # Create search context from card and section data
                            context = f"{section_title} - {course_title}"
                            
                            # Validate and enhance resources
                            validated_resources = await asyncio.to_thread(
                                get_valid_resources,
                                keyword=card.keyword,
                                context=context,
                                existing_resources=card_dict.get('resources', [])
                            )
                            
                            # Update card resources with validated ones
                            if hasattr(card, 'resources'):
                                card.resources = validated_resources
                            else:
                                # If card is a dict
                                card_dict['resources'] = validated_resources
                                card = card_dict
                        
                        # Create card in DB
                        card_db = create_card(db, card)
                        
                        # Associate with section
                        add_card_to_section(db, section_id, card_db.id)
                        
                        # Associate card with user in user_cards table if user_id provided
                        if user_id:
                            try:
                                save_card_for_user(
                                    db=db, 
                                    user_id=user_id, 
                                    card_id=card_db.id,
                                    recommended_by="Structured Learning Path"
                                )
                                logging.info(f"Associated card {card_db.id} with user {user_id} in user_cards table")
                            except Exception as user_card_err:
                                logging.error(f"Failed to associate card {card_db.id} with user {user_id}: {user_card_err}", exc_info=True)
                        
                        created_cards.append({
                            "id": card_db.id,
                            "keyword": card.keyword
                        })
                        
                        cards_processed += 1
                        if progress_callback:
                            progress_callback(cards_processed)
                            
                    except Exception as e:
                        logging.error(f"Error saving card for section {section_id}: {e}")
                
                # Update progress
                sections_processed += 1
                
                return {
                    "section_id": section_id,
                    "cards": created_cards
                }
                
            except Exception as e:
                logging.error(f"Error processing section {section_data.get('id')}: {e}")
                return {
                    "section_id": section_data.get("id"),
                    "error": str(e),
                    "cards": []
                }

        # Prepare section tasks
        section_tasks = []
        for course in learning_path_structure.get("courses", []):
            course_title = course.get("title", "")
            for section in course.get("sections", []):
                # Add course title to section data for context in resource generation
                section["course_title"] = course_title
                section_tasks.append(process_section(section))
                
        # Run all section tasks concurrently
        section_results = await asyncio.gather(*section_tasks, return_exceptions=True)
        
        # Process results
        for result in section_results:
            if isinstance(result, Exception):
                logging.error(f"Section processing failed: {result}")
                continue
            
            if isinstance(result, dict) and "cards" in result:
                all_created_cards.extend(result["cards"])
                
        return {
            "cards_created": len(all_created_cards),
            "sections_processed": sections_processed,
            "cards": all_created_cards
        }

    # Make sure generate_cards_for_learning_path still exists for the old endpoints
    # It might need adjustments based on the CardGeneratorAgent changes if you modified generate_card directly