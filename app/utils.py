import os
from openai import AzureOpenAI
from jose import JWTError, jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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

def generate_token(data: dict):
    """
    Generate a JWT token for authentication.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30)))
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode, 
        os.getenv("JWT_SECRET_KEY"), 
        algorithm=os.getenv("JWT_ALGORITHM", "HS256")
    )
    return encoded_jwt

def verify_token(token: str):
    """
    Verify a JWT token and return the username if valid.
    """
    try:
        payload = jwt.decode(
            token, 
            os.getenv("JWT_SECRET_KEY"), 
            algorithms=[os.getenv("JWT_ALGORITHM", "HS256")]
        )
        username = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None 