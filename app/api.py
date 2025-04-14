from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.utils import get_azure_openai_client
import os

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
    return request.state.user or {"msg": "Not signed in"}

@router.get("/test-db-connection")
async def test_db_connection():
    try:
        db = SessionLocal()
        result = db.execute(text("SELECT 1")).fetchone()
        db.close()
        
        if result:
            return {"status": "success", "message": "Database connection successful", "result": result[0]}
        return {"status": "error", "message": "No result returned"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/test-openai")
async def test_openai_connection():
    try:
        client = get_azure_openai_client()
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": "Hello, are you working?"}],
            max_tokens=50,
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
        )
        return {"status": "success", "message": "OpenAI connection successful", "response": response.choices[0].message.content}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/public-test", include_in_schema=True)
async def public_test():
    """此端点不需要任何认证，用于测试API是否正常运行"""
    return {"status": "success", "message": "Public API endpoint is working"}

