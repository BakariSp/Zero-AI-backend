from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.db import init_db
from app.api import router as api_router
from app.auth import get_user_from_request
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # Startup code (runs before the app starts)
    init_db()
    yield
    # Shutdown code (runs when the app is shutting down)
    pass

app = FastAPI(lifespan=lifespan)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加中间件来处理用户认证
@app.middleware("http")
async def add_user_to_request(request: Request, call_next):
    user = get_user_from_request(request)
    request.state.user = user
    response = await call_next(request)
    return response

# 包含API路由
app.include_router(api_router, prefix="/api")

# 添加一个根路由用于健康检查
@app.get("/")
async def root():
    return {"status": "API is running"}
