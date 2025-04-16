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
# Load environment variables from .env file
load_dotenv()
print("Environment variables loaded:")
print(f"MICROSOFT_CLIENT_ID: {'Yes' if os.getenv('MICROSOFT_CLIENT_ID') else 'No'}")
print(f"GOOGLE_CLIENT_ID: {'Yes' if os.getenv('GOOGLE_CLIENT_ID') else 'No'}")

app = FastAPI(title="Zero AI API")

# Add SessionMiddleware - this is required for OAuth
app.add_middleware(
    SessionMiddleware, 
    secret_key=os.getenv("SESSION_SECRET_KEY", "your-secret-key-here")  # Use environment variable
)

# Configure CORS
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url],  # Only allow requests from your frontend
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Add middleware for user authentication
@app.middleware("http")
async def add_user_to_request(request: Request, call_next):
    user = get_user_from_request(request)
    request.state.user = user
    response = await call_next(request)
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
# Initialize database on startup
@app.on_event("startup")
def startup_db_client():
    init_db()

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
