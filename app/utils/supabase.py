import os
import logging
from typing import Optional, Dict, Any
import json
import httpx
import time
import asyncio
from httpx import HTTPStatusError, RequestError, TimeoutException

# Configure logging
logger = logging.getLogger(__name__)

class SupabaseClient:
    """
    A simple client for interacting with Supabase API.
    
    This class provides a way to interact with the Supabase APIs directly,
    which can be useful for verifying tokens or getting user information.
    """
    
    def __init__(self):
        """Initialize the Supabase client with API credentials from environment variables"""
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            logger.warning(
                "Supabase credentials not found in environment variables. "
                "Set SUPABASE_URL and SUPABASE_KEY to use Supabase features."
            )
        else:
            logger.info(f"Supabase client initialized with URL: {self.supabase_url[:20]}...")
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify a JWT token with Supabase and return the associated user.
        
        Args:
            token: The JWT token to verify
            
        Returns:
            Optional[Dict[str, Any]]: The user data if the token is valid, None otherwise
        """
        if not self.supabase_url or not self.supabase_key:
            logger.error("Cannot verify token: Supabase credentials not configured")
            return None
        
        # Log a masked token for debugging
        token_preview = token[:10] + "..." if len(token) > 10 else "invalid_token"
        logger.info(f"Attempting to verify token {token_preview} with Supabase")
        
        # First attempt - most tokens should succeed on first try
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "apikey": self.supabase_key,
                    "Content-Type": "application/json"
                }
                logger.info(f"Sending request to {self.supabase_url}/auth/v1/user")
                
                response = await client.get(
                    f"{self.supabase_url}/auth/v1/user",
                    headers=headers
                )
                
                logger.info(f"Received response: Status {response.status_code}")
                
                if response.status_code == 200:
                    user_data = response.json()
                    logger.info(f"Token verified successfully for user {user_data.get('id', 'unknown')}")
                    if 'email' in user_data:
                        email = user_data['email']
                        logger.info(f"User email: {email}")
                    return user_data
                elif response.status_code == 401:
                    logger.warning(f"Token is invalid or expired: {response.text}")
                    return None
                else:
                    # For other errors, try a few more times
                    logger.warning(f"Token verification failed with status {response.status_code}, will retry")
                    
        except (HTTPStatusError, TimeoutException, RequestError) as e:
            logger.warning(f"Network error on first attempt: {str(e)}, will retry")
        except Exception as e:
            logger.error(f"Unexpected error verifying token: {str(e)}")
            return None
        
        # Retry mechanism only for network errors or server errors (not auth errors)
        max_retries = 2  # Reduced from 3 to 2 additional attempts
        retry_delay = 0.5
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Retry attempt {attempt}/{max_retries}")
                async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "apikey": self.supabase_key,
                        "Content-Type": "application/json"
                    }
                    
                    response = await client.get(
                        f"{self.supabase_url}/auth/v1/user",
                        headers=headers
                    )
                    
                    logger.info(f"Retry response: Status {response.status_code}")
                    
                    if response.status_code == 200:
                        user_data = response.json()
                        logger.info(f"Token verified successfully on retry for user {user_data.get('id', 'unknown')}")
                        if 'email' in user_data:
                            email = user_data['email']
                            logger.info(f"User email: {email}")
                        return user_data
                    elif response.status_code == 401:
                        logger.warning(f"Token is invalid or expired on retry: {response.text}")
                        return None
                    else:
                        logger.warning(f"Retry failed: {response.status_code} {response.text}")
                        if attempt < max_retries:
                            wait_time = retry_delay * (2 ** attempt)
                            logger.info(f"Waiting {wait_time}s before next retry...")
                            await asyncio.sleep(wait_time)
                            
            except (HTTPStatusError, TimeoutException, RequestError) as e:
                logger.error(f"Network error on retry {attempt}: {str(e)}")
                if attempt < max_retries:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.info(f"Waiting {wait_time}s before next retry...")
                    await asyncio.sleep(wait_time)
            except Exception as e:
                logger.error(f"Unexpected error on retry {attempt}: {str(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                return None
        
        logger.error(f"Token verification failed after all retries")
        return None
    
    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a user's information from Supabase Auth.
        
        Args:
            user_id: The Supabase user ID
            
        Returns:
            Optional[Dict[str, Any]]: The user data if found, None otherwise
        """
        if not self.supabase_url or not self.supabase_key:
            logger.error("Cannot get user: Supabase credentials not configured")
            return None
        
        try:
            # Call the Supabase Auth Admin API to get user data
            # Note: This requires the service_role key, not the anon key
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.supabase_url}/auth/v1/admin/users/{user_id}",
                    headers={
                        "Authorization": f"Bearer {self.supabase_key}",
                        "apikey": self.supabase_key
                    }
                )
                
                if response.status_code == 200:
                    user_data = response.json()
                    return user_data
                else:
                    logger.warning(f"Failed to get user {user_id}: {response.status_code} {response.text}")
                    return None
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {str(e)}")
            return None

# Create a singleton instance
supabase_client = SupabaseClient() 