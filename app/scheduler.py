"""
Scheduler for running background tasks at regular intervals
"""
import asyncio
import logging
from datetime import datetime
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from app.db import get_db, SessionLocal
from app.backend_tasks.cleanup_tasks import cleanup_inactive_guest_users

logger = logging.getLogger(__name__)

# Create a scheduler
scheduler = AsyncIOScheduler()

async def cleanup_guest_users_task():
    """
    Background task to clean up inactive guest users
    """
    logger.info("Running guest user cleanup task")
    
    # Get a database session
    db = SessionLocal()
    
    try:
        # Run the cleanup task
        deleted_count = cleanup_inactive_guest_users(db, days_threshold=30)
        logger.info(f"Guest user cleanup completed: {deleted_count} users deleted")
    
    except Exception as e:
        logger.error(f"Error in guest user cleanup task: {str(e)}")
    
    finally:
        # Close the database session
        db.close()

def init_scheduler():
    """
    Initialize and start the scheduler
    """
    # Add the guest user cleanup task to run daily at 3 AM
    scheduler.add_job(
        cleanup_guest_users_task,
        CronTrigger(hour=3, minute=0),  # Run at 3:00 AM every day
        id="cleanup_guest_users",
        replace_existing=True
    )
    
    # Start the scheduler
    scheduler.start()
    logger.info("Scheduler started with the following jobs:")
    for job in scheduler.get_jobs():
        logger.info(f" - {job.id}: {job.trigger}")

def start_scheduler():
    """
    Start the scheduler when the application starts
    """
    init_scheduler()
    logger.info("Scheduler initialized and started") 