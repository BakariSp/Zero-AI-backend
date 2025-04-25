import logging
from fastapi import APIRouter, Depends, Body, HTTPException
from openai import AzureOpenAI
from typing import Dict, Any

# Import your agent and dependency functions
from app.services.agents.dialogue_planner import DialoguePlannerAgent
from app.core.dependencies import get_azure_openai_client, get_azure_openai_deployment # Adjust import path as needed
from app.services.agents.dialogue_planner import DialogueInput # Import the input model

router = APIRouter()

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
    client: AzureOpenAI = Depends(get_azure_openai_client),
    deployment: str = Depends(get_azure_openai_deployment) # Or get specific deployment for dialogue
) -> Dict[str, Any]:
    """
    Handles conversational input for learning path generation and modification.
    """
    try:
        # Instantiate the DialoguePlannerAgent
        # Ensure the deployment name passed is suitable for the planner's tasks (intent recognition, reply generation)
        dialogue_planner = DialoguePlannerAgent(client=client, deployment=deployment)

        # Prepare the context for the agent
        context = {
            "current_plan": payload.current_plan,
            "chat_history": payload.chat_history
        }

        # Process the input using the agent
        response = await dialogue_planner.process_user_input(
            user_input=payload.user_input,
            context=context
        )

        # The agent should return a dictionary matching the desired output format
        return response

    except ValueError as ve:
        # Catch specific errors like JSON parsing issues from agents
        raise HTTPException(status_code=400, detail=f"Input or Agent Processing Error: {ve}")
    except RuntimeError as re:
        # Catch initialization errors or other runtime issues
        raise HTTPException(status_code=500, detail=f"Agent Initialization Error: {re}")
    except Exception as e:
        # General error handler
        # Log the error details here
        logging.error(f"Unexpected error in /dialogue endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")

# Make sure this router is included in your main FastAPI app (e.g., in app/main.py)
# Example:
# from app.api.endpoints import ai as ai_router
# app.include_router(ai_router.router, prefix="/api/ai", tags=["AI Generation"])