import os
import json
import logging
import requests
import hmac
import base64
import hashlib
import time
from typing import List, Dict, Any, Optional, Union
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ZhipuAIClient:
    """
    Client for interacting with Zhipu AI's GLM-4 API.
    Designed to have a similar interface to AzureOpenAI client for easier integration.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Zhipu AI client.
        
        Args:
            api_key: The API key for authenticating with Zhipu AI.
                    If not provided, it will be loaded from the environment variable ZHIPU_AI_API_KEY.
        """
        self.api_key = api_key or os.getenv("ZHIPU_AI_API_KEY")
        if not self.api_key:
            raise ValueError("No API key provided for Zhipu AI. Set ZHIPU_AI_API_KEY environment variable.")
        
        self.base_url = "https://open.bigmodel.cn/api/paas/v4"
        # Create a nested structure to match OpenAI's client
        self.chat = type('ChatObject', (), {
            "completions": self.ChatCompletions(self)
        })
        
    def _generate_jwt_token(self):
        """Generate JWT token for authentication"""
        import jwt
        
        api_key_parts = self.api_key.split(".")
        if len(api_key_parts) != 2:
            raise ValueError("Invalid Zhipu AI API key format")
            
        id, secret = api_key_parts
        
        # Create the JWT payload
        current_time = int(time.time())
        payload = {
            "api_key": id,
            "exp": current_time + 3600,  # Token expires in 1 hour
            "timestamp": current_time
        }
        
        # Create the JWT token
        token = jwt.encode(
            payload=payload,
            key=secret,
            algorithm="HS256",
            headers={"alg": "HS256", "sign_type": "SIGN"}
        )
        
        return token, id, secret
    
    def _generate_hmac_auth(self, path: str):
        """Generate HMAC authentication headers"""
        api_key_parts = self.api_key.split(".")
        if len(api_key_parts) != 2:
            raise ValueError("Invalid Zhipu AI API key format")
            
        id, secret = api_key_parts
        
        # Get current timestamp
        timestamp = int(time.time())
        
        # Create signature string
        signature_str = f"{path}\n{timestamp}"
        
        # Create HMAC signature
        signature = hmac.new(
            secret.encode('utf-8'),
            signature_str.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        
        # Encode signature to base64
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        # Return headers
        return {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {id}",
            "X-Timestamp": str(timestamp),
            "X-Signature": signature_b64
        }, id, secret
        
    class ChatCompletions:
        """
        Class to handle chat completions requests, mimicking OpenAI's structure.
        """
        
        def __init__(self, client):
            self.client = client
        
        def create(self, 
                   messages: List[Dict[str, str]], 
                   model: str = None, 
                   temperature: float = 0.7, 
                   max_tokens: int = 1000, 
                   stream: bool = False,
                   **kwargs) -> Any:
            """
            Create a chat completion request to Zhipu AI.
            
            Args:
                messages: List of message dictionaries with 'role' and 'content' keys.
                model: The model to use (defaults to GLM-4 if not specified).
                temperature: Sampling temperature between 0 and 1.
                max_tokens: Maximum number of tokens to generate.
                stream: Whether to stream the response.
                **kwargs: Additional parameters to pass to the API.
                
            Returns:
                A response object with a structure similar to OpenAI's response.
            """
            model = model or os.getenv("ZHIPU_AI_MODEL", "glm-4")
            
            # First try JWT token authentication
            try:
                token, id, secret = self.client._generate_jwt_token()
                
                # Debug token generation
                logging.info(f"Using JWT auth with API key ID: {id}")
                # Don't log the full secret, just the first few characters
                secret_preview = secret[:4] + "..." if len(secret) > 4 else "***"
                logging.info(f"Using secret: {secret_preview}")
                
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                }
                
                # Convert messages to Zhipu AI format if needed
                # GLM-4 uses the same format as OpenAI, so we can use messages directly
                
                data = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": stream
                }
                
                # Add any additional parameters
                for key, value in kwargs.items():
                    data[key] = value
                    
                path = "/chat/completions"
                url = f"{self.client.base_url}{path}"
                logging.info(f"Making request to Zhipu AI: {url}")
                logging.info(f"Request data: {data}")
                
                response = requests.post(url, headers=headers, json=data)
                logging.info(f"Response status code: {response.status_code}")
                
                # If we get a 401 error, try again with HMAC authentication
                if response.status_code == 401:
                    logging.warning("JWT authentication failed. Trying HMAC authentication...")
                    return self._try_hmac_auth(path, data, model)
                
                # Handle errors
                if response.status_code != 200:
                    self._handle_error_response(response)
                
                response.raise_for_status()
                return self._process_response(response, model)
                
            except Exception as e:
                logging.error(f"JWT authentication error: {e}")
                logging.info("Falling back to HMAC authentication...")
                
                # Try HMAC authentication as fallback
                path = "/chat/completions"
                
                data = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": stream
                }
                
                # Add any additional parameters
                for key, value in kwargs.items():
                    data[key] = value
                
                return self._try_hmac_auth(path, data, model)
        
        def _try_hmac_auth(self, path, data, model):
            """Try HMAC authentication method"""
            headers, id, secret = self.client._generate_hmac_auth(path)
            
            logging.info(f"Using HMAC auth with API key ID: {id}")
            secret_preview = secret[:4] + "..." if len(secret) > 4 else "***"
            logging.info(f"Using secret: {secret_preview}")
            
            url = f"{self.client.base_url}{path}"
            logging.info(f"Making HMAC auth request to: {url}")
            
            response = requests.post(url, headers=headers, json=data)
            logging.info(f"HMAC auth response status code: {response.status_code}")
            
            # Handle errors
            if response.status_code != 200:
                self._handle_error_response(response)
                
            response.raise_for_status()
            return self._process_response(response, model)
        
        def _handle_error_response(self, response):
            """Handle error responses from Zhipu AI"""
            error_text = response.text
            logging.error(f"Error response from Zhipu AI: {error_text}")
            
            # Try to parse the error message for a more helpful error
            try:
                error_json = response.json()
                if "error" in error_json:
                    error_data = error_json["error"]
                    error_code = error_data.get("code", "unknown")
                    error_message = error_data.get("message", "No message provided")
                    
                    if error_code == "401":
                        if "令牌已过期" in error_message or "token" in error_message.lower():
                            logging.error("Authentication error: JWT token validation failed")
                            logging.error("Please check your API key and make sure it's still valid")
                            logging.error("The token generation might be incorrect for the current Zhipu AI API version")
                    
                    raise requests.exceptions.HTTPError(
                        f"Zhipu AI API error {error_code}: {error_message}",
                        response=response
                    )
            except ValueError:
                # If we can't parse the JSON, just continue with the standard error
                pass
        
        def _process_response(self, response, model):
            """Process successful response from Zhipu AI"""
            # Process the response to match OpenAI's format
            response_data = response.json()
            logging.info(f"Response data: {response_data}")
            
            # Zhipu AI response structure is different from OpenAI
            # Validate response structure
            if "choices" not in response_data:
                logging.error(f"Unexpected response format from Zhipu AI: 'choices' not found in response")
                logging.error(f"Response: {response_data}")
                # Try to handle common response formats
                if "data" in response_data and "choices" in response_data["data"]:
                    response_data = response_data["data"]
                else:
                    raise ValueError(f"Unexpected response format from Zhipu AI: {response_data}")
            
            # Create a response object similar to OpenAI's
            class Choice:
                def __init__(self, message, finish_reason="stop", index=0):
                    # Ensure message has required structure
                    if not isinstance(message, dict):
                        logging.error(f"Invalid message format: {message}")
                        message = {"role": "assistant", "content": str(message)}
                    
                    if "role" not in message:
                        message["role"] = "assistant"
                        
                    if "content" not in message:
                        message["content"] = "No content provided"
                        
                    self.message = type('Message', (), {"role": message["role"], "content": message["content"]})
                    self.finish_reason = finish_reason
                    self.index = index
            
            class ChatCompletion:
                def __init__(self, id, model, choices, usage):
                    self.id = id
                    self.model = model
                    self.choices = []
                    
                    # Process choices - handle different response formats
                    if isinstance(choices, list):
                        for i, choice in enumerate(choices):
                            # Handle different choice formats
                            if isinstance(choice, dict) and "message" in choice:
                                self.choices.append(Choice(choice["message"], choice.get("finish_reason", "stop"), i))
                            elif isinstance(choice, dict) and "content" in choice:
                                # Handle format where choice directly contains content
                                self.choices.append(Choice(
                                    {"role": "assistant", "content": choice["content"]},
                                    choice.get("finish_reason", "stop"), 
                                    i
                                ))
                            else:
                                logging.warning(f"Unexpected choice format: {choice}")
                                # Create a fallback choice
                                self.choices.append(Choice(
                                    {"role": "assistant", "content": str(choice)},
                                    "stop", 
                                    i
                                ))
                    else:
                        logging.error(f"Expected choices to be a list, got: {type(choices)}")
                        # Add a dummy choice
                        self.choices.append(Choice(
                            {"role": "assistant", "content": "Error processing response"},
                            "stop",
                            0
                        ))
                            
                    # Make sure we have at least one choice
                    if not self.choices:
                        self.choices.append(Choice(
                            {"role": "assistant", "content": "No choices returned from API"},
                            "stop",
                            0
                        ))
                        
                    # Set usage information
                    if isinstance(usage, dict):
                        self.usage = type('Usage', (), usage)
                    else:
                        self.usage = type('Usage', (), {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0
                        })
            
            # Create the ChatCompletion object from Zhipu AI's response
            completion = ChatCompletion(
                id=response_data.get("id", "zhipu-completion"),
                model=response_data.get("model", model),
                choices=response_data.get("choices", []),
                usage=response_data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
            )
            
            # Log the processed result
            logging.info(f"Processed completion object: {completion}")
            if hasattr(completion, 'choices') and completion.choices:
                logging.info(f"First choice message: {completion.choices[0].message.content[:100]}...")
            
            return completion

def get_zhipu_ai_client() -> ZhipuAIClient:
    """
    Create and return a Zhipu AI client using environment variables.
    """
    try:
        client = ZhipuAIClient()
        return client
    except Exception as e:
        logging.error(f"Failed to initialize Zhipu AI client: {e}")
        raise 