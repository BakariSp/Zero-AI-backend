import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
import asyncio
import time
from datetime import datetime, timedelta

from app.db import SessionLocal
from app.services.learning_path_planner import LearningPathPlannerService
from app.models import LearningPath, User
from app.learning_paths.crud import get_learning_path
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
        import traceback
        error_details = traceback.format_exc()
        logging.error(f"Error in background card generation: {e}")
        logging.error(f"Traceback: {error_details}")
        task_status[task_id]["status"] = "failed"
        task_status[task_id]["errors"].append(str(e))
        task_status[task_id]["error_details"] = error_details
    finally:
        db.close()

def update_task_progress(task_id: str, completed: int):
    """更新任务进度"""
    if task_id in task_status:
        total = task_status[task_id]["total"]
        if total > 0:
            progress = min(int((completed / total) * 100), 100)
            task_status[task_id]["progress"] = progress
            task_status[task_id]["completed"] = completed

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