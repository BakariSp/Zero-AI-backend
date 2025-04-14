from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.utils import get_azure_openai_client
import os
from datetime import datetime
import time

router = APIRouter()

# 数据库依赖
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/me")
def read_current_user(request: Request):
    user = request.state.user
    if not user:
        raise HTTPException(
            status_code=401, 
            detail={
                "status": "error",
                "code": 401,
                "message": "Not authenticated",
                "timestamp": datetime.now().isoformat()
            }
        )
    return {
        "status": "success",
        "code": 200,
        "message": "User information retrieved successfully",
        "data": {
            "user": user
        },
        "timestamp": datetime.now().isoformat()
    }

@router.get("/test-db-connection")
async def test_db_connection():
    try:
        db = SessionLocal()
        result = db.execute(text("SELECT 1 as test_value")).fetchone()
        db.close()
        
        if result:
            return {
                "status": "success",
                "code": 200,
                "message": "Database connection successful",
                "data": {
                    "test_value": result[0],
                    "db_type": "MySQL",
                    "connection_info": "Connected to Azure MySQL database"
                },
                "timestamp": datetime.now().isoformat()
            }
        return {
            "status": "error",
            "code": 500,
            "message": "Database connection established but no result returned",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "code": 500,
            "message": f"Database connection failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

@router.get("/test-openai")
async def test_openai_connection():
    try:
        client = get_azure_openai_client()
        start_time = time.time()
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": "Hello, are you working?"}],
            max_tokens=50,
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
        )
        elapsed_time = time.time() - start_time
        
        return {
            "status": "success",
            "code": 200,
            "message": "OpenAI connection successful",
            "data": {
                "response": response.choices[0].message.content,
                "model": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
                "response_time_seconds": round(elapsed_time, 2)
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "code": 500,
            "message": f"OpenAI connection failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

@router.get("/public-test", include_in_schema=True)
async def public_test():
    """此端点不需要任何认证，用于测试API是否正常运行"""
    return {
        "status": "success",
        "code": 200,
        "message": "Public API endpoint is working",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

