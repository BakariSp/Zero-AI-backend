from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import timedelta, datetime, date
from pydantic import BaseModel, EmailStr, validator
from starlette.responses import RedirectResponse, JSONResponse
import os
import base64
import json
import logging
import traceback
from fastapi.encoders import jsonable_encoder

from app.db import SessionLocal
from app.auth.jwt import (
    create_access_token, 
    get_current_active_user,
    get_current_user,
    get_current_user_optional,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    Token
)
from app.auth.oauth import oauth, get_oauth_user
from app.auth.supabase import get_current_active_supabase_user, verify_supabase_token
from app.users.crud import (
    get_user, 
    get_users, 
    get_user_by_email,
    get_user_by_username,
    update_user,
    get_subscription_limits,
    check_subscription_limits,
    update_user_subscription as update_user_subscription_crud,
    create_user
)
from app.models import User
from app.users import schemas
from app.user_daily_usage.crud import get_or_create_daily_usage
from app.users import crud
from app.users.schemas import UserCreate, UserResponse, UserUpdate, UserInterests, TermsAcceptanceCreate, TermsAcceptanceResponse

router = APIRouter()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        # Ping the database to ensure connection is active
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        yield db
    except Exception as e:
        logging.error(f"Database connection error: {str(e)}")
        # Try to create a new connection
        db.close()
        db = SessionLocal()
        yield db
    finally:
        db.close()

# Create an alternative database session for diagnostic use
def get_fresh_db():
    """Create a fresh database connection for diagnostics"""
    from sqlalchemy import text
    db = SessionLocal()
    try:
        # Test the connection
        db.execute(text("SELECT 1"))
        return db
    except Exception as e:
        logging.error(f"Fresh DB connection error: {str(e)}")
        db.close()
        # Try one more time
        db = SessionLocal()
        return db

# Dependency to get the current user with support for both JWT and Supabase auth
async def get_current_user_unified(
    request: Request,
    jwt_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Get the current user with unified authentication support (JWT and Supabase).
    This dependency is the primary auth entry point that combines both auth methods.
    
    Returns:
        User object if authenticated, None otherwise
    """
    path = request.url.path
    logging.info(f"[DEBUG] get_current_user_unified called for path: {path}")
    
    # CRITICAL FIX: Check request.state.user FIRST and return immediately if it's a User object
    # This bypasses all the problematic dependency chain issues
    if hasattr(request.state, "user") and isinstance(request.state.user, User):
        logging.info(f"[DEBUG] IMMEDIATE RETURN: Found User object in request.state.user with ID: {request.state.user.id}")
        return request.state.user
    
    # Add detailed debugging at the very start
    logging.info(f"[DEBUG] === DETAILED REQUEST STATE DEBUG ===")
    logging.info(f"[DEBUG] hasattr(request.state, 'user'): {hasattr(request.state, 'user')}")
    if hasattr(request.state, 'user'):
        logging.info(f"[DEBUG] request.state.user is None: {request.state.user is None}")
        logging.info(f"[DEBUG] type(request.state.user): {type(request.state.user)}")
        if request.state.user is not None:
            if isinstance(request.state.user, User):
                logging.info(f"[DEBUG] request.state.user.id: {request.state.user.id}")
                logging.info(f"[DEBUG] request.state.user.email: {request.state.user.email}")
            elif isinstance(request.state.user, dict):
                logging.info(f"[DEBUG] request.state.user dict keys: {request.state.user.keys()}")
    logging.info(f"[DEBUG] jwt_user from dependency: {jwt_user}")
    logging.info(f"[DEBUG] === END DETAILED DEBUG ===")
    
    # Handle dict user from request.state
    if hasattr(request.state, "user") and isinstance(request.state.user, dict):
        # Legacy dictionary format, try to convert to a User object
        try:
            user_email = request.state.user.get('email')
            logging.info(f"[DEBUG] User from request.state.user is a dict with email: {user_email}")
            if user_email:
                # Try with current db session - but catch any JWT auth errors
                try:
                    db_user = get_user_by_email(db, email=user_email)
                    if db_user:
                        logging.info(f"[DEBUG] Successfully retrieved user from DB by email: {db_user.id}")
                        return db_user
                except Exception as db_error:
                    # If DB query fails due to auth issues, create a temporary user
                    logging.warning(f"[DEBUG] DB lookup failed due to: {str(db_error)}, creating temporary user")
                    # Create a temporary user from the dict data
                    temp_user = User(
                        id=request.state.user.get("id", 0),
                        email=user_email,
                        username=user_email.split("@")[0],
                        full_name=request.state.user.get("full_name", ""),
                        is_active=True,
                        oauth_provider="supabase",
                        subscription_type="free"
                    )
                    return temp_user
        except Exception as e:
            logging.error(f"[DEBUG] Error converting legacy user dict to User: {str(e)}")
    
    # If no user in request.state.user, check for Supabase user data
    if hasattr(request.state, "supabase_user") and request.state.supabase_user is not None:
        logging.info(f"[DEBUG] Found Supabase user data in request.state.supabase_user")
        email = request.state.supabase_user.get("email")
        if email:
            logging.info(f"[DEBUG] Looking up user with email {email} in database")
            try:
                db_user = get_user_by_email(db, email=email)
                if db_user:
                    logging.info(f"[DEBUG] Found user in database for email {email}: {db_user.id}")
                    return db_user
            except Exception as db_error:
                logging.warning(f"[DEBUG] DB lookup failed for Supabase user due to: {str(db_error)}")
            
            # If DB lookup fails or user not found, create temporary user
            logging.info(f"[DEBUG] Creating temporary user for Supabase email: {email}")
            supabase_data = request.state.supabase_user
            temp_user = User(
                id=supabase_data.get("id", 0),
                email=email,
                username=email.split("@")[0],
                full_name=supabase_data.get("name", ""),
                is_active=True,
                oauth_provider="supabase",
                subscription_type="free"
            )
            return temp_user
    
    # Fall back to JWT auth only if no middleware user data
    try:
        if jwt_user is not None:
            logging.info(f"[DEBUG] Using user from JWT auth: {jwt_user.id}")
            return jwt_user
    except Exception as e:
        logging.warning(f"[DEBUG] JWT auth failed: {str(e)}")
    
    # No valid user found
    logging.warning(f"[DEBUG] No authenticated user found for {request.url.path}")
    return None  # Return None instead of raising an exception, let the active user dependency handle it

# Dependency to get the current active user with unified auth
async def get_current_active_user_unified(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_unified),
    db: Session = Depends(get_db)
):
    """
    Check if the current user is active.
    Works with both JWT and Supabase authentication.
    """
    path = request.url.path
    logging.info(f"[DEBUG] get_current_active_user_unified called for path: {path}")
    
    # For OPTIONS requests, skip auth check
    if request.method == "OPTIONS":
        logging.info("[DEBUG] OPTIONS request detected, skipping auth check")
        return None
    
    # CRITICAL FIX: Check request.state.user FIRST and use it directly if it's a User object
    if hasattr(request.state, "user") and isinstance(request.state.user, User):
        logging.info(f"[DEBUG] IMMEDIATE RETURN from get_current_active_user_unified: Using User object from request.state: {request.state.user.id}")
        # Check if the user is active
        if not request.state.user.is_active:
            logging.error(f"[DEBUG] User {request.state.user.id} is not active")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        return request.state.user
    
    # Immediate debug of the current_user parameter
    logging.info(f"[DEBUG] === ACTIVE USER UNIFIED DEBUG ===")
    logging.info(f"[DEBUG] current_user parameter type: {type(current_user)}")
    logging.info(f"[DEBUG] current_user is None: {current_user is None}")
    if current_user is not None:
        logging.info(f"[DEBUG] current_user.id: {current_user.id}")
        logging.info(f"[DEBUG] current_user.email: {current_user.email}")
    
    # Check request.state directly
    logging.info(f"[DEBUG] Has user in request.state: {hasattr(request.state, 'user')}")
    if hasattr(request.state, "user"):
        logging.info(f"[DEBUG] Type of request.state.user: {type(request.state.user)}")
        if isinstance(request.state.user, User):
            logging.info(f"[DEBUG] request.state.user is a User object with ID: {request.state.user.id}")
    logging.info(f"[DEBUG] === END ACTIVE USER DEBUG ===")
        
    # If we have a current_user from the dependency, use it
    if current_user is not None:
        # Check if the user is active
        if not current_user.is_active:
            logging.error(f"[DEBUG] User {current_user.id} is not active")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        logging.info(f"[DEBUG] User {current_user.id} is authenticated and active for {path}")
        return current_user
    
    # If current_user is None but we have user data in request.state, try to use it
    if hasattr(request.state, "user") and request.state.user is not None:
        logging.info("[DEBUG] Retrieving user from request.state that was lost in the dependency chain")
        
        # If it's a dict, create a temporary user
        if isinstance(request.state.user, dict) and 'email' in request.state.user:
            email = request.state.user.get('email')
            logging.info(f"[DEBUG] Creating temporary user from request.state dict with email: {email}")
            temp_user = User(
                id=request.state.user.get("id", 0),
                email=email,
                username=email.split("@")[0],
                full_name=request.state.user.get("full_name", ""),
                is_active=True,
                oauth_provider="supabase",
                subscription_type="free"
            )
            return temp_user
    
    # Check for Supabase user data in request state
    if hasattr(request.state, "supabase_user") and request.state.supabase_user is not None:
        email = request.state.supabase_user.get("email")
        if email:
            logging.info(f"[DEBUG] Creating temporary user from Supabase data with email: {email}")
            supabase_data = request.state.supabase_user
            temp_user = User(
                id=supabase_data.get("id", 0),
                email=email,
                username=email.split("@")[0],
                full_name=supabase_data.get("name", ""),
                is_active=True,
                oauth_provider="supabase",
                subscription_type="free"
            )
            return temp_user
    
    # If we still don't have a user at this point, authentication has failed
    logging.warning(f"[DEBUG] All authentication fallbacks failed for {request.url.path}")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"}
    )

# User profile routes
@router.options("/users/me")
async def options_users_me(request: Request):
    # This is a dedicated OPTIONS handler that will immediately return a 200 OK
    # with no response model validation
    response = Response(status_code=200)
    
    # Get origin from request headers
    origin = request.headers.get("Origin", "http://localhost:3000")
    
    # Set CORS headers
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept, Origin, X-Requested-With"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Max-Age"] = "86400"  # 24 hours
    
    return response

@router.get("/users/me", response_model=schemas.UserResponse)
async def read_users_me(
    request: Request, 
    current_user: User = Depends(get_current_active_user_unified)
):
    # Enhanced debugging for this specific endpoint
    logging.info("=== /users/me ENDPOINT DEBUG ===")
    logging.info(f"Request method for /users/me: {request.method}")
    logging.info(f"Authorization header present: {request.headers.get('Authorization') is not None}")
    
    # Check for direct access to user from request.state for debugging
    if hasattr(request.state, "user"):
        logging.info(f"Has user in request.state: {hasattr(request.state, 'user')}")
        user_type = type(request.state.user)
        logging.info(f"Type of request.state.user: {user_type}")
        if isinstance(request.state.user, User):
            logging.info(f"User ID in request.state.user: {request.state.user.id}")
            # CRITICAL FIX: Always use the User object from request.state if it's available
            # This ensures we don't lose the user object due to session issues
            current_user = request.state.user
            logging.info(f"CRITICAL FIX: Using User object from request.state.user: {current_user.id}")
    
    # First and most important check: if we already have a User object from the dependency
    if current_user:
        logging.info(f"Using current_user from dependency: {current_user.id}")
        user_data = jsonable_encoder(current_user)
        response = JSONResponse(content=user_data)
        
        # Add CORS headers directly
        origin = request.headers.get("Origin", "http://localhost:3000")
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
    
    # Fallback 1: Check if we have a user in request state but it wasn't passed through dependency
    if hasattr(request.state, "user") and request.state.user is not None:
        logging.info("Falling back to user from request.state.user")
        
        if isinstance(request.state.user, User):
            logging.info(f"Using User object from request.state.user: {request.state.user.id}")
            user_data = jsonable_encoder(request.state.user)
            response = JSONResponse(content=user_data)
            
            # Add CORS headers
            origin = request.headers.get("Origin", "http://localhost:3000")
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            
            return response
        elif isinstance(request.state.user, dict) and 'email' in request.state.user:
            # Try to convert dict to User model
            email = request.state.user.get('email')
            logging.info(f"Request state user is dict with email: {email}")
            
            # Create a database session
            db = SessionLocal()
            try:
                # Look up the user
                db_user = get_user_by_email(db, email=email)
                if db_user:
                    logging.info(f"Found user in database for email {email}: {db_user.id}")
                    user_data = jsonable_encoder(db_user)
                    response = JSONResponse(content=user_data)
                    
                    # Add CORS headers
                    origin = request.headers.get("Origin", "http://localhost:3000")
                    response.headers["Access-Control-Allow-Origin"] = origin
                    response.headers["Access-Control-Allow-Credentials"] = "true"
                    
                    return response
                else:
                    logging.warning(f"User with email {email} from request.state.user not found in database")
                    
                    # Create temporary user from dict data
                    user_dict = request.state.user
                    temp_user = User(
                        id=user_dict.get("id", 0),
                        email=user_dict.get("email"),
                        username=user_dict.get("username", email.split("@")[0]),
                        full_name=user_dict.get("full_name", ""),
                        is_active=True,
                        oauth_provider=user_dict.get("oauth_provider", "supabase"),
                        subscription_type="free"
                    )
                    
                    user_data = jsonable_encoder(temp_user)
                    response = JSONResponse(content=user_data)
                    
                    # Add CORS headers
                    origin = request.headers.get("Origin", "http://localhost:3000")
                    response.headers["Access-Control-Allow-Origin"] = origin
                    response.headers["Access-Control-Allow-Credentials"] = "true"
                    
                    return response
            finally:
                db.close()
    
    # Fallback 2: Try direct lookup from Supabase data if available
    if hasattr(request.state, "supabase_user") and request.state.supabase_user is not None:
        try:
            email = request.state.supabase_user.get("email")
            if email:
                logging.info(f"Trying direct DB lookup for email: {email}")
                db = SessionLocal()
                try:
                    db_user = get_user_by_email(db, email=email)
                    if db_user:
                        logging.info(f"Successfully looked up user directly: {db_user.id}")
                        user_data = jsonable_encoder(db_user)
                        response = JSONResponse(content=user_data)
                        
                        # Add CORS headers
                        origin = request.headers.get("Origin", "http://localhost:3000")
                        response.headers["Access-Control-Allow-Origin"] = origin
                        response.headers["Access-Control-Allow-Credentials"] = "true"
                        
                        return response
                    else:
                        # Auto-create user
                        logging.info(f"Creating user for authenticated email: {email}")
                        
                        # Get Supabase user data
                        supabase_data = request.state.supabase_user
                        
                        # Generate username from email
                        username = email.split("@")[0]
                        
                        # Create user data
                        user_data = UserCreate(
                            email=email,
                            username=username,
                            password="",  # No password for Supabase users
                            full_name=supabase_data.get("name", ""),
                            is_active=True
                        )
                        
                        try:
                            # Create the user
                            new_user = create_user(
                                db=db,
                                user=user_data,
                                oauth_provider="supabase",
                                oauth_id=supabase_data.get("id"),
                                profile_picture=supabase_data.get("avatar_url", "")
                            )
                            
                            # Commit changes
                            db.commit()
                            
                            logging.info(f"Successfully created user account: {new_user.id}")
                            
                            # Return the new user
                            user_data = jsonable_encoder(new_user)
                            response = JSONResponse(content=user_data)
                            
                            # Add CORS headers
                            origin = request.headers.get("Origin", "http://localhost:3000")
                            response.headers["Access-Control-Allow-Origin"] = origin
                            response.headers["Access-Control-Allow-Credentials"] = "true"
                            
                            return response
                        except Exception as e:
                            db.rollback()
                            logging.error(f"Failed to create user: {str(e)}")
                            
                            # Create temporary user object without DB persistence
                            temp_user = User(
                                id=supabase_data.get("id", 0),
                                email=email,
                                username=username,
                                full_name=supabase_data.get("name", ""),
                                is_active=True,
                                oauth_provider="supabase",
                                oauth_id=supabase_data.get("id"),
                                subscription_type="free"
                            )
                            
                            user_data = jsonable_encoder(temp_user)
                            response = JSONResponse(content=user_data)
                            
                            # Add CORS headers
                            origin = request.headers.get("Origin", "http://localhost:3000")
                            response.headers["Access-Control-Allow-Origin"] = origin
                            response.headers["Access-Control-Allow-Credentials"] = "true"
                            
                            return response
                finally:
                    db.close()
        except Exception as e:
            logging.error(f"Error in direct DB lookup: {str(e)}")
    
    # Final fallback: Direct token verification
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            logging.info("Final attempt: Direct token verification")
            supabase_user = await verify_supabase_token(request)
            if supabase_user and "email" in supabase_user:
                email = supabase_user.get("email")
                logging.info(f"Token verification found email: {email}")
                
                db = SessionLocal()
                try:
                    db_user = get_user_by_email(db, email=email)
                    if db_user:
                        logging.info(f"Found user via direct token verification: {db_user.id}")
                        user_data = jsonable_encoder(db_user)
                        response = JSONResponse(content=user_data)
                        
                        # Add CORS headers
                        origin = request.headers.get("Origin", "http://localhost:3000")
                        response.headers["Access-Control-Allow-Origin"] = origin
                        response.headers["Access-Control-Allow-Credentials"] = "true"
                        
                        return response
                    else:
                        # Auto-create user
                        logging.info(f"Creating user for verified email: {email}")
                        
                        # Generate username from email
                        username = email.split("@")[0]
                        
                        # Create user data
                        user_data = UserCreate(
                            email=email,
                            username=username,
                            password="",  # No password for Supabase users
                            full_name=supabase_user.get("name", ""),
                            is_active=True
                        )
                        
                        try:
                            # Create the user
                            new_user = create_user(
                                db=db,
                                user=user_data,
                                oauth_provider="supabase",
                                oauth_id=supabase_user.get("id"),
                                profile_picture=supabase_user.get("avatar_url", "")
                            )
                            
                            # Commit changes
                            db.commit()
                            
                            logging.info(f"Successfully created user account: {new_user.id}")
                            
                            # Return the new user
                            user_data = jsonable_encoder(new_user)
                            response = JSONResponse(content=user_data)
                            
                            # Add CORS headers
                            origin = request.headers.get("Origin", "http://localhost:3000")
                            response.headers["Access-Control-Allow-Origin"] = origin
                            response.headers["Access-Control-Allow-Credentials"] = "true"
                            
                            return response
                        except Exception as e:
                            db.rollback()
                            logging.error(f"Failed to create user: {str(e)}")
                            
                            # Create temporary user object without DB persistence
                            temp_user = User(
                                id=supabase_user.get("id", 0),
                                email=email,
                                username=username,
                                full_name=supabase_user.get("name", ""),
                                is_active=True,
                                oauth_provider="supabase",
                                oauth_id=supabase_user.get("id"),
                                subscription_type="free"
                            )
                            
                            user_data = jsonable_encoder(temp_user)
                            response = JSONResponse(content=user_data)
                            
                            # Add CORS headers
                            origin = request.headers.get("Origin", "http://localhost:3000")
                            response.headers["Access-Control-Allow-Origin"] = origin
                            response.headers["Access-Control-Allow-Credentials"] = "true"
                            
                            return response
                finally:
                    db.close()
        except Exception as e:
            logging.error(f"Final token verification failed: {str(e)}")
    
    # Absolute last resort - if we have any authentication info, create a temporary user
    if auth_header and auth_header.startswith("Bearer "):
        try:
            # Try to extract something useful from the token
            token = auth_header.split(" ")[1]
            import base64
            import json
            
            # Try to parse JWT parts (this is a best-effort attempt)
            try:
                # Parse JWT payload (second part)
                parts = token.split(".")
                if len(parts) >= 2:
                    # Add padding if needed
                    padded = parts[1] + "=" * (4 - len(parts[1]) % 4) if len(parts[1]) % 4 else parts[1]
                    payload = json.loads(base64.b64decode(padded).decode('utf-8'))
                    
                    if "email" in payload:
                        email = payload["email"]
                        user_id = payload.get("sub", "temp-id")
                        
                        logging.info(f"Created emergency user from token payload: {email}")
                        
                        # Create minimal user
                        temp_user = User(
                            id=user_id,
                            email=email,
                            username=email.split("@")[0],
                            full_name="",
                            is_active=True,
                            subscription_type="free"
                        )
                        
                        user_data = jsonable_encoder(temp_user)
                        response = JSONResponse(content=user_data)
                        
                        # Add CORS headers
                        origin = request.headers.get("Origin", "http://localhost:3000")
                        response.headers["Access-Control-Allow-Origin"] = origin
                        response.headers["Access-Control-Allow-Credentials"] = "true"
                        
                        return response
            except Exception as e:
                logging.error(f"Emergency JWT parsing failed: {str(e)}")
        except Exception as e:
            logging.error(f"Emergency auth attempt failed: {str(e)}")
    
    # If we reach here, authentication has failed
    logging.error("All authentication methods failed for /users/me")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication failed",
        headers={"WWW-Authenticate": "Bearer"}
    )

@router.put("/users/me", response_model=schemas.UserResponse)
async def update_user_me(
    user_update: schemas.UserUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user_unified),
    db: Session = Depends(get_db)
):
    try:
        logging.info(f"=== PUT /users/me ENDPOINT DEBUG ===")
        logging.info(f"Request method: {request.method}")
        logging.info(f"Authorization header present: {request.headers.get('Authorization') is not None}")
        
        # First check: If current_user is None, try to retrieve from request.state
        if current_user is None:
            logging.warning("Current user is None, attempting to recover from request.state")
            
            if hasattr(request.state, "user") and request.state.user is not None:
                logging.info("Found user in request.state.user")
                
                if isinstance(request.state.user, User):
                    logging.info(f"Using User object from request.state.user: {request.state.user.id}")
                    current_user = request.state.user
                elif isinstance(request.state.user, dict) and 'email' in request.state.user:
                    email = request.state.user.get('email')
                    logging.info(f"Looking up user by email from request.state.user dict: {email}")
                    db_user = get_user_by_email(db, email=email)
                    if db_user:
                        logging.info(f"Found user in database for email {email}: {db_user.id}")
                        current_user = db_user
                    else:
                        logging.warning(f"User lookup failed: User with email {email} not found in database")
            
            # Check for Supabase data if we still don't have a user
            if current_user is None and hasattr(request.state, "supabase_user") and request.state.supabase_user is not None:
                email = request.state.supabase_user.get("email")
                if email:
                    logging.info(f"Looking up user with email {email} from Supabase data")
                    db_user = get_user_by_email(db, email=email)
                    if db_user:
                        logging.info(f"Found user in database: {db_user.id}")
                        current_user = db_user
            
            # Last resort: Direct token verification
            if current_user is None:
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    try:
                        logging.info("Attempting direct token verification")
                        supabase_user = await verify_supabase_token(request)
                        if supabase_user and "email" in supabase_user:
                            email = supabase_user.get("email")
                            logging.info(f"Direct verification found email: {email}")
                            
                            db_user = get_user_by_email(db, email=email)
                            if db_user:
                                logging.info(f"Found user via direct verification: {db_user.id}")
                                current_user = db_user
                    except Exception as e:
                        logging.error(f"Direct verification failed: {str(e)}")
        
        if current_user is None:
            logging.error("Failed to recover user for update")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        logging.info(f"Processing update for user: {current_user.id}")
        
        # Check if username is being updated and is already taken
        if user_update.username and user_update.username != current_user.username:
            logging.info(f"Username change requested: {current_user.username} -> {user_update.username}")
            username_exists = get_user_by_username(db, username=user_update.username)
            if username_exists:
                logging.warning(f"Username '{user_update.username}' is already taken")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
        
        # Update the user
        updated_user = update_user(
            db=db,
            user_id=current_user.id,
            user_data=user_update.dict(exclude_unset=True)
        )
        
        # Verify the update was successful by checking the database directly
        db_user = db.query(User).filter(User.id == current_user.id).first()
        if db_user:
            if user_update.username and db_user.username != user_update.username:
                logging.error(f"Username update verification failed: expected={user_update.username}, actual={db_user.username}")
            
            if user_update.interests and db_user.interests != user_update.interests:
                logging.error(f"Interests update verification failed: expected={user_update.interests}, actual={db_user.interests}")
        
        logging.info(f"User {current_user.id} updated successfully")
        return updated_user
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logging.error(f"Error updating user: {str(e)}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )

@router.put("/users/me/interests", response_model=schemas.UserResponse)
async def update_user_interests(
    interests: schemas.UserInterests,
    current_user: User = Depends(get_current_active_user_unified),
    db: Session = Depends(get_db)
):
    """Update user's interests and generate personalized learning paths"""
    try:
        from app.models import User
        
        logging.info(f"Updating interests for user: {current_user.id}")
        
        # Update user interests in the database
        update_data = {"interests": interests.interests}
        updated_user = update_user(
            db=db,
            user_id=current_user.id,
            user_data=update_data
        )
        
        # Force a final commit to ensure changes are saved
        db.commit()
        
        # Verify the update was successful
        db_user = db.query(User).filter(User.id == current_user.id).first()
        if db_user and db_user.interests != interests.interests:
            logging.error(f"Interests update verification failed: expected={interests.interests}, actual={db_user.interests}")
        else:
            logging.info(f"Interests updated successfully for user: {current_user.id}")
            
        return updated_user
    except Exception as e:
        logging.error(f"Error updating user interests: {str(e)}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user interests: {str(e)}"
        )

# Admin routes
@router.get("/users/{user_id}", response_model=schemas.UserResponse)
async def read_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user_unified),
    db: Session = Depends(get_db)
):
    # Only allow superusers to view other users
    if user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    db_user = get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return db_user

@router.get("/users", response_model=List[schemas.UserResponse])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user_unified),
    db: Session = Depends(get_db)
):
    # Only allow superusers to list all users
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    users = get_users(db, skip=skip, limit=limit)
    return users

@router.get("/test")
def test_route():
    return {"message": "Test route is working"}

@router.get("/me", response_model=schemas.UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user_unified)):
    """Get information about the currently authenticated user"""
    user_data = {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "profile_picture": current_user.profile_picture,
        "is_active": current_user.is_active,
        "oauth_provider": current_user.oauth_provider,
        "is_superuser": current_user.is_superuser,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None
    }
    return user_data 

# Add this route to handle card deletion from learning paths
@router.delete("/me/learning-paths/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card_from_learning_path(
    card_id: int,
    section_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """
    Remove a card from a section in the user's learning path.
    This is a proxy to the cards router endpoint.
    """
    from app.cards.crud import remove_card_from_user_learning_path
    
    try:
        # Check if current_user is None
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
            
        remove_card_from_user_learning_path(db, user_id=current_user.id, card_id=card_id, section_id=section_id)
        return {"detail": "Card removed from learning path successfully"}
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        # Log any unexpected errors
        logging.error(f"Error removing card {card_id} from learning path: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove card: {str(e)}"
        ) 

@router.get("/subscription", response_model=dict)
async def get_user_subscription_info(
    request: Request,  # Add request parameter for debugging
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Get the user's current subscription information and usage limits"""
    # Add enhanced debugging for this endpoint
    logging.info(f"[DEBUG] /subscription endpoint called with path: {request.url.path}")
    logging.info(f"[DEBUG] User authenticated: {current_user.id if current_user else None}")
    
    # CRITICAL FIX: Direct check for User object in request.state.user
    if current_user is None and hasattr(request.state, "user") and isinstance(request.state.user, User):
        logging.info(f"[DEBUG] CRITICAL FIX: Using User object directly from request.state: {request.state.user.id}")
        current_user = request.state.user
    
    # Extra verification that current_user is valid
    if not current_user:
        logging.error(f"[DEBUG] User is None in subscription endpoint after dependency check")
        
        # First check: If current_user is None, try to retrieve from request.state
        if hasattr(request.state, "user") and request.state.user is not None:
            logging.warning(f"[DEBUG] Attempting to recover user from request.state in subscription endpoint")
            if isinstance(request.state.user, User):
                current_user = request.state.user
                logging.info(f"[DEBUG] Recovered User model from request.state.user with ID: {current_user.id}")
            elif isinstance(request.state.user, dict) and "id" in request.state.user:
                # Try to look up the user in the database first
                if "email" in request.state.user:
                    email = request.state.user.get("email")
                    logging.info(f"[DEBUG] Looking up user by email from dict: {email}")
                    db_user = get_user_by_email(db, email=email)
                    if db_user:
                        logging.info(f"[DEBUG] Found user in database: {db_user.id}")
                        current_user = db_user
                    else:
                        # Create a temporary user with default subscription
                        user_id = request.state.user.get("id")
                        logging.info(f"[DEBUG] Creating temporary user from dict with ID: {user_id}")
                        current_user = User(
                            id=user_id, 
                            email=email,
                            username=email.split("@")[0],
                            is_active=True,
                            subscription_type="free"
                        )
                else:
                    # Create a temporary user with default subscription
                    user_id = request.state.user.get("id")
                    email = request.state.user.get("email", "user@example.com")
                    logging.info(f"[DEBUG] Creating temporary user from dict with ID: {user_id}")
                    current_user = User(
                        id=user_id, 
                        email=email,
                        username=email.split("@")[0],
                        is_active=True,
                        subscription_type="free"
                    )
        
        # Check for Supabase data if we still don't have a user
        if not current_user and hasattr(request.state, "supabase_user") and request.state.supabase_user is not None:
            email = request.state.supabase_user.get("email")
            if email:
                logging.info(f"[DEBUG] Looking up user with email {email} from Supabase data")
                db_user = get_user_by_email(db, email=email)
                if db_user:
                    logging.info(f"[DEBUG] Found user in database: {db_user.id}")
                    current_user = db_user
                else:
                    # Create a temporary user with default subscription
                    supabase_data = request.state.supabase_user
                    user_id = supabase_data.get("id", "temp-id")
                    logging.info(f"[DEBUG] Creating temporary user from Supabase data with ID: {user_id}")
                    current_user = User(
                        id=user_id, 
                        email=email,
                        username=email.split("@")[0],
                        is_active=True,
                        subscription_type="free"
                    )
        
        # Last resort: Direct token verification
        if not current_user:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                try:
                    logging.info("[DEBUG] Attempting direct token verification for subscription")
                    supabase_user = await verify_supabase_token(request)
                    if supabase_user and "email" in supabase_user:
                        email = supabase_user.get("email")
                        logging.info(f"[DEBUG] Direct verification found email: {email}")
                        
                        db_user = get_user_by_email(db, email=email)
                        if db_user:
                            logging.info(f"[DEBUG] Found user via direct verification: {db_user.id}")
                            current_user = db_user
                        else:
                            # Create a temporary user with default subscription
                            user_id = supabase_user.get("id", "temp-id")
                            logging.info(f"[DEBUG] Creating temporary user from token data with ID: {user_id}")
                            current_user = User(
                                id=user_id, 
                                email=email,
                                username=email.split("@")[0],
                                is_active=True,
                                subscription_type="free"
                            )
                except Exception as e:
                    logging.error(f"[DEBUG] Direct verification failed: {str(e)}")
        
        # If we still don't have a user, raise 401
        if not current_user:
            logging.error(f"[DEBUG] Failed to recover user in subscription endpoint")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    # Get subscription type, default to 'free' if not set
    subscription = current_user.subscription_type or 'free'
    logging.info(f"[DEBUG] User subscription type: {subscription}")
    
    # Get subscription limits for this subscription type
    limits = get_subscription_limits(subscription)
    
    try:
        # Get daily usage for today
        daily_usage = get_or_create_daily_usage(db, current_user.id)
        logging.info(f"[DEBUG] Daily usage retrieved: paths={daily_usage.paths_generated}/{daily_usage.paths_daily_limit}, cards={daily_usage.cards_generated}/{daily_usage.cards_daily_limit}")
        
        # Calculate remaining resources
        remaining = {
            "paths": daily_usage.paths_daily_limit - daily_usage.paths_generated,
            "cards": daily_usage.cards_daily_limit - daily_usage.cards_generated
        }
    except Exception as e:
        logging.error(f"[DEBUG] Error getting daily usage: {str(e)}")
        # Fallback to default limits if daily usage retrieval fails
        remaining = {
            "paths": limits.get("paths", 3),
            "cards": limits.get("cards", 20)
        }
        daily_usage = None
    
    # Handle premium users with unlimited resources
    if subscription == 'premium':
        remaining = {
            "paths": -1,  # -1 indicates unlimited
            "cards": -1   # -1 indicates unlimited
        }
    
    response_data = {
        "subscription_type": subscription,
        "subscription_start_date": current_user.subscription_start_date.isoformat() if current_user.subscription_start_date else None,
        "subscription_expiry_date": current_user.subscription_expiry_date.isoformat() if current_user.subscription_expiry_date else None,
        "daily_limits": {
            "paths": daily_usage.paths_daily_limit if daily_usage else limits.get("paths", 3),
            "cards": daily_usage.cards_daily_limit if daily_usage else limits.get("cards", 20)
        },
        "remaining_today": remaining
    }
    
    logging.info(f"[DEBUG] Returning subscription info: {response_data}")
    return response_data

@router.put("/subscription", response_model=schemas.UserResponse)
async def update_user_subscription(
    subscription_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Update a user's subscription type, with optional promotion code"""
    try:
        # Get the target subscription type from the request
        subscription_type = subscription_data.get("subscription_type")
        if not subscription_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subscription type is required"
            )
            
        # Get the promotion code if present
        promotion_code = subscription_data.get("promotion_code")
        
        # Process subscription update
        updated_user = update_user_subscription_crud(
            db=db,
            user_id=current_user.id,
            subscription_type=subscription_type,
            promotion_code=promotion_code
        )
        
        return updated_user
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Handle other errors
        logging.error(f"Error updating subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update subscription: {str(e)}"
        )

@router.post("/terms/accept", response_model=TermsAcceptanceResponse, status_code=status.HTTP_201_CREATED)
async def accept_terms(
    terms: TermsAcceptanceCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Record the user's acceptance of terms and conditions"""
    try:
        from app.models import UserTermsAcceptance
        
        logging.info(f"Processing terms acceptance for user: {current_user.id}, version: {terms.terms_version}")
        
        # Get the client's IP address
        ip = request.client.host if request.client else None
        if not terms.ip_address and ip:
            terms.ip_address = ip
        
        # Create the terms acceptance record directly using the model
        new_terms = UserTermsAcceptance(
            user_id=current_user.id,
            terms_version=terms.terms_version,
            ip_address=terms.ip_address
        )
        
        db.add(new_terms)
        db.commit()
        db.refresh(new_terms)
        
        logging.info(f"Terms acceptance created successfully: ID={new_terms.id}")
        
        # Return the new record
        return TermsAcceptanceResponse(
            id=new_terms.id,
            user_id=new_terms.user_id,
            terms_version=new_terms.terms_version,
            signed_at=new_terms.signed_at,
            ip_address=new_terms.ip_address
        )
    except Exception as e:
        logging.error(f"Error recording terms acceptance: {str(e)}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record terms acceptance: {str(e)}"
        )

@router.get("/terms/history", response_model=List[TermsAcceptanceResponse])
async def get_terms_acceptance_history(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Get the user's history of terms and conditions acceptance"""
    try:
        # Get the terms acceptance history for this user
        history = crud.get_user_terms_acceptances(
            db=db,
            user_id=current_user.id,
            skip=skip,
            limit=limit
        )
        
        return history
    except Exception as e:
        logging.error(f"Error getting terms acceptance history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get terms acceptance history: {str(e)}"
        )

@router.get("/terms/status/{terms_version}", response_model=dict)
async def check_terms_status(
    terms_version: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """Check if the user has accepted a specific version of the terms"""
    try:
        # Check if the user has accepted this version of the terms
        has_accepted = crud.has_accepted_terms(
            db=db,
            user_id=current_user.id,
            terms_version=terms_version
        )
        
        # Get the most recent acceptance if available
        latest = crud.get_latest_terms_acceptance(
            db=db,
            user_id=current_user.id,
            terms_version=terms_version
        )
        
        return {
            "has_accepted": has_accepted,
            "latest_acceptance": latest.signed_at.isoformat() if latest else None,
            "terms_version": terms_version
        }
    except Exception as e:
        logging.error(f"Error checking terms status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check terms status: {str(e)}"
        )

@router.get("/users/me/direct", response_model=schemas.UserResponse)
async def read_users_me_direct(
    request: Request,
    db: Session = Depends(get_db)
):
    """Direct access to user data without going through the authentication dependency"""
    logging.info("=== DIRECT BYPASS ENDPOINT CALLED ===")
    
    # Check for auth header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No valid Authorization header"
        )
    
    # First try to get user from request state
    if hasattr(request.state, "user") and request.state.user is not None:
        if isinstance(request.state.user, User):
            logging.info(f"Direct route: Found User object in request.state.user: {request.state.user.id}")
            return request.state.user
        elif isinstance(request.state.user, dict):
            logging.info(f"Direct route: Found dict in request.state.user")
            email = request.state.user.get('email')
            if email:
                user = get_user_by_email(db, email=email)
                if user:
                    return user
    
    # Otherwise try direct token verification
    try:
        supabase_user = await verify_supabase_token(request)
        if supabase_user and "email" in supabase_user:
            email = supabase_user.get("email")
            logging.info(f"Direct route: Got email from token: {email}")
            
            # Look up user in database
            user = get_user_by_email(db, email=email)
            if user:
                logging.info(f"Direct route: Found user in database: {user.id}")
                return user
            else:
                # Auto-create user
                logging.info(f"Direct route: Creating new user for {email}")
                
                # Generate username from email
                username = email.split("@")[0]
                
                # Create user data
                user_data = UserCreate(
                    email=email,
                    username=username,
                    password="",  # No password for Supabase users
                    full_name=supabase_user.get("name", ""),
                    is_active=True
                )
                
                # Create the user
                new_user = create_user(
                    db=db,
                    user=user_data,
                    oauth_provider="supabase",
                    oauth_id=supabase_user.get("id"),
                    profile_picture=supabase_user.get("avatar_url", "")
                )
                
                # Commit changes
                db.commit()
                
                logging.info(f"Direct route: Created new user: {new_user.id}")
                return new_user
    except Exception as e:
        logging.error(f"Direct route error: {str(e)}")
    
    # If we reached here, authentication failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication failed in direct route"
    ) 

@router.get("/debug/auth", response_model=dict)
async def debug_authentication(request: Request):
    """
    Debug endpoint to check authentication without requiring it.
    This endpoint will return details about the current authentication state
    without raising an error if authentication fails.
    """
    logging.info(f"=== DEBUG AUTH ENDPOINT CALLED ===")
    
    # Check headers
    auth_header = request.headers.get("Authorization")
    logging.info(f"Authorization header present: {auth_header is not None}")
    
    # Log all headers for debugging (excluding sensitive info)
    safe_headers = {k: v for k, v in request.headers.items() 
                  if k.lower() not in ['authorization', 'cookie', 'x-api-key']}
    logging.info(f"Request headers: {safe_headers}")
    
    # Check request state
    has_user = hasattr(request.state, "user") and request.state.user is not None
    has_supabase = hasattr(request.state, "supabase_user") and request.state.supabase_user is not None
    
    # Get basic user info if available
    user_info = {}
    if has_user:
        if isinstance(request.state.user, dict):
            user_info = {"type": "dict", "data": request.state.user}
        else:
            try:
                user_info = {
                    "type": "object",
                    "id": request.state.user.id,
                    "email": request.state.user.email,
                    "username": getattr(request.state.user, "username", None),
                    "is_active": getattr(request.state.user, "is_active", None),
                    "oauth_provider": getattr(request.state.user, "oauth_provider", None)
                }
            except Exception as e:
                user_info = {"type": "error", "message": str(e)}
    
    # Get Supabase info if available
    supabase_info = request.state.supabase_user if has_supabase else None
    
    # Basic response
    results = {
        "auth_header_present": auth_header is not None,
        "has_user_in_state": has_user,
        "has_supabase_in_state": has_supabase,
        "user_info": user_info,
        "supabase_info": supabase_info,
        "headers": safe_headers,
        "method": request.method,
        "path": request.url.path,
        "state_dir": dir(request.state)
    }
    
    # Try to verify token directly
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            supabase_user = await verify_supabase_token(request)
            if supabase_user:
                results["token_verification"] = "success"
                results["token_user_id"] = supabase_user.get("id")
                results["token_email"] = supabase_user.get("email")
                
                # Check if user exists in database
                db = SessionLocal()
                try:
                    email = supabase_user.get("email")
                    if email:
                        db_user = get_user_by_email(db, email=email)
                        if db_user:
                            results["database_user_found"] = True
                            results["database_user_id"] = db_user.id
                            results["database_user_email"] = db_user.email
                            results["database_user_active"] = db_user.is_active
                            
                            # Test if the user object can be serialized
                            try:
                                import json
                                from datetime import datetime, date
                                
                                def json_serial(obj):
                                    """JSON serializer for objects not serializable by default"""
                                    if isinstance(obj, (datetime, date)):
                                        return obj.isoformat()
                                    return str(obj)
                                
                                # Try to serialize the user object
                                user_dict = {c.name: getattr(db_user, c.name) for c in db_user.__table__.columns}
                                json.dumps(user_dict, default=json_serial)
                                results["user_serializable"] = True
                            except Exception as e:
                                results["user_serializable"] = False
                                results["serialization_error"] = str(e)
                        else:
                            results["database_user_found"] = False
                            
                            # Test if we can create the user automatically
                            try:
                                # Generate username from email
                                username = email.split("@")[0]
                                
                                # Mock user creation (don't actually create)
                                results["could_create_user"] = True
                                results["would_create_with"] = {
                                    "email": email,
                                    "username": username,
                                    "oauth_provider": "supabase",
                                    "oauth_id": supabase_user.get("id")
                                }
                            except Exception as e:
                                results["could_create_user"] = False
                                results["creation_error"] = str(e)
                finally:
                    db.close()
            else:
                results["token_verification"] = "failed"
        except Exception as e:
            results["token_verification"] = "error"
            results["token_error"] = str(e)
            
            # Get full error traceback
            import traceback
            results["token_error_traceback"] = traceback.format_exc()
    
    # Test db connection
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        results["db_connection"] = "working"
    except Exception as e:
        results["db_connection"] = f"error: {str(e)}"
    
    # Check environment variables
    results["supabase_url_configured"] = os.getenv("SUPABASE_URL") is not None
    results["supabase_key_configured"] = os.getenv("SUPABASE_KEY") is not None
    
    # Add server timestamp
    from datetime import datetime
    results["server_timestamp"] = datetime.utcnow().isoformat()
    
    return results

@router.get("/users/me/db-test", response_model=dict)
async def test_database_updates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_unified)
):
    """
    Diagnostic endpoint to test direct database updates
    """
    try:
        logging.info(f"Database test for user ID: {current_user.id}, email: {current_user.email}")
        
        # Get original user state
        orig_user = db.query(User).filter(User.id == current_user.id).first()
        if not orig_user:
            logging.error(f"User {current_user.id} not found in database!")
            return {"status": "error", "message": "User not found in database"}
            
        logging.info(f"Original user state: username={orig_user.username}, interests={orig_user.interests}")
        
        # Test 1: Direct ORM update
        logging.info("Test 1: Direct ORM update")
        test_interests = ["test_interest_1", "test_interest_2"]
        orig_user.interests = test_interests
        
        try:
            db.commit()
            logging.info("Test 1: Database commit successful")
        except Exception as e:
            logging.error(f"Test 1: Database commit failed: {str(e)}")
            db.rollback()
            return {"status": "error", "message": f"ORM update failed: {str(e)}"}
        
        # Verify update
        db.refresh(orig_user)
        logging.info(f"After Test 1: interests={orig_user.interests}")
        
        # Test 2: SQL update
        logging.info("Test 2: Direct SQL update")
        try:
            from sqlalchemy import text
            test_username = f"test_user_{current_user.id}"
            sql = text(f"UPDATE users SET username = :username WHERE id = :id")
            db.execute(sql, {"username": test_username, "id": current_user.id})
            db.commit()
            logging.info("Test 2: SQL update committed")
        except Exception as e:
            logging.error(f"Test 2: SQL update failed: {str(e)}")
            db.rollback()
            return {"status": "error", "message": f"SQL update failed: {str(e)}"}
            
        # Final verification
        final_user = db.query(User).filter(User.id == current_user.id).first()
        logging.info(f"Final user state: username={final_user.username}, interests={final_user.interests}")
        
        # Test 3: Create terms acceptance
        logging.info("Test 3: Creating terms acceptance record")
        try:
            from app.models import UserTermsAcceptance
            test_terms = UserTermsAcceptance(
                user_id=current_user.id,
                terms_version="test_v1.0",
                ip_address="127.0.0.1"
            )
            db.add(test_terms)
            db.commit()
            db.refresh(test_terms)
            logging.info(f"Test 3: Terms acceptance created with ID: {test_terms.id}")
            
            # Verify terms acceptance
            terms_check = db.query(UserTermsAcceptance).filter(
                UserTermsAcceptance.user_id == current_user.id,
                UserTermsAcceptance.terms_version == "test_v1.0"
            ).first()
            
            if terms_check:
                logging.info(f"Terms acceptance verified with ID: {terms_check.id}")
            else:
                logging.error("Terms acceptance not found after creation!")
        except Exception as e:
            logging.error(f"Test 3: Terms acceptance creation failed: {str(e)}")
            db.rollback()
            return {"status": "error", "message": f"Terms acceptance creation failed: {str(e)}"}
        
        return {
            "status": "success",
            "message": "Database tests completed",
            "user_id": current_user.id,
            "username": final_user.username,
            "interests": final_user.interests,
            "terms_acceptance_id": test_terms.id if 'test_terms' in locals() else None
        }
    except Exception as e:
        logging.error(f"Database test error: {str(e)}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        
        return {
            "status": "error",
            "message": f"Test failed: {str(e)}",
            "traceback": traceback.format_exc()
        } 

@router.post("/admin/reset-db-pool", response_model=dict)
async def admin_reset_db_pool(
    current_user: User = Depends(get_current_active_user_unified)
):
    """Reset the database connection pool to fix potential connection issues."""
    # Only allow superusers to perform this action
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
        
    from app.db import reset_db_pool
    
    success = reset_db_pool()
    
    return {
        "success": success,
        "message": "Database connection pool reset successfully" if success else "Failed to reset database connection pool",
        "timestamp": datetime.utcnow().isoformat()
    } 

@router.get("/diagnostic/auth", response_model=dict)
async def diagnostic_auth_info(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Diagnostic endpoint to troubleshoot authentication issues.
    This endpoint will attempt all the authentication methods used in the unified auth system
    and report detailed results for debugging.
    """
    logging.info(f"[DEBUG] === DIAGNOSTIC AUTH ENDPOINT CALLED FOR PATH: {request.url.path} ===")
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "path": request.url.path,
        "method": request.method,
        "request_state": {},
        "auth_header": {},
        "db_checks": {},
        "token_verification": {}
    }
    
    # Check request.state
    results["request_state"]["has_user"] = hasattr(request.state, "user")
    results["request_state"]["has_supabase_user"] = hasattr(request.state, "supabase_user")
    
    if hasattr(request.state, "user") and request.state.user is not None:
        if isinstance(request.state.user, User):
            results["request_state"]["user_type"] = "User model instance"
            results["request_state"]["user_id"] = request.state.user.id
            results["request_state"]["user_email"] = request.state.user.email
            results["request_state"]["user_is_active"] = request.state.user.is_active
        elif isinstance(request.state.user, dict):
            results["request_state"]["user_type"] = "Dictionary"
            results["request_state"]["user_dict"] = request.state.user
        else:
            results["request_state"]["user_type"] = str(type(request.state.user))
    
    if hasattr(request.state, "supabase_user") and request.state.supabase_user is not None:
        results["request_state"]["supabase_user_keys"] = list(request.state.supabase_user.keys())
        results["request_state"]["supabase_user_email"] = request.state.supabase_user.get("email")
    
    # Check auth header
    auth_header = request.headers.get("Authorization")
    results["auth_header"]["present"] = auth_header is not None
    results["auth_header"]["type"] = "Bearer" if auth_header and auth_header.startswith("Bearer ") else "None/Unknown"
    
    # Database checks
    if hasattr(request.state, "user") and isinstance(request.state.user, dict) and "email" in request.state.user:
        email = request.state.user.get("email")
        results["db_checks"]["request_state_user_dict_email"] = email
        try:
            db_user = get_user_by_email(db, email=email)
            results["db_checks"]["user_found_by_email"] = db_user is not None
            if db_user:
                results["db_checks"]["db_user_id"] = db_user.id
                results["db_checks"]["db_user_is_active"] = db_user.is_active
        except Exception as e:
            results["db_checks"]["error_looking_up_user"] = str(e)
    
    if hasattr(request.state, "supabase_user") and "email" in request.state.supabase_user:
        email = request.state.supabase_user.get("email")
        results["db_checks"]["supabase_user_email"] = email
        try:
            db_user = get_user_by_email(db, email=email)
            results["db_checks"]["supabase_user_found_in_db"] = db_user is not None
            if db_user:
                results["db_checks"]["supabase_db_user_id"] = db_user.id
                results["db_checks"]["supabase_db_user_is_active"] = db_user.is_active
        except Exception as e:
            results["db_checks"]["error_looking_up_supabase_user"] = str(e)
    
    # Token verification
    if auth_header and auth_header.startswith("Bearer "):
        try:
            supabase_user = await verify_supabase_token(request)
            results["token_verification"]["success"] = supabase_user is not None
            if supabase_user:
                results["token_verification"]["user_id"] = supabase_user.get("id")
                results["token_verification"]["email"] = supabase_user.get("email")
                
                # Check if user exists in database
                db = SessionLocal()
                try:
                    email = supabase_user.get("email")
                    if email:
                        db_user = get_user_by_email(db, email=email)
                        if db_user:
                            results["database_user_found"] = True
                            results["database_user_id"] = db_user.id
                            results["database_user_email"] = db_user.email
                            results["database_user_active"] = db_user.is_active
                            
                            # Test if the user object can be serialized
                            try:
                                import json
                                from datetime import datetime, date
                                
                                def json_serial(obj):
                                    """JSON serializer for objects not serializable by default"""
                                    if isinstance(obj, (datetime, date)):
                                        return obj.isoformat()
                                    return str(obj)
                                
                                # Try to serialize the user object
                                user_dict = {c.name: getattr(db_user, c.name) for c in db_user.__table__.columns}
                                json.dumps(user_dict, default=json_serial)
                                results["user_serializable"] = True
                            except Exception as e:
                                results["user_serializable"] = False
                                results["serialization_error"] = str(e)
                        else:
                            results["database_user_found"] = False
                            
                            # Test if we can create the user automatically
                            try:
                                # Generate username from email
                                username = email.split("@")[0]
                                
                                # Mock user creation (don't actually create)
                                results["could_create_user"] = True
                                results["would_create_with"] = {
                                    "email": email,
                                    "username": username,
                                    "oauth_provider": "supabase",
                                    "oauth_id": supabase_user.get("id")
                                }
                            except Exception as e:
                                results["could_create_user"] = False
                                results["creation_error"] = str(e)
                finally:
                    db.close()
            else:
                results["token_verification"] = "failed"
        except Exception as e:
            results["token_verification"] = "error"
            results["token_error"] = str(e)
            
            # Get full error traceback
            import traceback
            results["token_error_traceback"] = traceback.format_exc()
    
    # Check environment variables
    results["supabase_url_configured"] = os.getenv("SUPABASE_URL") is not None
    results["supabase_key_configured"] = os.getenv("SUPABASE_KEY") is not None
    
    # Add server timestamp
    from datetime import datetime
    results["server_timestamp"] = datetime.utcnow().isoformat()
    
    return results 

@router.get("/auth-diagnostics", response_model=dict)
async def detailed_auth_diagnostics(request: Request, db: Session = Depends(get_db)):
    """
    Detailed diagnostic endpoint for authentication issues.
    This captures the complete authentication flow step-by-step.
    """
    result = {
        "timestamp": datetime.utcnow().isoformat(),
        "request_info": {
            "path": request.url.path,
            "method": request.method,
            "headers": {k: v for k, v in request.headers.items() 
                      if k.lower() not in ['authorization', 'cookie', 'x-api-key']}
        },
        "auth_flow": [],
        "request_state": {},
        "database_checks": [],
        "token_verification": {},
        "user_data": {},
        "middleware_data": {},
        "errors": []
    }
    
    # Step 1: Check request.state for user data
    result["auth_flow"].append("Checking request.state for user data")
    try:
        result["request_state"]["has_user"] = hasattr(request.state, "user")
        result["request_state"]["has_supabase_user"] = hasattr(request.state, "supabase_user")
        result["request_state"]["state_attributes"] = dir(request.state)
        
        if hasattr(request.state, "user") and request.state.user is not None:
            result["auth_flow"].append("User found in request.state.user")
            if isinstance(request.state.user, User):
                result["auth_flow"].append("User in request.state is a User model")
                result["request_state"]["user_type"] = "User model"
                result["request_state"]["user_id"] = request.state.user.id
                result["request_state"]["user_email"] = request.state.user.email
                result["request_state"]["user_is_active"] = request.state.user.is_active
                
                # Attempt to serialize User model to verify it's valid
                try:
                    from fastapi.encoders import jsonable_encoder
                    user_data = jsonable_encoder(request.state.user)
                    result["request_state"]["user_serializable"] = True
                    result["user_data"] = user_data
                except Exception as e:
                    result["request_state"]["user_serializable"] = False
                    result["request_state"]["serialization_error"] = str(e)
            elif isinstance(request.state.user, dict):
                result["auth_flow"].append("User in request.state is a dict")
                result["request_state"]["user_type"] = "dict"
                result["request_state"]["user_dict"] = request.state.user
                
                # If the dict has an email, check the database
                if "email" in request.state.user:
                    email = request.state.user.get("email")
                    result["auth_flow"].append(f"User dict has email: {email}, checking database")
                    result["database_checks"].append({
                        "step": "Lookup from request.state.user dict",
                        "email": email
                    })
                    
                    db_user = get_user_by_email(db, email=email)
                    if db_user:
                        result["auth_flow"].append(f"Found user in database with email {email}")
                        result["database_checks"][-1]["found"] = True
                        result["database_checks"][-1]["user_id"] = db_user.id
                    else:
                        result["auth_flow"].append(f"User with email {email} not found in database")
                        result["database_checks"][-1]["found"] = False
            else:
                result["auth_flow"].append(f"User in request.state is of unexpected type: {type(request.state.user)}")
                result["request_state"]["user_type"] = str(type(request.state.user))
        else:
            result["auth_flow"].append("No user found in request.state.user")
        
        if hasattr(request.state, "supabase_user") and request.state.supabase_user is not None:
            result["auth_flow"].append("Supabase user data found in request.state.supabase_user")
            result["request_state"]["supabase_user_data"] = request.state.supabase_user
            
            # If supabase_user has an email, check the database
            if "email" in request.state.supabase_user:
                email = request.state.supabase_user.get("email")
                result["auth_flow"].append(f"Supabase user has email: {email}, checking database")
                result["database_checks"].append({
                    "step": "Lookup from request.state.supabase_user",
                    "email": email
                })
                
                db_user = get_user_by_email(db, email=email)
                if db_user:
                    result["auth_flow"].append(f"Found user in database with email {email}")
                    result["database_checks"][-1]["found"] = True
                    result["database_checks"][-1]["user_id"] = db_user.id
                else:
                    result["auth_flow"].append(f"User with email {email} not found in database")
                    result["database_checks"][-1]["found"] = False
        else:
            result["auth_flow"].append("No supabase user data found in request.state.supabase_user")
    except Exception as e:
        result["auth_flow"].append(f"Error checking request.state: {str(e)}")
        result["errors"].append({
            "step": "request_state_check",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
    
    # Step 2: Check Authorization header and verify token
    auth_header = request.headers.get("Authorization")
    result["auth_flow"].append("Checking Authorization header")
    if auth_header:
        if auth_header.startswith("Bearer "):
            result["auth_flow"].append("Bearer token found in Authorization header")
            result["token_verification"]["has_token"] = True
            
            # Get token preview (first 10 chars)
            token = auth_header.split(" ")[1]
            token_preview = token[:10] + "..." if len(token) > 10 else token
            result["token_verification"]["token_preview"] = token_preview
            
            # Try to verify the token
            try:
                result["auth_flow"].append("Attempting to verify token")
                supabase_user = await verify_supabase_token(request)
                
                if supabase_user:
                    result["auth_flow"].append("Token verification successful")
                    result["token_verification"]["verified"] = True
                    result["token_verification"]["user_id"] = supabase_user.get("id")
                    result["token_verification"]["email"] = supabase_user.get("email")
                    result["token_verification"]["user_data"] = supabase_user
                    
                    # Check database for this user
                    email = supabase_user.get("email")
                    if email:
                        result["auth_flow"].append(f"Token has email: {email}, checking database")
                        result["database_checks"].append({
                            "step": "Lookup from token verification",
                            "email": email
                        })
                        
                        db_user = get_user_by_email(db, email=email)
                        if db_user:
                            result["auth_flow"].append(f"Found user in database with email {email}")
                            result["database_checks"][-1]["found"] = True
                            result["database_checks"][-1]["user_id"] = db_user.id
                            
                            # Try to serialize the user for verification
                            try:
                                from fastapi.encoders import jsonable_encoder
                                user_data = jsonable_encoder(db_user)
                                result["database_checks"][-1]["serializable"] = True
                                if not result.get("user_data"):
                                    result["user_data"] = user_data
                            except Exception as e:
                                result["database_checks"][-1]["serializable"] = False
                                result["database_checks"][-1]["serialization_error"] = str(e)
                        else:
                            result["auth_flow"].append(f"User with email {email} not found in database")
                            result["database_checks"][-1]["found"] = False
                else:
                    result["auth_flow"].append("Token verification failed")
                    result["token_verification"]["verified"] = False
            except Exception as e:
                result["auth_flow"].append(f"Error verifying token: {str(e)}")
                result["token_verification"]["verified"] = False
                result["token_verification"]["error"] = str(e)
                result["errors"].append({
                    "step": "token_verification",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
        else:
            result["auth_flow"].append("Authorization header does not contain a Bearer token")
            result["token_verification"]["has_token"] = False
    else:
        result["auth_flow"].append("No Authorization header found")
        result["token_verification"]["has_token"] = False
    
    # Step 3: Try the dependency chain manually to see where it fails
    result["auth_flow"].append("Testing authentication dependency chain")
    try:
        result["auth_flow"].append("Calling get_current_user_unified")
        user_from_unified = await get_current_user_unified(request, None, db)
        
        if user_from_unified:
            result["auth_flow"].append(f"get_current_user_unified returned user: {user_from_unified.id}")
            result["middleware_data"]["get_current_user_unified"] = {
                "success": True,
                "user_id": user_from_unified.id,
                "email": user_from_unified.email
            }
            
            # Try the next step in the chain
            result["auth_flow"].append("Calling get_current_active_user_unified")
            try:
                active_user = await get_current_active_user_unified(request, user_from_unified, db)
                if active_user:
                    result["auth_flow"].append(f"get_current_active_user_unified returned user: {active_user.id}")
                    result["middleware_data"]["get_current_active_user_unified"] = {
                        "success": True,
                        "user_id": active_user.id
                    }
                else:
                    result["auth_flow"].append("get_current_active_user_unified returned None")
                    result["middleware_data"]["get_current_active_user_unified"] = {
                        "success": False,
                        "returned": None
                    }
            except Exception as e:
                result["auth_flow"].append(f"get_current_active_user_unified raised error: {str(e)}")
                result["middleware_data"]["get_current_active_user_unified"] = {
                    "success": False,
                    "error": str(e)
                }
                result["errors"].append({
                    "step": "get_current_active_user_unified",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
        else:
            result["auth_flow"].append("get_current_user_unified returned None")
            result["middleware_data"]["get_current_user_unified"] = {
                "success": False,
                "returned": None
            }
    except Exception as e:
        result["auth_flow"].append(f"get_current_user_unified raised error: {str(e)}")
        result["middleware_data"]["get_current_user_unified"] = {
            "success": False,
            "error": str(e)
        }
        result["errors"].append({
            "step": "get_current_user_unified",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
    
    # Step 4: Database connection check
    result["auth_flow"].append("Testing database connection")
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        result["database_connection"] = "working"
    except Exception as e:
        result["database_connection"] = f"error: {str(e)}"
        result["errors"].append({
            "step": "database_connection",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
    
    # Step 5: Environment check
    result["environment"] = {
        "supabase_url_configured": os.getenv("SUPABASE_URL") is not None,
        "supabase_key_configured": os.getenv("SUPABASE_KEY") is not None,
        "db_url_configured": os.getenv("DATABASE_URL") is not None
    }
    
    # Final assessment
    if result.get("user_data"):
        result["authentication_status"] = "successful"
    elif result["token_verification"].get("verified") and not any(check.get("found", False) for check in result["database_checks"]):
        result["authentication_status"] = "token_valid_but_user_not_in_database"
    elif not result["token_verification"].get("verified"):
        result["authentication_status"] = "token_verification_failed"
    elif not result["token_verification"].get("has_token"):
        result["authentication_status"] = "no_token_provided"
    else:
        result["authentication_status"] = "unknown_failure"
    
    return result

@router.get("/direct-auth-check", response_model=dict)
async def direct_auth_check(request: Request):
    """
    Direct authentication check endpoint that bypasses the dependency chain.
    This endpoint is solely for debugging authentication issues.
    """
    result = {
        "timestamp": datetime.utcnow().isoformat(),
        "path": request.url.path,
        "method": request.method,
        "headers_present": {
            "authorization": request.headers.get("Authorization") is not None,
            "origin": request.headers.get("Origin")
        },
        "request_state": {}
    }
    
    # Check request.state directly
    if hasattr(request.state, "user"):
        result["request_state"]["has_user"] = True
        user_obj = request.state.user
        
        if user_obj is None:
            result["request_state"]["user_type"] = "NoneType"
            result["auth_status"] = "none_user_in_state"
        elif isinstance(user_obj, User):
            result["request_state"]["user_type"] = "User object"
            result["request_state"]["user_id"] = user_obj.id
            result["request_state"]["user_email"] = user_obj.email
            result["request_state"]["user_is_active"] = user_obj.is_active
            
            # Try to serialize the user object
            try:
                from fastapi.encoders import jsonable_encoder
                user_data = jsonable_encoder(user_obj)
                result["request_state"]["user_data"] = user_data
                result["auth_status"] = "success"
            except Exception as e:
                result["request_state"]["serialization_error"] = str(e)
                result["auth_status"] = "error_serializing"
        elif isinstance(user_obj, dict):
            result["request_state"]["user_type"] = "dictionary"
            result["request_state"]["user_dict"] = user_obj
            result["auth_status"] = "dict_not_user_object"
        else:
            result["request_state"]["user_type"] = str(type(user_obj))
            result["auth_status"] = "unknown_user_type"
    else:
        result["request_state"]["has_user"] = False
        result["auth_status"] = "no_user_in_state"
    
    # Check for Supabase user data
    if hasattr(request.state, "supabase_user"):
        result["request_state"]["has_supabase_user"] = True
        supabase_user = request.state.supabase_user
        if supabase_user is None:
            result["request_state"]["supabase_user"] = "None"
        else:
            result["request_state"]["supabase_user"] = supabase_user
    else:
        result["request_state"]["has_supabase_user"] = False
    
    # Try direct token verification
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            result["token_verification"] = "attempting"
            supabase_user = await verify_supabase_token(request)
            if supabase_user:
                result["token_verification"] = "success"
                result["token_user"] = {
                    "id": supabase_user.get("id"),
                    "email": supabase_user.get("email")
                }
            else:
                result["token_verification"] = "failed"
                # Include the token preview for debugging
                token = auth_header.split(" ")[1]
                result["token_preview"] = token[:10] + "..." if len(token) > 10 else token
        except Exception as e:
            result["token_verification"] = "error"
            result["token_error"] = str(e)
            result["token_error_traceback"] = traceback.format_exc()
    else:
        result["token_verification"] = "no_token"
    
    # Check database connection
    try:
        from sqlalchemy import text
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            result["database_connection"] = "working"
        except Exception as e:
            result["database_connection"] = f"error: {str(e)}"
        finally:
            db.close()
    except Exception as e:
        result["database_connection"] = f"connection error: {str(e)}"
    
    return result