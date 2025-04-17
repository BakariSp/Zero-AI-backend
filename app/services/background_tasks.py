import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
import asyncio
import time
from datetime import datetime, timedelta
import traceback

from app.db import SessionLocal
from app.services.learning_path_planner import LearningPathPlannerService
from app.services.ai_generator import extract_learning_goals
from app.models import LearningPath, User
from app.learning_paths.crud import get_learning_path, assign_learning_path_to_user
from app.users.crud import get_user

# 全局任务状态跟踪
task_status = {}

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
        "status": "starting",
        "stage": "initializing",
        "progress": 0,
        "total_cards": 0,
        "cards_completed": 0,
        "learning_path_id": None,
        "errors": [],
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
        logging.info(f"Task {task_id}: Generating path structure...")
        # Note: generate_complete_learning_path already creates LP, Courses, Sections in DB
        # and assigns to user if user_id is provided.
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

        # --- Stage 3: Generate Cards ---
        task_status[task_id]["stage"] = "generating_cards"
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
        logging.info(f"Task {task_id}: Successfully completed full learning path generation.")

    except asyncio.TimeoutError:
        elapsed_time = time.time() - start_time
        task_status[task_id]["status"] = "timeout"
        task_status[task_id]["errors"].append(f"Task timed out after {elapsed_time:.2f} seconds (limit: {timeout_seconds}s)")
        logging.error(f"Task {task_id}: Generation timed out.")
    except Exception as e:
        error_details = traceback.format_exc()
        logging.error(f"Task {task_id}: Error during generation: {e}\n{error_details}")
        task_status[task_id]["status"] = "failed"
        task_status[task_id]["errors"].append(f"Error in stage '{task_status[task_id]['stage']}': {str(e)}")
        task_status[task_id]["error_details"] = error_details # Optional: include traceback for debugging
    finally:
        if db:
            db.close()
        task_status[task_id]["end_time"] = time.time()

def update_task_progress(task_id: str, completed: int):
    """更新任务进度"""
    if task_id in task_status:
        task_status[task_id]["completed"] = completed
        total = task_status[task_id].get("total", 0)
        if total > 0:
            task_status[task_id]["progress"] = int((completed / total) * 100)

def get_task_status(task_id: str) -> Dict[str, Any]:
    """获取任务状态"""
    if task_id in task_status:
        return task_status[task_id]
    return {"status": "not_found"}

def schedule_learning_path_generation(
    background_tasks: BackgroundTasks,
    db: Session,
    learning_path_structure: Dict[str, Any],
    learning_path_id: int,
    user_id: int
):
    """调度学习路径卡片生成任务"""
    background_tasks.add_task(
        generate_cards_background,
        learning_path_id=learning_path_id,
        user_id=user_id,
        learning_path_structure=learning_path_structure
    )
    
    # 创建任务ID并返回
    task_id = f"card_gen_{learning_path_id}_{user_id}"
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
    prompt: str,
    user_id: int
) -> str:
    """Schedules the full learning path generation and returns a task ID."""
    # Generate a unique task ID (consider using UUID)
    task_id = f"full_path_gen_{user_id}_{int(time.time())}"
    logging.info(f"Scheduling full learning path generation task with ID: {task_id}")
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

@task_router.get("/tasks/{task_id}/status", response_model=Dict[str, Any])
async def get_task_status(task_id: str):
    """Retrieve the status of a background task."""
    status_info = task_status.get(task_id)
    if not status_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return status_info 