#!/usr/bin/env python
import os
import sys
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the API base URL
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000/api')

# Get the test user token
token = os.getenv('TEST_USER_TOKEN')

# Ensure we have a token
if not token:
    print("Please set the TEST_USER_TOKEN environment variable with a valid JWT token")
    sys.exit(1)

# Setup headers
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

def get_learning_path_recommendations():
    """Get learning path recommendations to test adding to my paths"""
    url = f"{API_BASE_URL}/recommendations/interests"
    
    data = {
        "interests": ["tech_basics", "ai_data", "creative_worlds"],
        "limit": 3
    }
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error getting recommendations: {response.status_code} - {response.text}")
        return None

def add_learning_path_to_my_paths(path_id):
    """Add a learning path to my collection"""
    url = f"{API_BASE_URL}/learning-paths/{path_id}/add-to-my-paths"
    
    response = requests.post(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error adding learning path: {response.status_code} - {response.text}")
        return None

def get_my_learning_paths():
    """Get my learning paths to verify the addition"""
    url = f"{API_BASE_URL}/learning-paths/user"
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error getting my learning paths: {response.status_code} - {response.text}")
        return None

def main():
    # Get learning path recommendations
    print("Fetching learning path recommendations...")
    recommendations = get_learning_path_recommendations()
    
    if not recommendations or not recommendations.get("learning_paths"):
        print("No recommendations found")
        return
    
    # Get the first recommended learning path ID
    first_path = recommendations["learning_paths"][0]
    path_id = first_path["id"]
    path_title = first_path["title"]
    
    print(f"Selected learning path: {path_title} (ID: {path_id})")
    
    # Add the learning path to my collection
    print(f"Adding learning path {path_id} to my collection...")
    result = add_learning_path_to_my_paths(path_id)
    
    if not result:
        print("Failed to add learning path to collection")
        return
    
    print(f"Learning path added to collection: {result['learning_path']['title']} (ID: {result['learning_path_id']})")
    
    # Get my learning paths to verify
    print("Fetching my learning paths to verify...")
    my_paths = get_my_learning_paths()
    
    if not my_paths:
        print("Failed to get my learning paths")
        return
    
    # Check if our newly added path is in the list
    found = False
    for path in my_paths:
        if path["learning_path"]["title"] == path_title:
            found = True
            print(f"Found learning path in my collection: {path['learning_path']['title']} (ID: {path['learning_path_id']})")
            break
    
    if not found:
        print(f"Learning path {path_title} not found in my collection")

if __name__ == "__main__":
    main() 