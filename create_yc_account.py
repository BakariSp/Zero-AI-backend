from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.users.crud import create_user, update_user_subscription
from app.users.schemas import UserCreate
from app.utils.security import pwd_context
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_yc_review_account():
    """Create a Y Combinator review account with premium subscription"""
    db = SessionLocal()
    try:
        # Create user data
        user_data = UserCreate(
            email="yc@zero.ai",
            username="yc_review",
            password="wewanttomeetyou",
            full_name="Y Combinator Review",
            is_active=True,
            subscription_type="premium"
        )

        # Create the user
        logger.info("Creating Y Combinator review account...")
        user = create_user(
            db=db,
            user=user_data,
            oauth_provider=None,  # No OAuth for this account
            oauth_id=None,
            profile_picture=None
        )

        # Update subscription to premium with 1 year expiry
        logger.info("Setting up premium subscription...")
        updated_user = update_user_subscription(
            db=db,
            user_id=user.id,
            subscription_type="premium",
            promotion_code=None,
            expiry_days=365  # 1 year subscription
        )

        logger.info(f"Successfully created Y Combinator review account:")
        logger.info(f"User ID: {updated_user.id}")
        logger.info(f"Email: {updated_user.email}")
        logger.info(f"Username: {updated_user.username}")
        logger.info(f"Subscription: {updated_user.subscription_type}")
        logger.info(f"Subscription Expiry: {updated_user.subscription_expiry_date}")

        return updated_user

    except Exception as e:
        logger.error(f"Error creating Y Combinator review account: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    try:
        user = create_yc_review_account()
        print("\nAccount created successfully!")
        print(f"Email: {user.email}")
        print(f"Password: yc@zero / wewanttomeetyou")
        print(f"Subscription: {user.subscription_type}")
        print(f"Expires: {user.subscription_expiry_date}")
    except Exception as e:
        print(f"\nError: {str(e)}")
        exit(1) 