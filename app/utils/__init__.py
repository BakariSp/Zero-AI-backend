# Utils package

# Import the necessary modules and redefine the functions
import os
import logging
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the Zhipu AI client
try:
    from app.utils.zhipu_ai_client import ZhipuAIClient, get_zhipu_ai_client
except ImportError:
    logging.warning("ZhipuAIClient import failed. Make sure the module is available.")
    ZhipuAIClient = None
    get_zhipu_ai_client = None

def get_azure_openai_client():
    """
    Create and return an Azure OpenAI client using environment variables.
    """
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),  
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    return client

def get_ai_client():
    """
    Get the appropriate AI client based on environment configuration.
    Returns either a ZhipuAIClient or AzureOpenAI client.
    """
    use_zhipu = os.getenv("USE_ZHIPU_AI", "false").lower() == "true"
    
    if use_zhipu and ZhipuAIClient is not None and get_zhipu_ai_client is not None:
        try:
            logging.info("Initializing Zhipu AI GLM-4 client")
            return get_zhipu_ai_client()
        except Exception as e:
            logging.error(f"Error initializing Zhipu AI client: {e}")
            logging.warning("Falling back to Azure OpenAI client")
            return get_azure_openai_client()
    else:
        logging.info("Using Azure OpenAI client")
        return get_azure_openai_client()

def get_model_deployment(is_card_model=False):
    """
    Get the appropriate model deployment name based on environment configuration.
    
    Args:
        is_card_model: Whether to return the card-specific model deployment
        
    Returns:
        str: The model deployment name to use
    """
    use_zhipu = os.getenv("USE_ZHIPU_AI", "false").lower() == "true"
    
    if use_zhipu:
        if is_card_model:
            return os.getenv("ZHIPU_AI_CARD_MODEL", "glm-4")
        else:
            return os.getenv("ZHIPU_AI_MODEL", "glm-4")
    else:
        if is_card_model:
            return os.getenv("CARD_MODEL_AZURE_DEPLOYMENT_NAME", "gpt-4o-card")
        else:
            return os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
