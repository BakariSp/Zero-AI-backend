from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncio

from app.users.routes import router as users_router
from app.learning_paths.routes import router as learning_paths_router
from app.cards.routes import router as cards_router
from app.daily_logs.routes import router as daily_logs_router
from app.achievements.routes import router as achievements_router
from app.sections.routes import router as sections_router
from app.learning_path_courses.routes import router as learning_path_courses_router
from app.recommendation.routes import router as recommendation_router
from app.auth.oauth import router as oauth_router
from app.courses.routes import router as courses_router
from app.tasks.routes import router as tasks_router
from app.planner.ai import router as planner_router

app = FastAPI(
    title="AI Learning Guide API",
    description="API for AI-powered learning path generation and tracking",
    version="1.0.0"
)

# Configure CORS
origins = [
    "http://localhost",
    "http://localhost:3000",  # React frontend
    "http://localhost:8080",  # Vue frontend
    os.getenv("FRONTEND_URL", "")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users_router, prefix="/api", tags=["users"])
app.include_router(learning_paths_router, prefix="/api", tags=["learning_paths"])
app.include_router(cards_router, prefix="/api", tags=["cards"])
app.include_router(daily_logs_router, prefix="/api", tags=["daily_logs"])
app.include_router(achievements_router, prefix="/api", tags=["achievements"])
app.include_router(sections_router, prefix="/api", tags=["sections"])
app.include_router(learning_path_courses_router, prefix="/api", tags=["learning_path_courses"])
app.include_router(recommendation_router, prefix="/api", tags=["recommendations"])
app.include_router(oauth_router, prefix="/oauth", tags=["oauth"])
app.include_router(courses_router, prefix="/api", tags=["courses"])
app.include_router(tasks_router, prefix="/api", tags=["tasks"])
app.include_router(planner_router, prefix="/api/ai", tags=["AI Planner"])

@app.get("/")
def read_root():
    return {
        "message": "Welcome to the AI Learning Guide API",
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.on_event("startup")
async def startup_event():
    # Initialize background tasks
    from app.services.cache import periodic_cache_cleanup
    asyncio.create_task(periodic_cache_cleanup()) 