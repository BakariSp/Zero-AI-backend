"""
Cleanup tasks for the application
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

from app.models import User

logger = logging.getLogger(__name__)

def cleanup_inactive_guest_users(db: Session, days_threshold: int = 30) -> int:
    """
    Delete guest users that have been inactive for more than the specified number of days
    
    Args:
        db: Database session
        days_threshold: Number of days of inactivity before guest users are deleted
        
    Returns:
        Number of guest users deleted
    """
    # Calculate the cutoff date
    cutoff_date = datetime.utcnow() - timedelta(days=days_threshold)
    
    # Find guest users to delete
    guest_users_to_delete = db.query(User).filter(
        User.is_guest == True,
        User.merged_into_user_id.is_(None),  # Not already merged
        User.last_active_at < cutoff_date
    ).all()
    
    count = len(guest_users_to_delete)
    logger.info(f"Found {count} inactive guest users to delete (inactive for > {days_threshold} days)")
    
    # Delete each user and their data
    for user in guest_users_to_delete:
        try:
            # Log the user being deleted
            logger.info(f"Deleting inactive guest user {user.id} (last active: {user.last_active_at})")
            
            # Delete the user
            db.delete(user)
            
        except Exception as e:
            logger.error(f"Error deleting guest user {user.id}: {str(e)}")
            count -= 1  # Reduce the count for failed deletions
    
    # Commit the transaction
    db.commit()
    
    logger.info(f"Successfully deleted {count} inactive guest users")
    return count 