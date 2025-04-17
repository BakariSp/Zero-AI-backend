from typing import List, Dict, Any, Optional
import logging
import asyncio
from sqlalchemy.orm import Session

from app.services.ai_generator import LearningPathPlannerAgent, CardGeneratorAgent, ParallelCardGeneratorManager
from app.learning_paths.schemas import LearningPathCreate
from app.courses.schemas import CourseCreate
from app.learning_paths.crud import create_learning_path, assign_learning_path_to_user
from app.cards.crud import create_card
from app.courses.crud import create_course, add_section_to_course
from app.sections.crud import create_section, add_card_to_section

class LearningPathPlannerService:
    """Service to handle the full learning path planning workflow"""
    
    def __init__(self):
        self.planner_agent = LearningPathPlannerAgent()
        self.card_manager = ParallelCardGeneratorManager()
    
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
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate all cards for a learning path structure using batch processing per section.
        """
        section_tasks = []
        section_contexts = [] # To store section_id for linking cards later

        # 1. Create one task per SECTION, not per keyword
        for course in learning_path_structure.get("courses", []):
            course_title = course.get("title")
            for section in course.get("sections", []):
                section_title = section.get("title")
                section_id = section.get("section_id")
                keywords = section.get("keywords", [])

                if not keywords: # Skip sections with no keywords
                    continue

                # Create a single task for all keywords in this section
                task = self.card_manager.card_generator.generate_cards_for_section_batch( # <--- NEW BATCH METHOD
                    keywords=keywords,
                    section_title=section_title,
                    course_title=course_title
                )
                section_tasks.append(task)
                # Store context needed after gather (section_id and original keywords for matching)
                section_contexts.append({
                    "section_id": section_id,
                    "keywords": keywords # Keep keywords if needed to match results, or rely on order
                })

        # 2. Execute all section-batch tasks in parallel
        # Each result in 'batch_results' will be a list of card data dicts for a section
        batch_results = await asyncio.gather(*section_tasks, return_exceptions=True) # Handle potential errors per batch

        # 3. Process results and create cards in DB
        result_cards = []
        total_cards_processed = 0
        card_order_in_section = {} # Track order within each section

        for i, batch_result in enumerate(batch_results):
            section_id = section_contexts[i]["section_id"]
            original_keywords = section_contexts[i]["keywords"] # Get keywords for this batch

            if isinstance(batch_result, Exception):
                logging.error(f"Card generation batch failed for section {section_id}: {batch_result}")
                # Optionally report partial failure via progress_callback or task status
                continue # Skip this batch

            if not isinstance(batch_result, list):
                 logging.error(f"Unexpected result type for section {section_id}: {type(batch_result)}. Expected list.")
                 continue

            # Ensure the card_order_in_section counter starts at 0 for each new section
            if section_id not in card_order_in_section:
                card_order_in_section[section_id] = 0

            # Process each card generated in the batch for this section
            # IMPORTANT: Ensure the AI returns cards in the same order as keywords were provided,
            # or include the original keyword in the AI response for matching.
            # Assuming order is preserved for simplicity here:
            for card_index, card_data in enumerate(batch_result):
                 # Add keyword if not returned by AI but needed for Card model/DB
                 if "keyword" not in card_data and card_index < len(original_keywords):
                     card_data["keyword"] = original_keywords[card_index]

                 # Validate card_data structure if necessary
                 if not card_data or "keyword" not in card_data:
                      logging.warning(f"Skipping invalid card data in batch for section {section_id}: {card_data}")
                      continue

                 # Create the card
                 card_db = create_card(db, card_data) # Assuming create_card handles CardCreate schema

                 # Associate card with section
                 current_order = card_order_in_section[section_id]
                 add_card_to_section(db, section_id, card_db.id, current_order + 1)
                 card_order_in_section[section_id] += 1 # Increment order for the next card in this section

                 # Add to result list
                 result_cards.append({
                     "card_id": card_db.id,
                     "keyword": card_db.keyword,
                     "section_id": section_id
                 })

                 total_cards_processed += 1
                 # Report progress if callback provided
                 if progress_callback:
                     # Note: The total number of cards might need recalculation
                     # or the progress logic might need adjustment based on batches.
                     # This simple callback assumes progress per card processed.
                     progress_callback(total_cards_processed)

        return result_cards