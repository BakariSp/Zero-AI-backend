import logging
import json
import asyncio
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
            # Add timeout to prevent hanging requests
            response = await asyncio.wait_for(
                dialogue_planner.process_user_input(
                    user_input=payload.user_input,
                    context=context
                ),
                timeout=240.0  # Increase to 4 minutes to be longer than frontend timeout
            )
            logging.info("AI processing completed successfully")
        except asyncio.TimeoutError:
            logging.error("AI processing timed out after 240 seconds")
            raise HTTPException(status_code=504, detail="AI processing timed out after 4 minutes. Please try again with a simpler request.")
        except Exception as process_error:
            logging.error(f"Failed during process_user_input: {process_error}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"AI processing failed: {process_error}")
        
        # Add response construction logging as suggested by frontend team
        logging.info("Starting response construction...")
        logging.info(f"Response data type: {type(response)}")
        
        # Validate response is not None and is a dict
        if response is None:
            logging.error("Response from dialogue_planner.process_user_input is None")
            raise HTTPException(status_code=500, detail="AI processing returned None response")
        
        if not isinstance(response, dict):
            logging.error(f"Response is not a dict: {type(response)}")
            raise HTTPException(status_code=500, detail=f"AI processing returned invalid response type: {type(response)}")
        
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
            logging.error(f"Response missing required keys: {missing_keys}")
            logging.error(f"Available keys: {list(response.keys())}")
            raise ValueError(f"Response missing required keys: {missing_keys}")
        
        # Validate each required component
        if not isinstance(response.get('result'), dict):
            logging.error(f"Result is not a dict: {type(response.get('result'))}")
            raise ValueError(f"Result must be a dict, got {type(response.get('result'))}")
            
        if not isinstance(response.get('status'), dict):
            logging.error(f"Status is not a dict: {type(response.get('status'))}")
            raise ValueError(f"Status must be a dict, got {type(response.get('status'))}")
        
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
            logging.error("Response contains non-serializable objects")
            raise ValueError("Response contains non-serializable objects")
        
        # Test JSON serialization of original response
        try:
            json_string = json.dumps(response, ensure_ascii=False, default=str)
            logging.info(f"Original response JSON serialization successful, length: {len(json_string)} bytes")
            
            # Check if response is too large
            if len(json_string) > 1024 * 1024:  # 1MB
                logging.warning(f"Response size is very large: {len(json_string)} bytes")
                
        except Exception as json_error:
            logging.error(f"Original response JSON serialization failed: {json_error}")
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
                
            raise ValueError(f"Original response not JSON serializable: {json_error}")
        
        logging.info(f"Response construction successful. AI reply length: {len(response.get('ai_reply', ''))}")
        logging.info(f"Response status: {response.get('status', {})}")
        
        # Create a clean response structure to ensure no database objects are included
        logging.info("Creating clean response structure...")
        try:
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
            logging.info("Basic clean response structure created successfully")
        except Exception as e:
            logging.error(f"Failed to create basic clean response structure: {e}")
            raise ValueError(f"Failed to create clean response: {e}")
        
        # Safely copy result components with more defensive conversion
        result = response.get("result", {})
        
        try:
            # Handle learning_path
            if result.get("learning_path"):
                try:
                    lp = result["learning_path"]
                    if isinstance(lp, dict):
                        clean_response["result"]["learning_path"] = {
                            k: str(v) if v is not None else None 
                            for k, v in lp.items()
                        }
                    else:
                        clean_response["result"]["learning_path"] = None
                        logging.warning(f"learning_path is not a dict: {type(lp)}")
                except Exception as e:
                    logging.error(f"Error processing learning_path: {e}")
                    clean_response["result"]["learning_path"] = None
            else:
                clean_response["result"]["learning_path"] = None
                
            # Handle courses
            if result.get("courses"):
                try:
                    courses = result["courses"]
                    if isinstance(courses, list):
                        clean_courses = []
                        for course in courses:
                            if isinstance(course, dict):
                                clean_course = {}
                                for k, v in course.items():
                                    if k == "sections" and isinstance(v, list):
                                        # Handle nested sections
                                        clean_sections = []
                                        for section in v:
                                            if isinstance(section, dict):
                                                clean_section = {
                                                    sk: str(sv) if sv is not None and sk != "card_keywords" else sv
                                                    for sk, sv in section.items()
                                                }
                                                clean_sections.append(clean_section)
                                        clean_course[k] = clean_sections
                                    else:
                                        clean_course[k] = str(v) if v is not None else None
                                clean_courses.append(clean_course)
                        clean_response["result"]["courses"] = clean_courses
                    else:
                        clean_response["result"]["courses"] = None
                        logging.warning(f"courses is not a list: {type(courses)}")
                except Exception as e:
                    logging.error(f"Error processing courses: {e}")
                    clean_response["result"]["courses"] = None
            else:
                clean_response["result"]["courses"] = None
                
            # Handle sections (if separate from courses)
            if result.get("sections"):
                try:
                    sections = result["sections"]
                    if isinstance(sections, list):
                        clean_response["result"]["sections"] = [
                            {k: str(v) if v is not None else None for k, v in section.items()}
                            if isinstance(section, dict) else str(section)
                            for section in sections
                        ]
                    else:
                        clean_response["result"]["sections"] = None
                        logging.warning(f"sections is not a list: {type(sections)}")
                except Exception as e:
                    logging.error(f"Error processing sections: {e}")
                    clean_response["result"]["sections"] = None
            else:
                clean_response["result"]["sections"] = None
                
            # Handle cards
            if result.get("cards"):
                try:
                    cards = result["cards"]
                    if isinstance(cards, list):
                        clean_response["result"]["cards"] = [
                            {k: str(v) if v is not None else None for k, v in card.items()}
                            if isinstance(card, dict) else str(card)
                            for card in cards
                        ]
                    else:
                        clean_response["result"]["cards"] = None
                        logging.warning(f"cards is not a list: {type(cards)}")
                except Exception as e:
                    logging.error(f"Error processing cards: {e}")
                    clean_response["result"]["cards"] = None
            else:
                clean_response["result"]["cards"] = None
                
            logging.info("Clean response data conversion completed successfully")
            
        except Exception as conversion_error:
            logging.error(f"Critical error during clean response conversion: {conversion_error}", exc_info=True)
            # Create a minimal fallback response
            clean_response = {
                "ai_reply": "I processed your request, but encountered an issue formatting the response. Please try again.",
                "status": {
                    "has_learning_path": False,
                    "has_courses": False,
                    "has_sections": False,
                    "has_cards": False
                },
                "result": {
                    "learning_path": None,
                    "courses": None,
                    "sections": None,
                    "cards": None
                },
                "triggered_agent": "Error"
            }
            logging.info("Using fallback response due to conversion error")
        
        # Final serialization test of clean response
        try:
            json.dumps(clean_response, ensure_ascii=False, default=str)
            logging.info("Clean response JSON serialization successful")
        except Exception as e:
            logging.error(f"Clean response serialization failed: {e}")
            raise ValueError(f"Clean response not serializable: {e}")
        
        logging.info("=== ABOUT TO RETURN RESPONSE ===")
        logging.info(f"Response type: {type(clean_response)}")
        logging.info(f"Response keys: {list(clean_response.keys())}")
        logging.info("=== RETURNING CLEAN RESPONSE ===")
        
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

@router.post("/dialogue-simple")
async def simple_dialogue_endpoint(
    payload: DialogueInput = Body(...),
    client = Depends(get_ai_client),
    deployment: str = Depends(get_general_model_deployment)
) -> Dict[str, Any]:
    """
    Simplified version of the main dialogue endpoint that returns a minimal response
    to test if the issue is related to response size or complexity.
    """
    try:
        logging.info(f"Simple dialogue endpoint called with user_input: '{payload.user_input[:50]}...'")
        
        # Create a minimal response similar to the main endpoint structure
        simple_response = {
            "ai_reply": f"I received your message: '{payload.user_input}'. This is a simplified response.",
            "status": {
                "has_learning_path": False,
                "has_courses": False,
                "has_sections": False,
                "has_cards": False
            },
            "result": {
                "learning_path": None,
                "courses": None,
                "sections": None,
                "cards": None
            },
            "triggered_agent": "Simple"
        }
        
        logging.info("=== SIMPLE ENDPOINT ABOUT TO RETURN ===")
        logging.info(f"Simple response type: {type(simple_response)}")
        logging.info("=== RETURNING SIMPLE RESPONSE ===")
        
        return simple_response
        
    except Exception as e:
        logging.error(f"Simple dialogue endpoint error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Simple endpoint error: {e}")

@router.get("/health")
async def health_check():
    """
    Health check endpoint to verify the planner API is running and responsive.
    """
    try:
        return {
            "status": "healthy",
            "timestamp": str(datetime.now()),
            "service": "planner-api",
            "version": "1.0"
        }
    except Exception as e:
        logging.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")

# Make sure this router is included in your main FastAPI app (e.g., in app/main.py)
# Example:
# from app.api.endpoints import ai as ai_router
# app.include_router(ai_router.router, prefix="/api/ai", tags=["AI Generation"])