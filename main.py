import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.auth import get_user_from_request, get_current_active_user
from app.auth.middleware import SupabaseAuthMiddleware
from app.users.routes import router as users_router
from app.auth.jwt import router as auth_router
from app.auth.guest import router as guest_router
from app.auth.supabase import router as supabase_router
from app.cards.routes import router as cards_router
from app.db import init_db
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response
from fastapi.encoders import jsonable_encoder
from datetime import datetime
import json
from fastapi.security import OAuth2PasswordBearer
from app.users.schemas import UserResponse
from app.models import User
from app.learning_paths.routes import router as learning_paths_router
from app.daily_logs.routes import router as daily_logs_router
from app.achievements.routes import router as achievements_router
from app.courses.routes import router as courses_router
from app.sections.routes import router as sections_router
from app.learning_path_courses.routes import router as learning_path_courses_router
from app.recommendation.routes import router as recommendation_router
from sqlalchemy import text
from app.auth.oauth import router as oauth_router
from app.backend_tasks.routes import router as backend_tasks_router
from app.user_tasks.routes import router as user_tasks_router
from app.user_daily_usage.routes import router as user_daily_usage_router
from app.planner.ai import router as planner_router
from app.routers.learning_assistant import router as learning_assistant_router
from app.routes import router as app_routes
from app.scheduler import start_scheduler
import logging
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

# Configure basic logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()
print("Environment variables loaded:")
print(f"MICROSOFT_CLIENT_ID: {'Yes' if os.getenv('MICROSOFT_CLIENT_ID') else 'No'}")
print(f"GOOGLE_CLIENT_ID: {'Yes' if os.getenv('GOOGLE_CLIENT_ID') else 'No'}")
print(f"SUPABASE_URL: {'Yes' if os.getenv('SUPABASE_URL') else 'No'}")
print(f"SUPABASE_KEY: {'Yes' if os.getenv('SUPABASE_KEY') else 'No'}")

app = FastAPI(title="Zero AI API")

# Define CORS origins before using middleware
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
origins = [
    "http://localhost",
    "http://localhost:3000",  # React frontend
    "http://127.0.0.1:3000",  # Also allow 127.0.0.1
    "http://localhost:8080",  # Vue frontend
    "https://learnfromzero.app",  # Production domain
    "https://www.learnfromzero.app",  # www subdomain if used
    frontend_url
]
# Remove empty origins
origins = [origin for origin in origins if origin]

# OPTIONS preflight request handler middleware - this must be added FIRST
@app.middleware("http")
async def options_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        # For CORS preflight requests, return a minimal 200 response
        log.info(f"OPTIONS middleware handling request to: {request.url.path}")
        
        # Create a minimal response
        response = Response(status_code=200)
        
        # Set basic CORS headers
        origin = request.headers.get("Origin")
        # Check if the origin is in our allowed origins
        if origin in origins:
            response.headers["Access-Control-Allow-Origin"] = origin
        else:
            # Fallback to the frontend URL
            response.headers["Access-Control-Allow-Origin"] = frontend_url
            
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept, Origin, X-Requested-With, Access-Control-Request-Method, Access-Control-Request-Headers, X-CSRF-Token, X-MS-CLIENT-PRINCIPAL, X-Supabase-User"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Max-Age"] = "86400"  # 24 hours
        
        return response
        
    return await call_next(request)

# Add SessionMiddleware - this is required for OAuth
app.add_middleware(
    SessionMiddleware, 
    secret_key=os.getenv("SESSION_SECRET_KEY", "your-secret-key-here"),  # Use environment variable
    max_age=14400,  # Extend session lifetime to 4 hours
    same_site="lax",  # Allow cross-site cookies for OAuth redirects
    session_cookie="zero_session",  # Use a custom cookie name
    https_only=os.getenv("ENVIRONMENT", "development").lower() == "production",  # Secure in production
)

# Log session configuration
log.info(f"Session middleware configured with:")
log.info(f"- Cookie name: zero_session")
log.info(f"- Max age: 14400 seconds (4 hours)")
log.info(f"- Same site: lax")
log.info(f"- HTTPS only: {os.getenv('ENVIRONMENT', 'development').lower() == 'production'}")
log.info(f"- Secret key available: {bool(os.getenv('SESSION_SECRET_KEY'))}")

# Configure CORS - use a simpler configuration that allows all headers and methods
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Use the specific origins defined above
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["Content-Type", "Authorization"],
    max_age=86400,  # Cache preflight response for 24 hours
)

# Add Supabase authentication middleware
app.add_middleware(SupabaseAuthMiddleware)

# Add a middleware to ensure CORS headers are set on all responses
class EnsureCORSHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Continue with the regular request processing
        response = await call_next(request)
        
        # Check if the response already has CORS headers
        if "Access-Control-Allow-Origin" not in response.headers:
            # Get origin from request
            origin = request.headers.get("Origin")
            
            # Only set CORS headers if origin is present
            if origin:
                # Check if the origin is in our allowed origins
                if origin in origins:
                    response.headers["Access-Control-Allow-Origin"] = origin
                else:
                    # Fallback to the frontend URL if origin not in allowed list
                    response.headers["Access-Control-Allow-Origin"] = frontend_url
                    
                response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response

app.add_middleware(EnsureCORSHeadersMiddleware)

# Security headers middleware for production
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

# Temporarily remove TrustedHostMiddleware to diagnose the issue
# is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
# if is_production:
#     app.add_middleware(SecurityHeadersMiddleware)
#     
#     # Only add HTTPS redirect in production and if not behind a proxy that terminates SSL
#     if not os.getenv("BEHIND_PROXY", "false").lower() == "true":
#         app.add_middleware(HTTPSRedirectMiddleware)
#     
#     # Add trusted host middleware in production
#     app.add_middleware(
#         TrustedHostMiddleware, 
#         allowed_hosts=["learnfromzero.app", "www.learnfromzero.app", os.getenv("ALLOWED_HOST", "*")]
#     )
#     
#     log.info("Production security middleware enabled")
# else:
#     # Allow localhost and 127.0.0.1 in development
#     app.add_middleware(
#         TrustedHostMiddleware, 
#         allowed_hosts=["localhost", "127.0.0.1", os.getenv("ALLOWED_HOST", "*")]
#     )
#     log.info("Development environment: TrustedHostMiddleware configured for localhost")

# Add middleware for user authentication - should come AFTER OPTIONS middleware
@app.middleware("http")
async def add_user_to_request(request: Request, call_next):
    # Skip authentication for OPTIONS requests
    if request.method == "OPTIONS":
        logging.info(f"Authentication middleware skipping OPTIONS request to: {request.url.path}")
        # For OPTIONS, just call next middleware without doing any auth
        return await call_next(request)
    
    # Log the requested path to help with debugging
    logging.info(f"Processing request for path: {request.url.path}, method: {request.method}")
    
    # Log Authorization header presence (not content for security)
    auth_header = request.headers.get("Authorization")
    logging.info(f"Authorization header present: {auth_header is not None}")
    
    # IMPORTANT: Make sure we're using the correct path
    # Add original path for routing checks
    if not hasattr(request.state, "original_path"):
        request.state.original_path = request.url.path
    
    # Note: The SupabaseAuthMiddleware will have already populated request.state.user if using Supabase
    # Only try the legacy authentication if no user was found by Supabase
    if not hasattr(request.state, "user") or request.state.user is None:
        try:
            user = get_user_from_request(request)
            
            # Only set user if we found one through legacy methods
            if user:
                request.state.user = user
                logging.info(f"User identified through legacy middleware: {user.get('userId', 'unknown')}")
            else:
                logging.info("No user identified through legacy middleware")
        except Exception as e:
            logging.warning(f"Error during legacy authentication: {str(e)}")
            # Don't set user if there was an error
            pass
    else:
        # Check what type of user we got from Supabase middleware
        if isinstance(request.state.user, dict):
            logging.info(f"Request already has legacy user from Supabase middleware: {request.state.user.get('userId', 'unknown')}")
        else:
            logging.info(f"Request already has DB user from Supabase middleware: {request.state.user.id}")
    
    # For debugging, check the state of authentication before proceeding
    if hasattr(request.state, "user") and request.state.user is not None:
        if isinstance(request.state.user, dict):
            logging.info(f"Request will proceed with legacy user: {request.state.user.get('userId', 'unknown')}")
        else:
            logging.info(f"Request will proceed with DB user: {request.state.user.id}")
    else:
        # Check if we have supabase_user but not user
        if hasattr(request.state, "supabase_user") and request.state.supabase_user is not None:
            logging.info(f"Request has supabase_user data but no user object. This might indicate a database sync issue.")
        
        logging.info(f"Request will proceed without authenticated user")
    
    # Log authentication state
    logging.info(f"Authentication check for path: {request.url.path}")
    logging.info(f"Authorization header present: {auth_header is not None}")
    
    if auth_header and auth_header.startswith("Bearer "):
        logging.info(f"Successfully validated token for {request.url.path}")
    
    response = await call_next(request)
    
    # If unauthorized response, log the path for debugging
    if response.status_code == 401:
        logging.warning(f"Unauthorized access to path: {request.url.path}")
        
        # Add debug header for tracing
        response.headers["X-Debug-Path"] = request.url.path
        if hasattr(request.state, "user") and request.state.user is not None:
            user_id = getattr(request.state.user, "id", "unknown") 
            response.headers["X-Debug-User-Present"] = "true"
            response.headers["X-Debug-User-ID"] = str(user_id)
        else:
            response.headers["X-Debug-User-Present"] = "false"
    
    return response

# Include routers - make sure the prefix is correct
app.include_router(users_router, prefix="/api", tags=["users"])
app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(guest_router, prefix="/api", tags=["guest"])
app.include_router(supabase_router, prefix="/api/auth/supabase", tags=["supabase"])
app.include_router(cards_router, prefix="/api", tags=["cards"])
app.include_router(learning_paths_router, prefix="/api", tags=["learning_paths"])
app.include_router(daily_logs_router, prefix="/api", tags=["daily_logs"])
app.include_router(achievements_router, prefix="/api", tags=["achievements"])
app.include_router(courses_router, prefix="/api", tags=["courses"])
app.include_router(sections_router, prefix="/api", tags=["sections"])
app.include_router(learning_path_courses_router, prefix="/api", tags=["learning_path_courses"])
app.include_router(recommendation_router, prefix="/api", tags=["recommendation"])
app.include_router(oauth_router, prefix="/api/oauth", tags=["oauth"])
app.include_router(backend_tasks_router, prefix="/api/backend-tasks", tags=["backend_tasks"])
app.include_router(user_tasks_router, prefix="/api/user-tasks", tags=["user_tasks"])
app.include_router(user_daily_usage_router, prefix="/api/daily-usage", tags=["user_daily_usage"])
app.include_router(planner_router, prefix="/api/planner", tags=["planner"])
app.include_router(learning_assistant_router, prefix="/api/learning-assistant", tags=["learning_assistant"])
app.include_router(app_routes, prefix="/api", tags=["app"])

# Startup event - initialize database
@app.on_event("startup")
def startup_db_client():
    init_db()
    print("Database initialized")
    
    # Start the background scheduler
    try:
        start_scheduler()
        print("Background scheduler started")
    except Exception as e:
        print(f"Warning: Could not start scheduler: {e}")
        # Don't raise here, the app can still function without the scheduler

# Custom JSON encoder for handling datetime
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Add a global OPTIONS handler
@app.options("/{path:path}")
async def options_handler(path: str, request: Request):
    """
    Global OPTIONS handler for CORS preflight requests.
    This is a fallback in case an individual route doesn't have its own OPTIONS handler.
    """
    response = Response(status_code=200)
    
    # Get origin from request headers
    origin = request.headers.get("Origin")
    
    # Only set CORS headers if origin is present
    if origin:
        # Check if the origin is in our allowed origins
        if origin in origins:
            response.headers["Access-Control-Allow-Origin"] = origin
        else:
            # Fallback to the frontend URL if origin not in allowed list
            response.headers["Access-Control-Allow-Origin"] = frontend_url
            
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept, X-Requested-With, Origin, Access-Control-Request-Method, Access-Control-Request-Headers"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Max-Age"] = "86400"  # 24 hours
    
    return response

@app.get("/")
def read_root():
    """Root endpoint for health check and basic information"""
    return {
        "name": "Zero AI API",
        "version": "1.0.0",
        "status": "running"
    }

# When running in production, use:
# uvicorn main:app --host 0.0.0.0 --port $PORT
# This allows the app to be accessible from outside the container/VM

"""
PRODUCTION DEPLOYMENT NOTES:
---------------------------
Environment variables for production:

1. ENVIRONMENT = "production"  
   - Enables production security middleware

2. FRONTEND_URL = "https://learnfromzero.app"  
   - Your frontend URL for CORS

3. BEHIND_PROXY = "true" or "false"  
   - Set to "true" if behind a proxy that terminates SSL

4. ALLOWED_HOST = "learnfromzero.app"  
   - Your application's hostname for TrustedHostMiddleware

5. SESSION_SECRET_KEY = [secure random string]  
   - Secret key for session middleware

6. JWT_SECRET_KEY = [secure random string]  
   - Secret key for JWT tokens

7. DATABASE_URL = [your database connection string]  
   - Production database connection

8. PORT = [port number]  
   - The port your app should listen on
"""
