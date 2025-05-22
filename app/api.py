from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import SessionLocal, test_connection
from app.utils import get_azure_openai_client
import os
from datetime import datetime
import time
import logging

router = APIRouter()

# Database dependency
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
        # Test the connection
        connection_result = test_connection()
        
        if connection_result:
            return {
                "status": "success",
                "code": 200,
                "message": "Database connection successful",
                "data": {
                    "test_value": 1,
                    "db_type": "PostgreSQL",
                    "connection_info": "Connected to Supabase PostgreSQL database",
                    "connection_method": "Direct connection test successful"
                },
                "timestamp": datetime.now().isoformat()
            }
        
        # If the direct test fails, try the SQLAlchemy approach
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
                    "db_type": "PostgreSQL",
                    "connection_info": "Connected to Supabase PostgreSQL database",
                    "connection_method": "SQLAlchemy connection successful"
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
        import traceback
        error_details = traceback.format_exc()
        
        return {
            "status": "error",
            "code": 500,
            "message": f"Database connection failed: {str(e)}",
            "error_details": error_details,
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

@router.get("/test-ai")
async def test_ai_connection():
    """Test the currently configured AI service (Azure OpenAI or Zhipu AI)"""
    try:
        from app.utils import get_ai_client, get_model_deployment
        import traceback
        
        # Determine which AI provider is being used
        provider = "Zhipu AI" if os.getenv("USE_ZHIPU_AI", "false").lower() == "true" else "Azure OpenAI"
        logging.info(f"Testing AI connection using provider: {provider}")
        
        # Get client and model
        client = get_ai_client()
        model = get_model_deployment()
        logging.info(f"Using model: {model}")
        
        # Make test request
        start_time = time.time()
        try:
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": "Hello, are you working?"}],
                max_tokens=50,
                model=model
            )
            elapsed_time = time.time() - start_time
            
            # Log response for debugging
            if provider == "Zhipu AI":
                logging.info(f"Zhipu AI response: {response}")
                logging.info(f"Response type: {type(response)}")
                logging.info(f"Has choices: {hasattr(response, 'choices')}")
                if hasattr(response, 'choices') and len(response.choices) > 0:
                    logging.info(f"First choice: {response.choices[0]}")
            
            return {
                "status": "success",
                "code": 200,
                "message": f"{provider} connection successful",
                "data": {
                    "provider": provider,
                    "response": response.choices[0].message.content,
                    "model": model,
                    "response_time_seconds": round(elapsed_time, 2)
                },
                "timestamp": datetime.now().isoformat()
            }
        except AttributeError as e:
            # Handle specific structural errors that might occur with Zhipu AI
            error_msg = f"Attribute error when accessing response: {str(e)}"
            logging.error(error_msg)
            logging.error(traceback.format_exc())
            return {
                "status": "error",
                "code": 500,
                "message": f"{provider} connection failed: {error_msg}",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            # Handle general request errors
            error_msg = f"Error making request to {provider}: {str(e)}"
            logging.error(error_msg)
            logging.error(traceback.format_exc())
            return {
                "status": "error",
                "code": 500,
                "message": error_msg,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        provider = "Zhipu AI" if os.getenv("USE_ZHIPU_AI", "false").lower() == "true" else "Azure OpenAI"
        error_msg = f"{provider} client initialization failed: {str(e)}"
        logging.error(error_msg)
        logging.error(traceback.format_exc())
        return {
            "status": "error",
            "code": 500,
            "message": error_msg,
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

