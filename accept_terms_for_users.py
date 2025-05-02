#!/usr/bin/env python
"""
Script to accept terms of service for users in the database.
This is useful for migrating existing users, or for administrative purposes.

Usage:
    # Accept terms for all users
    python accept_terms_for_users.py --all
    
    # Accept terms for a specific user by email
    python accept_terms_for_users.py --email user@example.com
    
    # Specify terms version (default is v1.0)
    python accept_terms_for_users.py --all --version v1.1
    
    # Force acceptance without confirmation
    python accept_terms_for_users.py --all --force
"""

import sys
import os
import argparse
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import User, UserTermsAcceptance

def accept_terms_for_user(db: Session, user_id: int, terms_version: str, ip_address: str = "0.0.0.0") -> bool:
    """
    Create a terms acceptance record for a user.
    
    Args:
        db: Database session
        user_id: The ID of the user
        terms_version: Version of the terms being accepted
        ip_address: IP address (default is "0.0.0.0" for script-generated acceptances)
        
    Returns:
        bool: True if record was created successfully, False otherwise
    """
    try:
        # Check if user already has accepted this version
        existing = db.query(UserTermsAcceptance).filter(
            UserTermsAcceptance.user_id == user_id,
            UserTermsAcceptance.terms_version == terms_version
        ).first()
        
        if existing:
            print(f"User ID {user_id} has already accepted terms version {terms_version} at {existing.signed_at}")
            return True
        
        # Create new acceptance record
        acceptance = UserTermsAcceptance(
            user_id=user_id,
            terms_version=terms_version,
            ip_address=ip_address
        )
        
        db.add(acceptance)
        db.commit()
        
        print(f"User ID {user_id} has accepted terms version {terms_version}")
        return True
        
    except SQLAlchemyError as e:
        db.rollback()
        print(f"Database error for user ID {user_id}: {str(e)}")
        return False
    except Exception as e:
        print(f"Error for user ID {user_id}: {str(e)}")
        return False

def accept_terms_for_all_users(terms_version: str, force: bool = False) -> bool:
    """
    Create terms acceptance records for all users in the database.
    
    Args:
        terms_version: Version of the terms being accepted
        force: If True, will proceed without confirmation
        
    Returns:
        bool: True if successful for all users, False if any failed
    """
    db = SessionLocal()
    try:
        # Get all users
        users = db.query(User).all()
        
        if not users:
            print("No users found in the database.")
            return False
        
        print(f"Found {len(users)} users in the database.")
        
        # Confirm operation
        if not force:
            confirmation = input(f"Are you sure you want to accept terms version {terms_version} for ALL {len(users)} users? (y/n): ")
            if confirmation.lower() not in ["y", "yes"]:
                print("Operation canceled.")
                return False
        
        # Process each user
        success_count = 0
        fail_count = 0
        
        for user in users:
            if accept_terms_for_user(db, user.id, terms_version):
                success_count += 1
            else:
                fail_count += 1
        
        print(f"Operation completed: {success_count} successful, {fail_count} failed")
        return fail_count == 0
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return False
    finally:
        db.close()

def accept_terms_for_email(email: str, terms_version: str, force: bool = False) -> bool:
    """
    Create a terms acceptance record for a user identified by email.
    
    Args:
        email: Email address of the user
        terms_version: Version of the terms being accepted
        force: If True, will proceed without confirmation
        
    Returns:
        bool: True if successful, False otherwise
    """
    db = SessionLocal()
    try:
        # Find user by email
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"No user found with email: {email}")
            return False
        
        print(f"Found user: {user.username} (ID: {user.id}, Email: {user.email})")
        
        # Confirm operation
        if not force:
            confirmation = input(f"Accept terms version {terms_version} for this user? (y/n): ")
            if confirmation.lower() not in ["y", "yes"]:
                print("Operation canceled.")
                return False
        
        # Accept terms for the user
        return accept_terms_for_user(db, user.id, terms_version)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Accept terms of service for users.")
    
    # Define mutually exclusive group for target selection
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument("--all", action="store_true", help="Apply to all users")
    target_group.add_argument("--email", type=str, help="Email of specific user")
    
    # Other arguments
    parser.add_argument("--version", type=str, default="v1.0", help="Terms version (default: v1.0)")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompts")
    
    args = parser.parse_args()
    
    # Execute the appropriate function based on arguments
    if args.all:
        success = accept_terms_for_all_users(args.version, args.force)
    else:
        success = accept_terms_for_email(args.email, args.version, args.force)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1) 