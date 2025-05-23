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
                try:
                    # Get or create user in our database
                    user = await self._sync_user_with_database(supabase_user)
                    if user:
                        logger.info(f"User synchronized with database: {user.id}")
                        request.state.user = user
                        request.state.debug_user_id = str(user.id)
                    else:
                        logger.warning(f"Failed to sync user with database for {request.url.path}")
                        # Keep the Supabase user data for fallback authentication
                        request.state.user = supabase_user
                except Exception as e:
                    logger.error(f"Error syncing user with database: {str(e)}")
                    # Fall back to using Supabase user data only
                    request.state.user = supabase_user
            else:
                logger.info(f"Skipping database sync for path: {request.url.path}")
                # For paths that don't need database sync, just use Supabase data
                request.state.user = supabase_user
        else:
            logger.info(f"No Supabase authentication for {request.url.path}")
        
        # Continue processing the request
        try:
            # Check if user object is available in state before proceeding
            has_user = hasattr(request.state, "user") and request.state.user is not None
            if has_user:
                if isinstance(request.state.user, dict):
                    logger.info(f"Request proceeding with legacy user dict: {request.state.user.get('id', 'unknown')}")
                else:
                    logger.info(f"Request proceeding with User object: {request.state.user.id}")
            else:
                logger.info(f"Request proceeding without user object in state")
            
        except Exception as e:
            logger.error(f"Error in middleware pre-processing: {str(e)}")
        
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

    async def _sync_user_with_database(self, supabase_user: dict):
        """
        Synchronize Supabase user with our database.
        Creates a new user if they don't exist, updates if they do.
        
        Args:
            supabase_user: User data from Supabase
            
        Returns:
            User: The user object from our database
        """
        try:
            db = SessionLocal()
            try:
                email = supabase_user.get("email")
                user_id = supabase_user.get("id")
                is_anonymous = supabase_user.get("is_anonymous", False)
                
                # 🔍 DEBUG: 记录接收到的Supabase用户数据
                logger.info(f"🔍 [SYNC DEBUG] Received Supabase user data:")
                logger.info(f"🔍 [SYNC DEBUG] - user_id: {user_id}")
                logger.info(f"🔍 [SYNC DEBUG] - email: {email}")
                logger.info(f"🔍 [SYNC DEBUG] - is_anonymous: {is_anonymous}")
                logger.info(f"🔍 [SYNC DEBUG] - full supabase_user keys: {list(supabase_user.keys())}")
                logger.info(f"🔍 [SYNC DEBUG] - user_metadata: {supabase_user.get('user_metadata', {})}")
                
                if not user_id:
                    logger.error("🔍 [SYNC DEBUG] ERROR: No user ID found in Supabase user data")
                    return None
                
                # First, try to find user by oauth_id (Supabase user ID)
                existing_user = None
                try:
                    from app.users.crud import get_user_by_oauth
                    existing_user = get_user_by_oauth(db, "supabase", user_id)
                    logger.info(f"🔍 [SYNC DEBUG] Lookup by oauth_id result: {'Found' if existing_user else 'Not found'}")
                except Exception as e:
                    logger.warning(f"🔍 [SYNC DEBUG] Error looking up user by oauth_id: {str(e)}")
                
                # If not found by oauth_id and we have an email, try by email
                if not existing_user and email:
                    try:
                        existing_user = get_user_by_email(db, email)
                        logger.info(f"🔍 [SYNC DEBUG] Lookup by email result: {'Found' if existing_user else 'Not found'}")
                        # If found by email but no oauth_id, update it
                        if existing_user and not existing_user.oauth_id:
                            existing_user.oauth_provider = "supabase"
                            existing_user.oauth_id = user_id
                            db.commit()
                            logger.info(f"🔍 [SYNC DEBUG] Updated existing user {existing_user.id} with Supabase oauth_id")
                    except Exception as e:
                        logger.warning(f"🔍 [SYNC DEBUG] Error looking up user by email: {str(e)}")
                
                if existing_user:
                    logger.info(f"🔍 [SYNC DEBUG] Found existing user: {existing_user.id}, returning existing user")
                    return existing_user
                
                # Create new user
                logger.info(f"🔍 [SYNC DEBUG] Creating new user for Supabase ID: {user_id}")
                
                # For anonymous users, create special email and username
                if is_anonymous or not email:
                    # 🔧 FIX: 生成符合验证规则的数据
                    # 1. 用户名：只包含字母和数字（移除所有特殊字符）
                    # 2. 邮箱：使用真实的域名而不是保留域名
                    safe_user_id = user_id.replace("-", "").replace("_", "")  # 移除所有连字符和下划线
                    username = f"anonymous{safe_user_id}"  # 纯字母数字
                    email = f"anonymous{safe_user_id}@example.com"  # 使用example.com域名
                    full_name = "Anonymous User"
                    is_guest = True
                    
                    logger.info(f"🔍 [SYNC DEBUG] Anonymous user data prepared:")
                    logger.info(f"🔍 [SYNC DEBUG] - original_user_id: {user_id}")
                    logger.info(f"🔍 [SYNC DEBUG] - safe_user_id: {safe_user_id}")
                    logger.info(f"🔍 [SYNC DEBUG] - email: {email}")
                    logger.info(f"🔍 [SYNC DEBUG] - username: {username}")
                    logger.info(f"🔍 [SYNC DEBUG] - username.isalnum(): {username.isalnum()}")
                else:
                    # For regular users, use their email
                    # 确保用户名也符合纯字母数字的要求
                    base_username = email.split("@")[0] if email else f"user{user_id.replace('-', '').replace('_', '')}"
                    # 移除用户名中的特殊字符，只保留字母数字
                    username = ''.join(c for c in base_username if c.isalnum())
                    # 如果处理后用户名为空，使用默认格式
                    if not username:
                        username = f"user{user_id.replace('-', '').replace('_', '')}"
                    
                    full_name = supabase_user.get("user_metadata", {}).get("full_name") or \
                               supabase_user.get("user_metadata", {}).get("name") or ""
                    is_guest = False
                    
                    logger.info(f"🔍 [SYNC DEBUG] Regular user data prepared:")
                    logger.info(f"🔍 [SYNC DEBUG] - email: {email}")
                    logger.info(f"🔍 [SYNC DEBUG] - base_username: {base_username}")
                    logger.info(f"🔍 [SYNC DEBUG] - username: {username}")
                    logger.info(f"🔍 [SYNC DEBUG] - username.isalnum(): {username.isalnum()}")
                    logger.info(f"🔍 [SYNC DEBUG] - full_name: {full_name}")
                
                # Create user data
                user_data = UserCreate(
                    email=email,
                    username=username,
                    password="",  # No password for Supabase users
                    full_name=full_name,
                    is_active=True,
                    subscription_type="free"
                )
                
                logger.info(f"🔍 [SYNC DEBUG] UserCreate object created successfully:")
                logger.info(f"🔍 [SYNC DEBUG] - email: {user_data.email}")
                logger.info(f"🔍 [SYNC DEBUG] - username: {user_data.username}")
                logger.info(f"🔍 [SYNC DEBUG] - full_name: {user_data.full_name}")
                logger.info(f"🔍 [SYNC DEBUG] - is_active: {user_data.is_active}")
                logger.info(f"🔍 [SYNC DEBUG] - subscription_type: {user_data.subscription_type}")
                
                # 🔍 DEBUG: 记录即将传递给create_user的参数
                logger.info(f"🔍 [SYNC DEBUG] Calling create_user with:")
                logger.info(f"🔍 [SYNC DEBUG] - oauth_provider: supabase")
                logger.info(f"🔍 [SYNC DEBUG] - oauth_id: {user_id}")
                logger.info(f"🔍 [SYNC DEBUG] - is_guest: {is_guest}")
                logger.info(f"🔍 [SYNC DEBUG] - profile_picture: {supabase_user.get('user_metadata', {}).get('avatar_url')}")
                
                # Create the user
                new_user = create_user(
                    db=db,
                    user=user_data,
                    oauth_provider="supabase",
                    oauth_id=user_id,
                    profile_picture=supabase_user.get("user_metadata", {}).get("avatar_url"),
                    is_guest=is_guest
                )
                
                logger.info(f"🔍 [SYNC DEBUG] create_user call completed successfully")
                
                # Commit the transaction
                db.commit()
                logger.info(f"🔍 [SYNC DEBUG] Database transaction committed")
                
                db.refresh(new_user)
                logger.info(f"🔍 [SYNC DEBUG] User object refreshed from database")
                
                logger.info(f"🔍 [SYNC DEBUG] ✅ Successfully created new user:")
                logger.info(f"🔍 [SYNC DEBUG] - Database ID: {new_user.id}")
                logger.info(f"🔍 [SYNC DEBUG] - Email: {new_user.email}")
                logger.info(f"🔍 [SYNC DEBUG] - Username: {new_user.username}")
                logger.info(f"🔍 [SYNC DEBUG] - Is guest: {new_user.is_guest}")
                logger.info(f"🔍 [SYNC DEBUG] - OAuth ID: {new_user.oauth_id}")
                logger.info(f"🔍 [SYNC DEBUG] - OAuth Provider: {new_user.oauth_provider}")
                
                return new_user
                
            except Exception as e:
                db.rollback()
                logger.error(f"🔍 [SYNC DEBUG] ❌ Database error in user sync: {str(e)}")
                logger.error(f"🔍 [SYNC DEBUG] Exception type: {type(e).__name__}")
                import traceback
                logger.error(f"🔍 [SYNC DEBUG] Full traceback: {traceback.format_exc()}")
                return None
            finally:
                db.close()
                logger.info(f"🔍 [SYNC DEBUG] Database connection closed")
                
        except Exception as e:
            logger.error(f"🔍 [SYNC DEBUG] ❌ General error in user sync: {str(e)}")
            logger.error(f"🔍 [SYNC DEBUG] Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"🔍 [SYNC DEBUG] Full traceback: {traceback.format_exc()}")
            return None 