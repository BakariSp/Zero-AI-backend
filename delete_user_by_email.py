#!/usr/bin/env python
"""
Script to delete a user from the database by their email address.
This is useful for removing test accounts or for administrative purposes.

Usage:
    python delete_user_by_email.py user@example.com

Confirmation will be required before deletion.
"""

import sys
import os
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import User, UserDailyUsage, UserTermsAcceptance, UserLearningPath, UserCourse, UserSection, DailyLog

def delete_user_by_email(email: str, confirm: bool = False) -> bool:
    """
    Delete a user from the database by their email address.
    
    Args:
        email: The email address of the user to delete
        confirm: If True, will delete without confirmation prompt
        
    Returns:
        bool: True if user was deleted, False otherwise
    """
    db = SessionLocal()
    try:
        # Find the user by email
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"No user found with email: {email}")
            return False
        
        # Display user information
        print(f"Found user: {user.username} (ID: {user.id}, Email: {user.email})")
        
        # Confirm deletion
        if not confirm:
            confirmation = input("Are you sure you want to delete this user? This action cannot be undone. (y/n): ")
            if confirmation.lower() not in ["y", "yes"]:
                print("Deletion canceled.")
                return False
                
        user_id = user.id
        
        # Delete all related records before deleting the user
        # We need to delete these manually because some might not have CASCADE set up correctly
        
        # First, delete terms acceptance records
        terms_count = db.query(UserTermsAcceptance).filter(UserTermsAcceptance.user_id == user_id).delete()
        print(f"Deleted {terms_count} terms acceptance records")
        
        # Delete daily usage records
        daily_usage_count = db.query(UserDailyUsage).filter(UserDailyUsage.user_id == user_id).delete()
        print(f"Deleted {daily_usage_count} daily usage records")
        
        # Delete user learning paths
        learning_paths_count = db.query(UserLearningPath).filter(UserLearningPath.user_id == user_id).delete()
        print(f"Deleted {learning_paths_count} learning path records")
        
        # Delete user course records
        courses_count = db.query(UserCourse).filter(UserCourse.user_id == user_id).delete()
        print(f"Deleted {courses_count} course records")
        
        # Delete user section records
        sections_count = db.query(UserSection).filter(UserSection.user_id == user_id).delete()
        print(f"Deleted {sections_count} section records")
        
        # Delete daily logs
        logs_count = db.query(DailyLog).filter(DailyLog.user_id == user_id).delete()
        print(f"Deleted {logs_count} daily log records")
        
        # Commit these deletions to avoid foreign key issues
        db.commit()
        
        # Now delete the user
        db.delete(user)
        db.commit()
        
        print(f"User {email} has been successfully deleted.")
        return True
        
    except SQLAlchemyError as e:
        db.rollback()
        print(f"Database error: {str(e)}")
        return False
    except Exception as e:
        print(f"Error: {str(e)}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    # Check if email is provided as command line argument
    if len(sys.argv) < 2:
        print("Please provide an email address as an argument.")
        print("Usage: python delete_user_by_email.py user@example.com")
        sys.exit(1)
    
    email = sys.argv[1]
    
    # Check for --force flag
    force = "--force" in sys.argv
    
    # Execute deletion
    success = delete_user_by_email(email, confirm=force)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1) 