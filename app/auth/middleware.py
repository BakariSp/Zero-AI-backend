import json
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.auth.supabase import verify_supabase_token
from app.users.crud import get_user_by_email, create_user
from app.users.schemas import UserCreate

# Configure logging
logger = logging.getLogger(__name__)

class SupabaseAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle Supabase authentication.
    
    This middleware will:
    1. Extract Supabase JWT from Authorization header
    2. Verify the token using Supabase APIs
    3. Get the user from our database or create if they don't exist
    4. Attach the user to the request state for use in routes
    """
    
    async def dispatch(self, request: Request, call_next):
        # Add request path to the request state for debugging
        request.state.original_path = request.url.path
        logger.info(f"SupabaseAuthMiddleware processing request for: {request.url.path}")
        
        # Skip authentication for OPTIONS requests
        if request.method == "OPTIONS":
            logger.info(f"Skipping authentication for OPTIONS request to: {request.url.path}")
            return await call_next(request)
        
        # Log the requested path
        logger.info(f"Processing request with Supabase middleware: {request.url.path}")
        
        # Extract Authorization header for debugging
        auth_header = request.headers.get("Authorization")
        if auth_header:
            logger.info(f"Authorization header found for {request.url.path}")
            if not auth_header.startswith("Bearer "):
                logger.warning(f"Authorization header does not start with 'Bearer ' for {request.url.path}")
        else:
            logger.info(f"No Authorization header for {request.url.path}")
        
        # Initialize request state for user
        request.state.user = None
        request.state.supabase_user = None
        
        # Get Supabase user data from token
        supabase_user = await verify_supabase_token(request)
        if supabase_user:
            logger.info(f"Supabase authentication successful for {request.url.path}")
            logger.info(f"Supabase user ID: {supabase_user.get('id')}, email: {supabase_user.get('email')}")
            
            # Store the Supabase user data in request state
            request.state.supabase_user = supabase_user
            
            # Check if we need to synchronize with our database
            # Only do this for routes that require user data beyond just authentication
            # This avoids database calls for static resources or public endpoints
            if self._should_sync_with_database(request.url.path):
                # Get user from database
                db = SessionLocal()
                try:
                    email = supabase_user.get("email")
                    if email:
                        logger.info(f"Looking up user with email {email} in database")
                        user = get_user_by_email(db, email=email)
                        if user:
                            # Store the user in request state
                            request.state.user = user
                            logger.info(f"Found user in database for {email} (User ID: {user.id})")
                            
                            # IMPORTANT: Add debug prints to verify the state
                            logger.info(f"Verified request.state.user is set to User object ID: {user.id} at middleware step")
                        else:
                            # User doesn't exist in our database yet - create the user automatically
                            logger.info(f"User with email {email} authenticated via Supabase but not found in database")
                            logger.info(f"Auto-creating user account for {email}")
                            
                            # Generate username from email if not provided
                            username = supabase_user.get("username") or email.split("@")[0]
                            
                            # Extract name from Supabase user data if available
                            full_name = supabase_user.get("user_metadata", {}).get("full_name")
                            if not full_name:
                                full_name = supabase_user.get("name") or ""
                            
                            # Create user data
                            user_data = UserCreate(
                                email=email,
                                username=username,
                                password="",  # No password for Supabase users
                                full_name=full_name,
                                is_active=True
                            )
                            
                            try:
                                # Create the user in the database
                                new_user = create_user(
                                    db=db,
                                    user=user_data,
                                    oauth_provider="supabase",
                                    oauth_id=supabase_user.get("id"),
                                    profile_picture=supabase_user.get("avatar_url")
                                )
                                
                                # IMPORTANT: Explicitly commit changes to make sure they're persisted
                                db.commit()
                                
                                # Verify the user was created
                                check_user = get_user_by_email(db, email=email)
                                if check_user:
                                    logger.info(f"Verified user was created with ID: {check_user.id}")
                                else:
                                    logger.error(f"User creation was not persisted for {email}")
                                
                                # Store the new user in request state
                                request.state.user = new_user
                                logger.info(f"Successfully created user account for {email} (User ID: {new_user.id})")
                                
                                # Verify the state again
                                logger.info(f"Verified request.state.user is set to new User object ID: {new_user.id}")
                            except Exception as e:
                                db.rollback()  # Ensure we rollback on error
                                logger.error(f"Error creating user account for {email}: {str(e)}")
                    else:
                        logger.warning("Supabase user data missing email")
                except Exception as e:
                    logger.error(f"Database error in SupabaseAuthMiddleware: {str(e)}")
                    db.rollback()  # Ensure we rollback on error
                finally:
                    # Always close the DB session
                    db.close()
        else:
            # For legacy purposes, try to handle both Supabase and JWT tokens
            # This code will be removed when fully migrated to Supabase
            if auth_header and auth_header.startswith("Bearer "):
                logger.info(f"Supabase authentication failed, token might be legacy JWT: {request.url.path}")
        
        # Log user state before proceeding
        if hasattr(request.state, "user") and request.state.user is not None:
            if isinstance(request.state.user, dict):
                logger.info(f"Request proceeding with user dict: {request.state.user.get('email', 'unknown')}")
            else:
                logger.info(f"Request proceeding with user object, ID: {request.state.user.id}, Email: {request.state.user.email}")
                # Store user ID in a debug header for tracing
                user_id = getattr(request.state.user, "id", "unknown")
                request.state.debug_user_id = str(user_id)
                
                # CRITICAL FIX: Ensure we have a properly initialized user object
                # Sometimes the user object can get lost in serialization between middleware and route
                try:
                    # Test serialization to ensure it's a valid object
                    from fastapi.encoders import jsonable_encoder
                    user_json = jsonable_encoder(request.state.user)
                    logger.info(f"Successfully serialized user object in middleware")
                except Exception as e:
                    logger.error(f"Error serializing user object in middleware: {str(e)}")
                    # Since there was an error, let's create a fresh copy of the user object
                    from app.models import User
                    try:
                        original_user = request.state.user
                        # Create a copy with just the essential attributes
                        request.state.user = User(
                            id=original_user.id,
                            email=original_user.email,
                            username=original_user.username,
                            full_name=original_user.full_name,
                            is_active=original_user.is_active,
                            subscription_type=getattr(original_user, "subscription_type", "free")
                        )
                        logger.info(f"Created fresh copy of user object in middleware: {request.state.user.id}")
                    except Exception as e:
                        logger.error(f"Failed to create fresh user copy: {str(e)}")
        else:
            logger.info(f"Request proceeding without user object in state")
            
        # Process the request
        response = await call_next(request)
        
        # Add debug header to the response
        if hasattr(request.state, "debug_user_id"):
            response.headers["X-Debug-User-ID"] = request.state.debug_user_id
            
        # Log when unauthorized responses occur
        if response.status_code == 401:
            # Get detailed info about why we got a 401
            has_user = hasattr(request.state, "user") and request.state.user is not None
            has_supabase = hasattr(request.state, "supabase_user") and request.state.supabase_user is not None
            
            logger.warning(f"Unauthorized access (401) for path: {request.url.path}, has user: {has_user}, has supabase: {has_supabase}")
            
            # Check if user was lost during processing
            if has_user:
                if isinstance(request.state.user, dict):
                    logger.error(f"User data was present but response is 401. User dict: {request.state.user}")
                else:
                    logger.error(f"User object was present (ID: {request.state.user.id}) but response is 401")
                    
                # Add an additional header to show this was a middleware detection issue
                response.headers["X-Auth-Failure-Reason"] = "user_object_lost"
                
                # Just log the error but don't override the status code
                if response.status_code == 401 and not request.url.path.endswith("/token"):
                    logger.warning(f"Route returned 401 for path {request.url.path} even though user object was present")
        
        return response
    
    def _should_sync_with_database(self, path: str) -> bool:
        """
        Determine if we should sync with our database for this request.
        
        Args:
            path: The request path
            
        Returns:
            bool: True if we should sync with database, False otherwise
        """
        # List of paths that don't need database synchronization
        # For example, static files, health checks, etc.
        skip_paths = [
            "/static/",
            "/favicon.ico",
            "/health",
            "/api/token"  # Skip the token endpoint to avoid circular references
        ]
        
        # Check if path starts with any of the skip paths
        for skip_path in skip_paths:
            if path.startswith(skip_path):
                return False
        
        # For all other paths, sync with database
        return True 