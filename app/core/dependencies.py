import os
from functools import lru_cache
from openai import AzureOpenAI
from fastapi import HTTPException

# Example dependency setup - adapt to your configuration management
@lru_cache() # Cache the client instance
def get_azure_openai_client() -> AzureOpenAI:
    try:
        # Ensure these environment variables are set
        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        return client
    except Exception as e:
        # Log the error details
        print(f"ERROR: Failed to initialize Azure OpenAI client: {e}") # Use logging in production
        raise HTTPException(status_code=500, detail="Azure OpenAI client configuration error.")

def get_azure_openai_deployment() -> str:
    # Example: Using a general-purpose deployment name from env vars
    # You might want different deployments for different agents
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    if not deployment_name:
        raise HTTPException(status_code=500, detail="Azure OpenAI deployment name not configured.")
    return deployment_name

# You might create specific dependencies if the DialoguePlanner needs a different model/deployment
# def get_dialogue_planner_deployment() -> str:
#     # ... logic to get specific deployment ... 