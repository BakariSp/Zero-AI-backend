import json
import logging
import time
from typing import Dict, Any, Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.auth.supabase import verify_supabase_token
from app.users.crud import get_user_by_email, create_user
from app.users.schemas import UserCreate

# Configure logging
logger = logging.getLogger(__name__)

# Simple in-memory cache for token verification results (5-minute TTL)
_token_cache: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 300  # 5 minutes in seconds

def _get_cached_token_result(token: str) -> Optional[Dict[str, Any]]:
    """Get cached token verification result if still valid"""
    if token in _token_cache:
        cached_data = _token_cache[token]
        if time.time() - cached_data['timestamp'] < _CACHE_TTL:
            return cached_data['user_data']
        else:
            # Remove expired cache entry
            del _token_cache[token]
    return None

def _cache_token_result(token: str, user_data: Dict[str, Any]):
    """Cache token verification result"""
    _token_cache[token] = {
        'user_data': user_data,
        'timestamp': time.time()
    }

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
        # Skip authentication for OPTIONS requests
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Initialize request state for user
        request.state.user = None
        request.state.supabase_user = None
        
        # Get Supabase user data from token with caching
        supabase_user = None
        
        # Extract token for caching check
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
            # Try to get cached result first
            cached_result = _get_cached_token_result(token)
            if cached_result:
                supabase_user = cached_result
            else:
                # Verify token and cache result
                supabase_user = await verify_supabase_token(request)
                if supabase_user:
                    _cache_token_result(token, supabase_user)
        
        if supabase_user:
            # Store the Supabase user data in request state
            request.state.supabase_user = supabase_user
            
            # Check if we need to synchronize with our database
            if self._should_sync_with_database(request.url.path):
                try:
                    # Get or create user in our database
                    user = await self._sync_user_with_database(supabase_user)
                    if user:
                        request.state.user = user
                        # Print our user information
                        logger.info(f"Our user info: id={user.id}, email={user.email}, username={user.username}, "
                                  f"is_guest={user.is_guest}, subscription_type={user.subscription_type}")
                    else:
                        request.state.user = supabase_user
                except Exception as e:
                    request.state.user = supabase_user
            else:
                request.state.user = supabase_user
        
        # Continue processing the request
        response = await call_next(request)
        return response
    
    def _should_sync_with_database(self, path: str) -> bool:
        """
        Determine if we should sync with our database for this request.
        """
        skip_paths = [
            "/static/",
            "/favicon.ico",
            "/health",
            "/api/token"
        ]
        
        for skip_path in skip_paths:
            if path.startswith(skip_path):
                return False
        
        return True

    async def _sync_user_with_database(self, supabase_user: dict):
        """
        Synchronize Supabase user with our database.
        Creates a new user if they don't exist, updates if they do.
        """
        try:
            db = SessionLocal()
            try:
                email = supabase_user.get("email")
                user_id = supabase_user.get("id")
                is_anonymous = supabase_user.get("is_anonymous", False)
                
                # Try to find existing user by oauth_id first
                existing_user = None
                if user_id:
                    try:
                        from app.users.crud import get_user_by_oauth
                        existing_user = get_user_by_oauth(db, "supabase", user_id)
                    except Exception as e:
                        pass
                
                # If not found by oauth_id, try email
                if not existing_user and email:
                    try:
                        existing_user = get_user_by_email(db, email)
                        if existing_user and not existing_user.oauth_id:
                            existing_user.oauth_provider = "supabase"
                            existing_user.oauth_id = user_id
                            db.commit()
                    except Exception as e:
                        pass
                
                if existing_user:
                    return existing_user
                
                # Create new user
                if is_anonymous or not email:
                    safe_user_id = user_id.replace("-", "").replace("_", "")
                    username = f"anonymous{safe_user_id}"
                    email = f"anonymous{safe_user_id}@example.com"
                    full_name = "Anonymous User"
                    is_guest = True
                else:
                    username = email.split("@")[0]
                    full_name = supabase_user.get("user_metadata", {}).get("full_name", "")
                    is_guest = False
                
                # Create user data
                user_data = UserCreate(
                    email=email,
                    username=username,
                    password="",  # No password for Supabase users
                    full_name=full_name,
                    is_active=True
                )
                
                # Create the user
                new_user = create_user(
                    db=db,
                    user=user_data,
                    oauth_provider="supabase",
                    oauth_id=user_id,
                    profile_picture=supabase_user.get("user_metadata", {}).get("avatar_url"),
                    is_guest=is_guest
                )
                
                return new_user
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error syncing user with database: {str(e)}")
            return None 