from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import User, UserTermsAcceptance
import sys

def test_terms_acceptance():
    """
    Test the UserTermsAcceptance model by creating a record and querying it.
    """
    db = SessionLocal()
    try:
        # First, get a test user
        test_user = db.query(User).first()
        if not test_user:
            print("No users found in database. Please create a user first.")
            return

        # Create a terms acceptance record
        terms_version = "v1.0"
        ip_address = "127.0.0.1"
        
        terms_acceptance = UserTermsAcceptance(
            user_id=test_user.id,
            terms_version=terms_version,
            ip_address=ip_address
        )
        
        db.add(terms_acceptance)
        db.commit()
        db.refresh(terms_acceptance)
        
        print(f"Created terms acceptance record with ID: {terms_acceptance.id}")
        
        # Query the record back
        stored_record = db.query(UserTermsAcceptance).filter(
            UserTermsAcceptance.user_id == test_user.id,
            UserTermsAcceptance.terms_version == terms_version
        ).first()
        
        if stored_record:
            print(f"Successfully found record: User ID {stored_record.user_id} accepted terms version {stored_record.terms_version} at {stored_record.signed_at} from IP {stored_record.ip_address}")
        else:
            print("Failed to retrieve the created record!")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    test_terms_acceptance() 