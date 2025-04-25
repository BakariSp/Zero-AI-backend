import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
import asyncio
import time
from datetime import datetime, timedelta, timezone
import traceback
import uuid

from app.db import SessionLocal
from app.services.learning_path_planner import LearningPathPlannerService
from app.services.ai_generator import extract_learning_goals
from app.models import LearningPath, User
from app.learning_paths.crud import get_learning_path, assign_learning_path_to_user, create_learning_path
from app.users.crud import get_user
from app.recommendation.schemas import LearningPathStructureRequest, SectionGenerationStatus, EnhancedTaskStatus
from app.learning_paths.schemas import LearningPathCreate
from app.courses.schemas import CourseCreate
from app.sections.schemas import SectionCreate
from app.courses.crud import create_course, add_section_to_course
from app.sections.crud import create_section
from app.learning_path_courses.crud import add_course_to_learning_path
from app.tasks.crud import create_user_task, update_user_task, get_user_task_by_task_id
from app.tasks.schemas import UserTaskCreate, UserTaskUpdate
from app.tasks.models import TaskStatusEnum, TaskStageEnum
from app.models import CourseSection, Course

# 全局任务状态跟踪
task_status: Dict[str, Dict[str, Any]] = {}

async def generate_cards_background(
    learning_path_id: int,
    user_id: int,
    learning_path_structure: Dict[str, Any],
    timeout_seconds: int = 600  # 10 minutes default timeout
):
    """后台生成卡片的任务"""
    logging.info(f"Starting background card generation for learning path {learning_path_id}")
    
    # Create task status record
    task_id = f"card_gen_{learning_path_id}_{user_id}"
    task_status[task_id] = {
        "status": "running",
        "progress": 0,
        "total": 0,
        "completed": 0,
        "errors": []
    }
    
    try:
        # Create database session
        db = SessionLocal()
        
        # Initialize service
        planner_service = LearningPathPlannerService()
        
        # Calculate total tasks
        total_cards = 0
        result_courses = []
        for course in learning_path_structure.get("courses", []):
            for section in course.get("sections", []):
                total_cards += len(section.get("keywords", []))
        
        task_status[task_id]["total"] = total_cards
        
        # Generate cards with timeout
        try:
            result_cards = await asyncio.wait_for(
                planner_service.generate_cards_for_learning_path(
                    db=db,
                    learning_path_structure=learning_path_structure,
                    progress_callback=lambda completed: update_task_progress(task_id, completed)
                ),
                timeout=timeout_seconds
            )
            
            # Update task status
            task_status[task_id]["status"] = "completed"
            task_status[task_id]["progress"] = 100
            task_status[task_id]["completed"] = total_cards
            
            logging.info(f"Completed background card generation for learning path {learning_path_id}")
        except asyncio.TimeoutError:
            task_status[task_id]["status"] = "timeout"
            task_status[task_id]["errors"].append(f"Task timed out after {timeout_seconds} seconds")
            logging.error(f"Card generation timed out for learning path {learning_path_id}")
    except Exception as e:
        error_details = traceback.format_exc()
        logging.error(f"Error in background card generation: {e}")
        logging.error(f"Traceback: {error_details}")
        task_status[task_id]["status"] = "failed"
        task_status[task_id]["errors"].append(str(e))
        task_status[task_id]["error_details"] = error_details
    finally:
        db.close()

async def generate_full_learning_path_background(
    task_id: str,
    prompt: str,
    user_id: int,
    timeout_seconds: int = 1200 # Increase timeout for the whole process (e.g., 20 mins)
):
    """Background task to handle the entire learning path generation process."""
    logging.info(f"Starting full learning path generation for task {task_id}, user {user_id}")

    # Initialize task status
    task_status[task_id] = {
        "task_id": task_id,
        "status": "starting",
        "stage": "initializing",
        "progress": 0,
        "total_cards": 0,
        "cards_completed": 0,
        "learning_path_id": None,
        "total_sections": None,
        "sections_completed": 0,
        "total_cards_expected": None,
        "section_status": {},
        "errors": [],
        "error_details": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "start_time": time.time()
    }

    db: Optional[Session] = None
    start_time = time.time()

    try:
        db = SessionLocal()
        planner_service = LearningPathPlannerService()

        # --- Stage 1: Extract Goals ---
        task_status[task_id]["stage"] = "extracting_goals"
        logging.info(f"Task {task_id}: Extracting learning goals...")
        interests, difficulty_level, estimated_days = await extract_learning_goals(prompt)
        logging.info(f"Task {task_id}: Goals extracted - Interests: {interests}, Difficulty: {difficulty_level}, Days: {estimated_days}")

        # --- Stage 2: Generate Path Structure (AI Call + DB Writes) ---
        task_status[task_id]["stage"] = "planning_path_structure"
        update_user_task(db, task_id, UserTaskUpdate(stage=TaskStageEnum.PLANNING_STRUCTURE))
        logging.info(f"Task {task_id}: Generating path structure...")
        path_structure_result = await planner_service.generate_complete_learning_path(
            db=db,
            interests=interests,
            user_id=user_id, # Pass user_id here
            difficulty_level=difficulty_level,
            estimated_days=estimated_days
        )
        learning_path_id = path_structure_result["learning_path"]["id"]
        task_status[task_id]["learning_path_id"] = learning_path_id
        logging.info(f"Task {task_id}: Path structure created (ID: {learning_path_id}).")

        # --- ADDED: Update user_tasks table with the learning_path_id ---
        try:
            update_user_task(db, task_id, UserTaskUpdate(learning_path_id=learning_path_id))
            logging.info(f"Task {task_id}: Updated user_tasks record with learning_path_id {learning_path_id}.")
        except Exception as db_update_err:
            # Log the error but continue the process if possible
            logging.error(f"Task {task_id}: Failed to update user_tasks record with learning_path_id: {db_update_err}", exc_info=True)
        # --- END ADDED ---

        # --- Stage 3: Generate Cards ---
        task_status[task_id]["stage"] = "generating_cards"
        update_user_task(db, task_id, UserTaskUpdate(stage=TaskStageEnum.GENERATING_CARDS))
        logging.info(f"Task {task_id}: Starting card generation...")

        # Calculate total cards for progress tracking
        total_cards = 0
        for course in path_structure_result.get("courses", []):
            for section in course.get("sections", []):
                total_cards += len(section.get("keywords", [])) # Use 'keywords' from the structure
        task_status[task_id]["total_cards"] = total_cards

        # Define progress callback for card generation
        def card_progress_callback(completed_count):
            task_status[task_id]["cards_completed"] = completed_count
            if total_cards > 0:
                task_status[task_id]["progress"] = int((completed_count / total_cards) * 100)
            else:
                 task_status[task_id]["progress"] = 100 # Handle case with 0 keywords

        # Execute card generation (this function needs the DB session)
        # Use asyncio.wait_for for timeout on card generation specifically
        card_timeout = timeout_seconds - (time.time() - start_time) # Remaining time
        if card_timeout <= 0:
             raise asyncio.TimeoutError("Not enough time remaining for card generation.")

        await asyncio.wait_for(
            planner_service.generate_cards_for_learning_path(
                db=db,
                learning_path_structure=path_structure_result, # Pass the full structure
                progress_callback=card_progress_callback
            ),
            timeout=card_timeout
        )

        # --- Completion ---
        task_status[task_id]["status"] = "completed"
        task_status[task_id]["stage"] = "finished"
        task_status[task_id]["progress"] = 100
        task_status[task_id]["cards_completed"] = total_cards # Ensure it shows total on completion
        update_user_task(db, task_id, UserTaskUpdate(status=TaskStatusEnum.COMPLETED, stage=TaskStageEnum.FINISHED, progress=100))
        logging.info(f"Task {task_id}: Successfully completed full learning path generation.")

    except asyncio.TimeoutError:
        elapsed_time = time.time() - start_time
        task_status[task_id]["status"] = "timeout"
        task_status[task_id]["errors"].append(f"Task timed out after {elapsed_time:.2f} seconds (limit: {timeout_seconds}s)")
        update_user_task(db, task_id, UserTaskUpdate(status=TaskStatusEnum.TIMEOUT, error_details=f"Timeout after {elapsed_time:.2f}s"))
        logging.error(f"Task {task_id}: Generation timed out.")
    except Exception as e:
        error_details = traceback.format_exc()
        logging.error(f"Task {task_id}: Error during generation: {e}\n{error_details}")
        task_status[task_id]["status"] = "failed"
        task_status[task_id]["errors"].append(f"Error in stage '{task_status[task_id]['stage']}': {str(e)}")
        task_status[task_id]["error_details"] = error_details # Optional: include traceback for debugging
        update_user_task(db, task_id, UserTaskUpdate(status=TaskStatusEnum.FAILED, error_details=error_details))
    finally:
        if db:
            db.close()
        task_status[task_id]["end_time"] = time.time()

def update_task_progress(task_id: str, completed_count: int):
    """Updates the progress of a specific task."""
    if task_id in task_status:
        task_status[task_id]["cards_completed"] = completed_count
        total = task_status[task_id].get("total_cards", 0)
        if total > 0:
            task_status[task_id]["progress"] = int((completed_count / total) * 100)
        else:
            task_status[task_id]["progress"] = 100 # Or 0 if no cards expected
        task_status[task_id]["updated_at"] = datetime.now(timezone.utc)
    else:
        logging.warning(f"Attempted to update progress for unknown task_id: {task_id}")

def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """Safely retrieves the status dictionary for a given task ID."""
    return task_status.get(task_id)

def schedule_learning_path_generation(
    background_tasks: BackgroundTasks,
    db: Session,
    learning_path_structure: Dict[str, Any],
    learning_path_id: int,
    user_id: int
):
    """调度学习路径卡片生成任务"""
    task_id = f"card_gen_{learning_path_id}_{user_id}"
    # Create the task record in DB
    create_user_task(db, UserTaskCreate(task_id=task_id, user_id=user_id, status=TaskStatusEnum.QUEUED))
    background_tasks.add_task(
        generate_cards_background,
        learning_path_id=learning_path_id,
        user_id=user_id,
        learning_path_structure=learning_path_structure
    )
    return task_id 

async def cancel_task(task_id: str) -> bool:
    """Cancel a running task"""
    if task_id in task_status and task_status[task_id]["status"] == "running":
        task_status[task_id]["status"] = "cancelled"
        logging.info(f"Task {task_id} has been cancelled")
        return True
    return False 

def cleanup_old_tasks(max_tasks: int = 100, max_age_hours: int = 24):
    """Clean up old task statuses to prevent memory leaks"""
    # Add timestamp to task status if not already there
    for task_id, status in task_status.items():
        if "timestamp" not in status:
            status["timestamp"] = time.time()
    
    # If we have too many tasks, remove the oldest ones
    if len(task_status) > max_tasks:
        # Sort tasks by timestamp
        sorted_tasks = sorted(task_status.items(), key=lambda x: x[1].get("timestamp", 0))
        # Remove oldest tasks
        for task_id, _ in sorted_tasks[:len(task_status) - max_tasks]:
            del task_status[task_id]
    
    # Remove tasks older than max_age_hours
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    for task_id in list(task_status.keys()):
        if current_time - task_status[task_id].get("timestamp", current_time) > max_age_seconds:
            del task_status[task_id] 

all_task_contexts = []  # To keep track of section and course for each task 

def schedule_full_learning_path_generation(
    background_tasks: BackgroundTasks,
    db: Session,
    prompt: str,
    user_id: int
) -> str:
    """Schedules the full learning path generation and returns a task ID."""
    # Generate a unique task ID (consider using UUID)
    task_id = f"full_path_gen_{user_id}_{int(time.time())}"
    logging.info(f"Scheduling full learning path generation task with ID: {task_id}")
    # Create the task record in DB
    create_user_task(db, UserTaskCreate(task_id=task_id, user_id=user_id, status=TaskStatusEnum.QUEUED))
    background_tasks.add_task(
        generate_full_learning_path_background,
        task_id=task_id,
        prompt=prompt,
        user_id=user_id
    )
    # Initialize status immediately so the polling endpoint finds it
    task_status[task_id] = {
        "status": "pending",
        "stage": "queued",
        "progress": 0,
        "learning_path_id": None,
        "errors": [],
        "task_id": task_id # Include task_id in status
    }
    return task_id

from fastapi import APIRouter as TaskRouter
task_router = TaskRouter()

def schedule_structured_learning_path_generation(
    background_tasks: BackgroundTasks,
    db: Session,
    user_id: int,
    structure_request: LearningPathStructureRequest,
    timeout_seconds: int = 1800 # 30 minutes total timeout
) -> str:
    """Schedules the background task to save structure and generate cards."""
    task_id = f"struct_path_gen_{user_id}_{int(time.time())}"
    logging.info(f"Scheduling structured learning path creation task with ID: {task_id}")

    # --- ADDED: Create the task record in DB ---
    try:
        create_user_task(db, UserTaskCreate(task_id=task_id, user_id=user_id, status=TaskStatusEnum.QUEUED))
        logging.info(f"Task {task_id}: Created initial user_tasks record.")
    except Exception as db_create_err:
        # Log the error and potentially raise it or handle it
        logging.error(f"Task {task_id}: Failed to create initial user_tasks record: {db_create_err}", exc_info=True)
        # Depending on requirements, you might want to raise an exception here
        # to prevent scheduling the background task if the DB record fails.
        raise HTTPException(status_code=500, detail="Failed to create task record in database.")
    # --- END ADDED ---

    task_status[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "stage": "queued",
        "progress": 0,
        "message": "Task queued for processing.",
        "learning_path_id": None,
        "total_sections": None,
        "sections_completed": 0,
        "total_cards_expected": None,
        "cards_completed": 0,
        "section_status": {}, # Initialize section status dict
        "errors": [],
        "error_details": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    background_tasks.add_task(
        _run_structured_path_creation_task,
        task_id,
        SessionLocal,
        user_id,
        structure_request,
        timeout_seconds
    )
    logging.info(f"Scheduled structured learning path creation task {task_id} for user {user_id}")
    return task_id

async def _run_structured_path_creation_task(
    task_id: str,
    db_session_factory: callable,
    user_id: int,
    structure_request: LearningPathStructureRequest,
    timeout_seconds: int
):
    """Task to save structure and generate cards."""
    start_time = time.time()
    db: Optional[Session] = None
    planner_service = LearningPathPlannerService()

    try:
        db = db_session_factory()
        task_status[task_id]["status"] = "running"
        task_status[task_id]["stage"] = "saving_structure"
        task_status[task_id]["updated_at"] = datetime.now(timezone.utc)
        update_user_task(db, task_id, UserTaskUpdate(status=TaskStatusEnum.RUNNING, stage=TaskStageEnum.SAVING_STRUCTURE))
        logging.info(f"Task {task_id}: Starting structure saving for user {user_id}")

        # --- Stage 1: Save Learning Path Structure ---
        learning_path_create = LearningPathCreate(
            title=structure_request.title,
            description=f"Custom learning path based on user structure: {structure_request.title}",
            category=structure_request.courses[0].title if structure_request.courses else "Custom",
            difficulty_level=structure_request.difficulty_level,
            estimated_days=structure_request.estimated_days or len(structure_request.courses) * 7,
            is_template=False
        )
        learning_path_db = create_learning_path(db, learning_path_create)
        assign_learning_path_to_user(db, user_id, learning_path_db.id)
        task_status[task_id]["learning_path_id"] = learning_path_db.id
        logging.info(f"Task {task_id}: Created LearningPath ID {learning_path_db.id}")

        # Update user_tasks table with the learning_path_id
        try:
            update_user_task(db, task_id, UserTaskUpdate(learning_path_id=learning_path_db.id))
            logging.info(f"Task {task_id}: Updated user_tasks record with learning_path_id {learning_path_db.id}.")
        except Exception as db_update_err:
            logging.error(f"Task {task_id}: Failed to update user_tasks record with learning_path_id: {db_update_err}", exc_info=True)

        # Create Courses and Sections
        total_sections = 0
        section_id_map = {}
        
        for i, course_data in enumerate(structure_request.courses):
            course_create = CourseCreate(
                title=course_data.title,
                description=f"Course within '{structure_request.title}' path.",
                estimated_days=7
            )
            course_db = create_course(db, course_create)
            add_course_to_learning_path(db, learning_path_db.id, course_db.id, i + 1)
            logging.info(f"Task {task_id}: Created Course ID {course_db.id} - {course_db.title}")

            for j, section_data in enumerate(course_data.sections):
                total_sections += 1
                section_create = SectionCreate(
                    title=section_data.title,
                    description=f"Section within '{course_data.title}'.",
                    order_index=j + 1
                )
                section_db = create_section(db, section_create)
                add_section_to_course(db, course_db.id, section_db.id, j + 1)
                logging.info(f"Task {task_id}:   Created Section ID {section_db.id} - {section_db.title}")
                
                section_id_map[section_db.id] = SectionGenerationStatus(status="pending")

        task_status[task_id]["total_sections"] = total_sections
        task_status[task_id]["total_cards_expected"] = total_sections * 4  # Assuming 4 cards per section
        task_status[task_id]["section_status"] = section_id_map
        task_status[task_id]["stage"] = "structure_saved"
        task_status[task_id]["progress"] = 10
        task_status[task_id]["updated_at"] = datetime.now(timezone.utc)
        update_user_task(db, task_id, UserTaskUpdate(stage=TaskStageEnum.STRUCTURE_SAVED, progress=10))
        logging.info(f"Task {task_id}: Structure saved. Total sections: {total_sections}")

        # --- Stage 2: Generate Cards ---
        task_status[task_id]["stage"] = "generating_cards"
        update_user_task(db, task_id, UserTaskUpdate(stage=TaskStageEnum.GENERATING_CARDS))
        logging.info(f"Task {task_id}: Starting card generation...")

        # Get the card generator agent
        try:
            from app.services.ai_generator import get_card_generator_agent
            card_generator = get_card_generator_agent()
            logging.info(f"Task {task_id}: Successfully initialized card generator agent")
        except Exception as agent_err:
            logging.error(f"Task {task_id}: Failed to initialize card generator agent: {agent_err}", exc_info=True)
            raise RuntimeError(f"Failed to initialize AI card generator: {agent_err}")

        # Process each section and generate cards
        cards_per_section = 4  # Default number of cards per section
        total_cards_generated = 0
        sections_completed = 0
        sections_failed = 0

        # Process sections one by one to avoid overwhelming the system
        for section_id, section_status in section_id_map.items():
            if time.time() - start_time > timeout_seconds:
                raise asyncio.TimeoutError(f"Task timed out after {timeout_seconds} seconds")
            
            try:
                # Get section details
                section = db.query(CourseSection).filter(CourseSection.id == section_id).first()
                if not section:
                    logging.warning(f"Task {task_id}: Section ID {section_id} not found in database")
                    section_status.status = "failed"
                    section_status.error = "Section not found in database"
                    sections_failed += 1
                    continue
                
                # Get course title for context if available
                course_id = None
                course_title = "Unknown Course"
                # Find the course this section belongs to
                from sqlalchemy import text
                result = db.execute(text(
                    "SELECT course_id FROM course_section_association WHERE section_id = :section_id"
                ), {"section_id": section_id}).fetchone()
                
                if result:
                    course_id = result[0]
                    course = db.query(Course).filter(Course.id == course_id).first()
                    if course:
                        course_title = course.title
                
                # Get difficulty from learning path
                difficulty = structure_request.difficulty_level or "intermediate"
                
                logging.info(f"Task {task_id}: Generating {cards_per_section} cards for section '{section.title}' (ID: {section_id})")
                
                # Generate cards using the same method as in the endpoint
                card_data_list = await card_generator.generate_multiple_cards_from_topic(
                    topic=section.title,
                    num_cards=cards_per_section,
                    course_title=course_title,
                    difficulty=difficulty
                )
                
                if not card_data_list:
                    logging.warning(f"Task {task_id}: AI returned no cards for section '{section.title}' (ID: {section_id})")
                    section_status.status = "failed"
                    section_status.error = "AI returned no cards"
                    sections_failed += 1
                    continue
                
                # Save cards to database and link to section
                cards_saved = 0
                from app.cards.crud import create_card, _get_next_card_order_in_section
                
                for card_data in card_data_list:
                    try:
                        # Create card in database
                        card_db = create_card(db, card_data=card_data)
                        
                        # Add card to section with proper order
                        next_order = _get_next_card_order_in_section(db, section_id)
                        from app.sections.crud import add_card_to_section
                        add_card_to_section(db, section_id, card_db.id, next_order)
                        
                        cards_saved += 1
                        total_cards_generated += 1
                        logging.info(f"Task {task_id}: Created/linked card ID {card_db.id} ('{card_db.keyword}') to section {section_id}")
                    except Exception as card_err:
                        logging.error(f"Task {task_id}: Error saving card '{getattr(card_data, 'keyword', 'N/A')}' for section {section_id}: {card_err}", exc_info=True)
                
                # Update section status
                section_status.status = "completed"
                section_status.cards_generated = cards_saved
                sections_completed += 1
                
                # Update overall task progress
                task_status[task_id]["sections_completed"] = sections_completed
                task_status[task_id]["cards_completed"] = total_cards_generated
                progress = 10 + int(((sections_completed + sections_failed) / total_sections) * 90)
                task_status[task_id]["progress"] = progress
                task_status[task_id]["updated_at"] = datetime.now(timezone.utc)
                
                # Update progress in database
                try:
                    update_user_task(db, task_id, UserTaskUpdate(progress=progress))
                except Exception as prog_err:
                    logging.warning(f"Task {task_id}: Failed to update progress in database: {prog_err}")
                
            except Exception as section_err:
                logging.error(f"Task {task_id}: Error processing section {section_id}: {section_err}", exc_info=True)
                section_status.status = "failed"
                section_status.error = str(section_err)
                sections_failed += 1
        
        # Determine final status
        final_status = "completed"
        if sections_failed > 0 and sections_completed > 0:
            final_status = "completed_with_errors"
            task_status[task_id]["errors"].append(f"{sections_failed} out of {total_sections} sections failed during card generation.")
        elif sections_completed == 0:
            final_status = "failed"
            task_status[task_id]["errors"].append("All sections failed during card generation.")
        
        task_status[task_id]["status"] = final_status
        task_status[task_id]["stage"] = "finished"
        task_status[task_id]["progress"] = 100
        task_status[task_id]["updated_at"] = datetime.now(timezone.utc)
        
        final_db_status = TaskStatusEnum.COMPLETED
        if final_status == "completed_with_errors":
            final_db_status = TaskStatusEnum.COMPLETED_WITH_ERRORS
        elif final_status == "failed":
            final_db_status = TaskStatusEnum.FAILED
            
        update_user_task(db, task_id, UserTaskUpdate(
            status=final_db_status, 
            stage=TaskStageEnum.FINISHED, 
            progress=100, 
            message=task_status[task_id].get("errors", [])[0] if task_status[task_id].get("errors") else "Completed successfully"
        ))
        
        logging.info(f"Task {task_id}: Processing finished with status: {final_status}. Generated {total_cards_generated} cards across {sections_completed} sections.")

    except asyncio.TimeoutError:
        task_status[task_id]["status"] = "timeout"
        task_status[task_id]["errors"].append(f"Task timed out after {timeout_seconds} seconds during stage: {task_status[task_id]['stage']}")
        task_status[task_id]["updated_at"] = datetime.now(timezone.utc)
        if db:
            update_user_task(db, task_id, UserTaskUpdate(status=TaskStatusEnum.TIMEOUT, error_details=task_status[task_id]["errors"][-1]))
        logging.error(f"Task {task_id}: Timeout during stage: {task_status[task_id]['stage']}")
    except Exception as e:
        error_details = traceback.format_exc()
        logging.error(f"Task {task_id}: Error during stage {task_status[task_id]['stage']}: {e}", exc_info=True)
        task_status[task_id]["status"] = "failed"
        task_status[task_id]["errors"].append(f"Error during {task_status[task_id]['stage']}: {str(e)}")
        task_status[task_id]["error_details"] = error_details
        task_status[task_id]["updated_at"] = datetime.now(timezone.utc)
        if db:
            update_user_task(db, task_id, UserTaskUpdate(status=TaskStatusEnum.FAILED, error_details=error_details))
    finally:
        if db:
            db.close()
        task_status[task_id]["end_time"] = time.time() 