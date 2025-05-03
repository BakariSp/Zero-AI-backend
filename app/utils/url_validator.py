import logging
import re
import requests
from typing import Dict, List, Optional, Tuple
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

# Load environment variables
load_dotenv()

# Google Search API settings
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CX = os.getenv("GOOGLE_SEARCH_CX")  # Custom Search Engine ID
GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

logger = logging.getLogger(__name__)

def is_valid_url(url: str) -> bool:
    """
    Validate if a URL is properly formatted and accessible.
    
    Args:
        url: The URL to validate
        
    Returns:
        bool: True if URL is valid and accessible, False otherwise
    """
    # First, check if URL has a valid format
    try:
        result = urlparse(url)
        # Check basic format requirements
        if not all([result.scheme, result.netloc]):
            logger.debug(f"URL {url} failed basic format validation")
            return False
            
        # Check if URL uses http or https protocol
        if result.scheme not in ['http', 'https']:
            logger.debug(f"URL {url} uses invalid protocol: {result.scheme}")
            return False
    except Exception as e:
        logger.error(f"Error parsing URL {url}: {str(e)}")
        return False
    
    # Try requesting the URL to check if it's accessible
    try:
        # Set a short timeout to avoid hanging
        response = requests.head(url, timeout=5, allow_redirects=True)
        # Consider any 2xx or 3xx status code as valid
        return response.status_code < 400
    except requests.RequestException as e:
        logger.debug(f"URL {url} is not accessible: {str(e)}")
        return False

def search_google(query: str, num_results: int = 3) -> List[Dict[str, str]]:
    """
    Search Google for relevant resources based on a query.
    
    Args:
        query: The search query
        num_results: Number of results to return (default: 3)
        
    Returns:
        List[Dict[str, str]]: List of resources with url and title
    """
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        logger.warning("Google Search API key or CX not configured. Using fallback.")
        return []
        
    try:
        params = {
            'key': GOOGLE_API_KEY,
            'cx': GOOGLE_CX,
            'q': query,
            'num': num_results
        }
        
        response = requests.get(GOOGLE_SEARCH_URL, params=params)
        
        if response.status_code != 200:
            logger.error(f"Google Search API returned error: {response.status_code} - {response.text}")
            return []
            
        results = response.json().get('items', [])
        
        # Format the results
        resources = []
        for item in results:
            resources.append({
                'url': item.get('link'),
                'title': item.get('title')
            })
            
        return resources
    except Exception as e:
        logger.error(f"Error while searching Google: {str(e)}")
        return []

def get_valid_resources(keyword: str, context: Optional[str] = None, 
                        existing_resources: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, str]]:
    """
    Get valid resources for a card by filtering existing resources and/or fetching new ones.
    
    Args:
        keyword: The main keyword/topic
        context: Additional context to refine the search
        existing_resources: List of existing resources to validate
        
    Returns:
        List[Dict[str, str]]: List of valid resources with url and title
    """
    valid_resources = []
    
    # First, validate any existing resources
    if existing_resources:
        for resource in existing_resources:
            url = resource.get('url')
            if url and is_valid_url(url):
                valid_resources.append(resource)
    
    # If we don't have enough valid resources, search for new ones
    if len(valid_resources) < 2:
        search_query = f"{keyword}"
        if context:
            search_query += f" {context}"
            
        # Get additional resources from Google
        google_resources = search_google(search_query, num_results=3)
        
        # Add only valid and non-duplicate resources
        existing_urls = [r.get('url') for r in valid_resources]
        for resource in google_resources:
            url = resource.get('url')
            if url and url not in existing_urls and is_valid_url(url):
                valid_resources.append(resource)
                
    return valid_resources[:3]  # Limit to 3 resources 