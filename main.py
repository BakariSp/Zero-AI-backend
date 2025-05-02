import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.auth import get_user_from_request, get_current_active_user
from app.users.routes import router as users_router
from app.auth.jwt import router as auth_router
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
        # For CORS preflight requests, return an empty 200 response with appropriate CORS headers
        origin = request.headers.get("Origin", "")
        path = request.url.path
        
        log.info(f"OPTIONS request received for path: {path}")
        log.info(f"OPTIONS request headers: {request.headers}")
        
        # Create a response with appropriate CORS headers
        response = Response(status_code=200)
        
        # Check if the origin is in the allowed origins
        if origin in origins or "*" in origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            log.info(f"Setting Access-Control-Allow-Origin: {origin}")
        elif len(origins) > 0:
            response.headers["Access-Control-Allow-Origin"] = origins[0]
            log.info(f"Setting Access-Control-Allow-Origin: {origins[0]} (default)")
            
        # Add other CORS headers
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept, X-Requested-With, Origin, Access-Control-Request-Method, Access-Control-Request-Headers"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Max-Age"] = "86400"  # Cache preflight response for 24 hours
        
        log.info(f"Handling OPTIONS preflight request for path: {path}, origin: {origin}")
        log.info(f"Response headers: {response.headers}")
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

# Configure CORS - should be early in the middleware stack
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Use our defined origins list
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With", "Origin", "Access-Control-Request-Method", "Access-Control-Request-Headers"],
    expose_headers=["Content-Length", "Content-Type"],
    max_age=86400,  # Cache preflight response for 24 hours
)

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
        return await call_next(request)
    
    # Log the requested path to help with debugging
    logging.info(f"Processing request for path: {request.url.path}, method: {request.method}")
    
    # Log Authorization header presence (not content for security)
    auth_header = request.headers.get("Authorization")
    logging.info(f"Authorization header present: {auth_header is not None}")
    
    user = get_user_from_request(request)
    request.state.user = user
    
    # Log if user was found through the middleware
    if user:
        logging.info(f"User identified through middleware: {user.get('userId', 'unknown')}")
    else:
        logging.info("No user identified through middleware, will try JWT auth")
    
    response = await call_next(request)
    
    # If unauthorized response, log the path for debugging
    if response.status_code == 401:
        logging.warning(f"Unauthorized access to path: {request.url.path}")
    
    return response

# Include routers - make sure the prefix is correct
app.include_router(users_router, prefix="/api", tags=["users"])
app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(cards_router, prefix="/api", tags=["cards"])
app.include_router(learning_paths_router, prefix="/api", tags=["learning_paths"])
app.include_router(daily_logs_router, prefix="/api", tags=["daily_logs"])
app.include_router(achievements_router, prefix="/api", tags=["achievements"])
app.include_router(courses_router, prefix="/api", tags=["courses"])
app.include_router(sections_router, prefix="/api", tags=["sections"])
app.include_router(learning_path_courses_router, prefix="/api", tags=["learning_path_courses"])
app.include_router(recommendation_router, prefix="/api", tags=["recommendations"])
app.include_router(oauth_router, prefix="/oauth", tags=["oauth"])
app.include_router(backend_tasks_router, prefix="/api", tags=["backend_tasks"])
app.include_router(user_tasks_router, prefix="/api", tags=["user_tasks"])
app.include_router(user_daily_usage_router, prefix="/api", tags=["user_daily_usage"])
app.include_router(planner_router, prefix="/api/ai", tags=["AI Planner"])
app.include_router(learning_assistant_router, prefix="/api", tags=["learning_assistant"])
app.include_router(app_routes, prefix="/api", tags=["app"])
# Initialize database on startup
@app.on_event("startup")
def startup_db_client():
    init_db()
    log.info("Database initialized")
    # Log the origins allowed for CORS
    log.info(f"CORS allowed origins: {origins}")

# Custom JSON encoder for datetime objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Set the custom encoder for FastAPI
app.json_encoder = CustomJSONEncoder

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.get("/")
def read_root():
    return {"message": "Welcome to Zero AI API"}

@app.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

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
