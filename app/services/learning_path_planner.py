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
        Generate all cards for a learning path structure in parallel
        
        Args:
            db: Database session
            learning_path_structure: The structure returned by generate_complete_learning_path
            progress_callback: Optional callback function to report progress
            
        Returns:
            List of created cards with their section associations
        """
        all_tasks = []
        all_task_contexts = []  # To keep track of section and course for each task
        
        # Extract all keywords with their context from the learning path structure
        for course in learning_path_structure.get("courses", []):
            course_title = course.get("title")
            for section in course.get("sections", []):
                section_title = section.get("title")
                section_id = section.get("section_id")
                keywords = section.get("keywords", [])
                
                for keyword in keywords:
                    # Create a task for each keyword
                    task = self.card_manager.card_generator.generate_card(
                        keyword=keyword,
                        section_title=section_title,
                        course_title=course_title
                    )
                    all_tasks.append(task)
                    all_task_contexts.append({
                        "section_id": section_id,
                        "keyword": keyword
                    })
        
        # Execute all card generation tasks in parallel
        generated_cards = await asyncio.gather(*all_tasks)
        
        # Create cards in database and link to sections
        result_cards = []
        for i, card_data in enumerate(generated_cards):
            section_id = all_task_contexts[i]["section_id"]
            
            # Create the card
            card_db = create_card(db, card_data)
            
            # Associate card with section
            add_card_to_section(db, section_id, card_db.id, i+1)
            
            # Add to result
            result_cards.append({
                "card_id": card_db.id,
                "keyword": card_db.keyword,
                "section_id": section_id
            })
            
            # Report progress if callback provided
            if progress_callback:
                progress_callback(i + 1)
            
        return result_cards 