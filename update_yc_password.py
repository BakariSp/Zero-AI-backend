from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.users.crud import get_user_by_email, update_user
from app.utils.security import pwd_context
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_yc_password():
    """Update the Y Combinator review account's password"""
    db = SessionLocal()
    try:
        # Find the user by email
        email = "yc@zero.ai"
        logger.info(f"Looking up user with email: {email}")
        user = get_user_by_email(db, email)
        
        if not user:
            raise Exception(f"User with email {email} not found")
            
        # Hash the new password
        new_password = "excitedtomeetyou"
        hashed_password = pwd_context.hash(new_password)
        
        # Update the user's password
        logger.info("Updating password...")
        updated_user = update_user(
            db=db,
            user_id=user.id,
            user_data={"hashed_password": hashed_password}
        )
        
        logger.info("Successfully updated password for Y Combinator review account")
        return updated_user

    except Exception as e:
        logger.error(f"Error updating password: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    try:
        user = update_yc_password()
        print("\nPassword updated successfully!")
        print(f"Email: {user.email}")
        print(f"New password: excitedtomeetyou")
    except Exception as e:
        print(f"\nError: {str(e)}")
        exit(1) 