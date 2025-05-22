#!/usr/bin/env python
"""
Test script for Zhipu AI GLM-4 integration.
This script verifies that the Zhipu AI client is properly configured and can make API calls.
"""

import os
import sys
import logging
import traceback
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Check if Zhipu AI is enabled
use_zhipu = os.getenv("USE_ZHIPU_AI", "false").lower() == "true"
if not use_zhipu:
    logging.warning("Zhipu AI is not enabled. Set USE_ZHIPU_AI=true in .env file to enable it.")
    sys.exit(1)

# Check for API key
api_key = os.getenv("ZHIPU_AI_API_KEY")
if not api_key or api_key == "your_zhipu_api_key_here":
    logging.error("No valid Zhipu AI API key found. Please set ZHIPU_AI_API_KEY in .env file.")
    sys.exit(1)

# Validate API key format
if "." not in api_key or len(api_key.split(".")) != 2:
    logging.warning("API key doesn't appear to have the expected format (ID.SECRET). This might cause authentication issues.")

try:
    logging.info("Testing Zhipu AI client...")
    logging.info("Importing ZhipuAIClient...")
    from app.utils.zhipu_ai_client import ZhipuAIClient
    
    # Initialize client
    logging.info("Initializing ZhipuAIClient...")
    client = ZhipuAIClient()
    
    # Test API call
    model = os.getenv("ZHIPU_AI_MODEL", "glm-4")
    logging.info(f"Making test API call to Zhipu AI using model: {model}")
    
    try:
        # Check that the client has the expected structure
        if not hasattr(client, 'chat'):
            raise AttributeError("Client does not have 'chat' attribute")
        
        if not hasattr(client.chat, 'completions'):
            raise AttributeError("Client.chat does not have 'completions' attribute")
        
        if not hasattr(client.chat.completions, 'create'):
            raise AttributeError("Client.chat.completions does not have 'create' method")
        
        # Make the API call
        response = client.chat.completions.create(
            messages=[
                {"role": "user", "content": "Hello, please respond with a short greeting in English."}
            ],
            model=model,
            max_tokens=50
        )
        
        # Display response
        logging.info(f"Response received from Zhipu AI:")
        logging.info(f"Model: {response.model}")
        logging.info(f"Message: {response.choices[0].message.content}")
        
        logging.info("Zhipu AI test completed successfully!")
        
    except AttributeError as e:
        logging.error(f"Client structure error: {e}")
        logging.error("The client doesn't have the expected structure (client.chat.completions.create).")
        logging.info("Client structure:")
        if hasattr(client, 'chat'):
            logging.info("  - client.chat: ✓")
            if hasattr(client.chat, 'completions'):
                logging.info("  - client.chat.completions: ✓")
            else:
                logging.info("  - client.chat.completions: ✗")
        else:
            logging.info("  - client.chat: ✗")
        sys.exit(1)
    except Exception as e:
        logging.error(f"API call error: {e}")
        logging.error(traceback.format_exc())
        sys.exit(1)
    
except ImportError as e:
    logging.error(f"Failed to import Zhipu AI client: {e}")
    logging.error("Make sure app/utils/zhipu_ai_client.py exists and is properly implemented.")
    sys.exit(1)
except Exception as e:
    logging.error(f"Error testing Zhipu AI client: {e}")
    logging.error(traceback.format_exc())
    logging.error("Check your API key and network connection.")
    sys.exit(1) 