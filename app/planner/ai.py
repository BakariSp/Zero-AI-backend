import logging
import json
from fastapi import APIRouter, Depends, Body, HTTPException
from typing import Dict, Any
from datetime import datetime

# Import your agent and dependency functions
from app.services.agents.dialogue_planner import DialoguePlannerAgent
from app.utils import get_ai_client, get_model_deployment  # Use correct function names
from app.services.agents.dialogue_planner import DialogueInput # Import the input model

router = APIRouter()

def get_general_model_deployment() -> str:
    """Dependency function to get general model deployment"""
    return get_model_deployment(is_card_model=False)

@router.post(
    "/dialogue",
    # response_model=DialogueResponse, # Add if you define a response model
    summary="Process user input via Dialogue Planner",
    description="""Receives user input, optional chat history, and the current learning plan.
Determines intent, calls appropriate sub-agents (PathPlanner, CourseGenerator, etc.),
and returns a structured response including an AI reply and generated content.""",
)
async def handle_dialogue_endpoint(
    payload: DialogueInput = Body(...),
    client = Depends(get_ai_client),  # Use unified client (ZhipuAI or AzureOpenAI)
    deployment: str = Depends(get_general_model_deployment) # Get general model deployment
) -> Dict[str, Any]:
    """
    Handles conversational input for learning path generation and modification.
    """
    try:
        logging.info(f"Dialogue endpoint called with user_input: '{payload.user_input[:50]}...'")
        logging.info(f"Client type: {type(client)}")
        logging.info(f"Deployment: {deployment}")
        
        # Instantiate the DialoguePlannerAgent
        logging.info("Initializing DialoguePlannerAgent...")
        try:
            dialogue_planner = DialoguePlannerAgent(client=client, deployment=deployment)
            logging.info("DialoguePlannerAgent initialized successfully")
        except Exception as init_error:
            logging.error(f"Failed to initialize DialoguePlannerAgent: {init_error}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Agent initialization failed: {init_error}")

        # Prepare the context for the agent
        context = {
            "current_plan": payload.current_plan,
            "chat_history": payload.chat_history
        }
        logging.info(f"Context prepared: current_plan={payload.current_plan is not None}, chat_history_length={len(payload.chat_history)}")

        # Process the input using the agent
        logging.info("Starting AI processing...")
        try:
            response = await dialogue_planner.process_user_input(
                user_input=payload.user_input,
                context=context
            )
            logging.info("AI processing completed successfully")
        except Exception as process_error:
            logging.error(f"Failed during process_user_input: {process_error}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"AI processing failed: {process_error}")
        
        # Add response construction logging as suggested by frontend team
        logging.info("Starting response construction...")
        logging.info(f"Response data type: {type(response)}")
        
        # Log the keys and basic structure of the response
        if isinstance(response, dict):
            logging.info(f"Response keys: {list(response.keys())}")
            if "result" in response:
                result = response["result"]
                logging.info(f"Result type: {type(result)}")
                if isinstance(result, dict):
                    logging.info(f"Result keys: {list(result.keys())}")
                    # Log each result component type
                    for key, value in result.items():
                        logging.info(f"Result[{key}] type: {type(value)}, is None: {value is None}")
                        if isinstance(value, list):
                            logging.info(f"Result[{key}] length: {len(value)}")
        
        # Validate response structure
        if not isinstance(response, dict):
            raise ValueError(f"Expected dict response, got {type(response)}")
        
        required_keys = ['ai_reply', 'result', 'status', 'triggered_agent']
        missing_keys = [key for key in required_keys if key not in response]
        if missing_keys:
            raise ValueError(f"Response missing required keys: {missing_keys}")
        
        # Check for circular references and complex objects before JSON serialization
        logging.info("Checking for potential serialization issues...")
        
        def check_serializability(obj, path="root", max_depth=10):
            """Recursively check if an object is JSON serializable"""
            if max_depth <= 0:
                logging.warning(f"Max depth reached at {path}, potential circular reference")
                return False
                
            try:
                if obj is None or isinstance(obj, (str, int, float, bool)):
                    return True
                elif isinstance(obj, (list, tuple)):
                    for i, item in enumerate(obj):
                        if not check_serializability(item, f"{path}[{i}]", max_depth - 1):
                            return False
                    return True
                elif isinstance(obj, dict):
                    for key, value in obj.items():
                        if not check_serializability(value, f"{path}.{key}", max_depth - 1):
                            return False
                    return True
                else:
                    logging.error(f"Non-serializable type at {path}: {type(obj)}")
                    return False
            except Exception as e:
                logging.error(f"Error checking serializability at {path}: {e}")
                return False
        
        if not check_serializability(response):
            raise ValueError("Response contains non-serializable objects")
        
        # Test JSON serialization
        try:
            json_string = json.dumps(response, ensure_ascii=False, default=str)
            logging.info(f"JSON serialization successful, length: {len(json_string)} bytes")
            
            # Check if response is too large
            if len(json_string) > 1024 * 1024:  # 1MB
                logging.warning(f"Response size is very large: {len(json_string)} bytes")
                
        except Exception as json_error:
            logging.error(f"JSON serialization failed: {json_error}")
            logging.error(f"JSON error type: {type(json_error)}")
            
            # Try to identify the problematic part
            try:
                json.dumps(response.get("ai_reply", ""), default=str)
                logging.info("ai_reply is serializable")
            except Exception as e:
                logging.error(f"ai_reply serialization failed: {e}")
                
            try:
                json.dumps(response.get("status", {}), default=str)
                logging.info("status is serializable")
            except Exception as e:
                logging.error(f"status serialization failed: {e}")
                
            try:
                json.dumps(response.get("result", {}), default=str)
                logging.info("result is serializable")
            except Exception as e:
                logging.error(f"result serialization failed: {e}")
                
            raise ValueError(f"Response not JSON serializable: {json_error}")
        
        logging.info(f"Response construction successful. AI reply length: {len(response.get('ai_reply', ''))}")
        logging.info(f"Response status: {response.get('status', {})}")
        
        # Create a clean response structure to ensure no database objects are included
        clean_response = {
            "ai_reply": str(response.get("ai_reply", "")),
            "status": {
                "has_learning_path": bool(response.get("status", {}).get("has_learning_path", False)),
                "has_courses": bool(response.get("status", {}).get("has_courses", False)),
                "has_sections": bool(response.get("status", {}).get("has_sections", False)),
                "has_cards": bool(response.get("status", {}).get("has_cards", False))
            },
            "result": {},
            "triggered_agent": str(response.get("triggered_agent", "Unknown"))
        }
        
        # Safely copy result components
        result = response.get("result", {})
        if result.get("learning_path"):
            clean_response["result"]["learning_path"] = dict(result["learning_path"]) if result["learning_path"] else None
        if result.get("courses"):
            clean_response["result"]["courses"] = list(result["courses"]) if result["courses"] else None
        if result.get("sections"):
            clean_response["result"]["sections"] = list(result["sections"]) if result["sections"] else None
        if result.get("cards"):
            clean_response["result"]["cards"] = list(result["cards"]) if result["cards"] else None
        
        # Final serialization test of clean response
        try:
            json.dumps(clean_response, ensure_ascii=False, default=str)
            logging.info("Clean response JSON serialization successful")
        except Exception as e:
            logging.error(f"Clean response serialization failed: {e}")
            raise ValueError(f"Clean response not serializable: {e}")
        
        return clean_response

    except ValueError as ve:
        # Catch specific errors like JSON parsing issues from agents
        logging.error(f"Input or Agent Processing Error: {ve}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Input or Agent Processing Error: {ve}")
    except RuntimeError as re:
        # Catch initialization errors or other runtime issues
        logging.error(f"Agent Initialization Error: {re}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent Initialization Error: {re}")
    except Exception as e:
        # General error handler
        # Log the error details here
        logging.error(f"Unexpected error in /dialogue endpoint: {e}", exc_info=True)
        logging.error(f"Exception type: {type(e)}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")

@router.get("/test")
async def test_endpoint():
    """
    Simple test endpoint to verify the planner API is accessible.
    Returns a minimal response for connectivity testing.
    """
    return {
        "status": "success",
        "message": "Planner API is working",
        "endpoint": "/api/planner/test"
    }

@router.post("/dialogue-test")
async def test_dialogue_endpoint(payload: DialogueInput = Body(...)):
    """
    Minimal test version of the dialogue endpoint that returns a fixed response
    without calling any AI agents. Use this to test endpoint connectivity and
    request/response structure without AI processing complexity.
    """
    try:
        logging.info(f"Test dialogue endpoint called with user_input: '{payload.user_input[:50]}...'")
        
        # Return minimal response for testing
        test_response = {
            "status": {
                "has_learning_path": True,
                "has_courses": True,
                "has_sections": True,
                "has_cards": False
            },
            "result": {
                "learning_path": {"title": "Test Learning Path", "description": "This is a test path"},
                "courses": [{"title": "Test Course", "description": "This is a test course"}],
                "sections": None,
                "cards": None
            },
            "ai_reply": "I've generated a test learning path for you. This is just a test response.",
            "triggered_agent": "Test"
        }
        
        # Test JSON serialization
        import json
        json.dumps(test_response, ensure_ascii=False, default=str)
        logging.info("Test response JSON serialization successful")
        
        return test_response
        
    except Exception as e:
        logging.error(f"Test dialogue endpoint error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Test endpoint error: {e}")

@router.options("/cors-test")
@router.get("/cors-test")
async def cors_test_endpoint():
    """
    Test endpoint for CORS validation.
    This endpoint returns a simple success message and can be used to test if CORS is properly configured.
    """
    return {
        "status": "success",
        "message": "CORS is working properly for the planner API",
        "timestamp": str(datetime.now())
    }

@router.post("/dialogue-debug")
async def debug_dialogue_endpoint(
    payload: DialogueInput = Body(...),
) -> Dict[str, Any]:
    """
    Debug version of the dialogue endpoint that logs everything and returns a simple response
    without calling any AI agents. Use this to debug communication issues.
    """
    try:
        logging.info(f"=== DEBUG DIALOGUE ENDPOINT ===")
        logging.info(f"Received payload: {payload}")
        logging.info(f"User input: '{payload.user_input}'")
        logging.info(f"Current plan: {payload.current_plan}")
        logging.info(f"Chat history: {payload.chat_history}")
        
        # Return a simple test response
        debug_response = {
            "ai_reply": f"Debug: Received your message '{payload.user_input}'. This is a test response.",
            "status": {
                "has_learning_path": False,
                "has_courses": False,
                "has_sections": False,
                "has_cards": False
            },
            "result": {},
            "triggered_agent": "Debug"
        }
        
        logging.info(f"Returning debug response: {debug_response}")
        return debug_response
        
    except Exception as e:
        logging.error(f"Debug dialogue endpoint error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Debug endpoint error: {e}")

@router.get("/test-ai-client")
async def test_ai_client_endpoint(
    client = Depends(get_ai_client),
    deployment: str = Depends(get_general_model_deployment)
):
    """
    Test endpoint to check if AI client and deployment are properly configured
    """
    try:
        logging.info(f"=== AI CLIENT TEST ===")
        logging.info(f"Client type: {type(client)}")
        logging.info(f"Deployment: {deployment}")
        
        # Test a simple completion
        import asyncio
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=deployment,
            messages=[{"role": "user", "content": "Hello, this is a test"}],
            max_tokens=10,
            temperature=0.1
        )
        
        test_response = {
            "status": "success",
            "client_type": str(type(client)),
            "deployment": deployment,
            "ai_response": response.choices[0].message.content,
            "message": "AI client is working properly"
        }
        
        logging.info(f"AI client test successful: {test_response}")
        return test_response
        
    except Exception as e:
        logging.error(f"AI client test failed: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "client_type": str(type(client)) if client else "None",
            "deployment": deployment,
            "error": str(e),
            "message": "AI client test failed"
        }

@router.get("/test-dialogue-agent")
async def test_dialogue_agent_endpoint(
    client = Depends(get_ai_client),
    deployment: str = Depends(get_general_model_deployment)
):
    """
    Test endpoint to check if DialoguePlannerAgent can be initialized properly
    """
    try:
        logging.info(f"=== DIALOGUE AGENT TEST ===")
        logging.info(f"Attempting to initialize DialoguePlannerAgent...")
        
        # Try to initialize the DialoguePlannerAgent
        dialogue_planner = DialoguePlannerAgent(client=client, deployment=deployment)
        
        test_response = {
            "status": "success",
            "message": "DialoguePlannerAgent initialized successfully",
            "client_type": str(type(client)),
            "deployment": deployment,
            "agent_type": str(type(dialogue_planner))
        }
        
        logging.info(f"DialoguePlannerAgent test successful: {test_response}")
        return test_response
        
    except Exception as e:
        logging.error(f"DialoguePlannerAgent test failed: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "error_type": str(type(e)),
            "message": "DialoguePlannerAgent initialization failed"
        }

@router.post("/test-process-input")
async def test_process_input_endpoint(
    client = Depends(get_ai_client),
    deployment: str = Depends(get_general_model_deployment)
):
    """
    Test endpoint to check if DialoguePlannerAgent.process_user_input works with a simple test case
    """
    try:
        logging.info(f"=== PROCESS INPUT TEST ===")
        
        # Initialize the DialoguePlannerAgent
        dialogue_planner = DialoguePlannerAgent(client=client, deployment=deployment)
        
        # Test with a simple input
        test_context = {
            "current_plan": None,
            "chat_history": []
        }
        
        logging.info("Calling process_user_input with test data...")
        response = await dialogue_planner.process_user_input(
            user_input="Hello, this is a test",
            context=test_context
        )
        
        test_response = {
            "status": "success",
            "message": "process_user_input completed successfully",
            "response_keys": list(response.keys()) if isinstance(response, dict) else "Not a dict",
            "ai_reply_length": len(response.get("ai_reply", "")) if isinstance(response, dict) else 0
        }
        
        logging.info(f"Process input test successful: {test_response}")
        return test_response
        
    except Exception as e:
        logging.error(f"Process input test failed: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "error_type": str(type(e)),
            "message": "process_user_input test failed"
        }

# Make sure this router is included in your main FastAPI app (e.g., in app/main.py)
# Example:
# from app.api.endpoints import ai as ai_router
# app.include_router(ai_router.router, prefix="/api/ai", tags=["AI Generation"])