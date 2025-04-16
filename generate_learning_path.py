import requests
import json
import random
from typing import List, Dict, Any
from functools import lru_cache

# Base URL for your API
BASE_URL = "http://localhost:8000/api"  # Adjust if your server runs on a different port

# Authentication credentials
AUTH_EMAIL = "admin@example.com"
AUTH_PASSWORD = "admin123"

# Global variable to store the token
_ACCESS_TOKEN = None

@lru_cache(maxsize=1)
def get_access_token() -> str:
    """Login and return the access token (cached)"""
    global _ACCESS_TOKEN
    
    # If we already have a token, return it
    if _ACCESS_TOKEN:
        return _ACCESS_TOKEN
    
    login_data = {
        "username": AUTH_EMAIL,
        "password": AUTH_PASSWORD
    }
    
    # We know this endpoint works
    endpoint = f"{BASE_URL}/token"
    
    try:
        print(f"Authenticating at: {endpoint}")
        response = requests.post(endpoint, data=login_data)
        response.raise_for_status()
        
        # Store the token globally
        _ACCESS_TOKEN = response.json()["access_token"]
        print("Authentication successful")
        return _ACCESS_TOKEN
        
    except requests.exceptions.RequestException as e:
        print(f"Authentication failed: {e}")
        raise Exception(f"Failed to authenticate: {e}")

def get_auth_headers() -> Dict[str, str]:
    """Get the authorization headers with the access token"""
    token = get_access_token()
    return {"Authorization": f"Bearer {token}"}

# Learning path themes with engaging question-based titles
LEARNING_PATHS = [
    {
        "title": "How to Boost Your Brain Power?",
        "description": "Practical techniques and habits to enhance your cognitive abilities, memory, and problem-solving skills.",
        "category": "Personal Development",
        "difficulty_level": "beginner",
        "estimated_days": 21
    }
]

# Course themes for each learning path
COURSES_BY_PATH = [
    # Courses for "How to Boost Your Brain Power?"
    [
        {"title": "The Science of Memory", "description": "Understanding how memory works and techniques to improve retention."}
    ]
]

# Section themes for each course
SECTIONS_TEMPLATE = [
    {"title": "Practical Applications", "description": "Hands-on techniques to apply what you've learned."}
]

# Card keywords for each section (1 card per section)
CARD_KEYWORDS_BY_PATH = [
    # Keywords for "How to Boost Your Brain Power?" path
    [
        # Course 1: The Science of Memory
        [
            ["Memory Types"]  # Just one keyword for the one section
        ]
    ]
]

def create_learning_path(path_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a learning path and return the created object"""
    headers = get_auth_headers()
    response = requests.post(f"{BASE_URL}/learning-paths", json=path_data, headers=headers)
    response.raise_for_status()
    return response.json()

def create_course(course_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a course and return the created object"""
    headers = get_auth_headers()
    response = requests.post(f"{BASE_URL}/courses", json=course_data, headers=headers)
    response.raise_for_status()
    return response.json()

def create_section(section_data: Dict[str, Any], course_id: int = None) -> Dict[str, Any]:
    """Create a section and return the created object"""
    headers = get_auth_headers()
    
    try:
        if course_id:
            # Create a course section with the correct data structure
            # The API expects { "course_id": X, "section_data": { ... } }
            data = {
                "course_id": course_id,
                "order_index": section_data.get("order_index", 0),  # Add order_index at the top level
                "section_data": {
                    "title": section_data["title"],
                    "description": section_data.get("description", ""),
                    "order_index": section_data.get("order_index", 0),
                    "estimated_days": section_data.get("estimated_days", 1)
                }
            }
            print(f"Creating course section with data: {json.dumps(data, indent=2)}")
            response = requests.post(f"{BASE_URL}/course-sections", json=data, headers=headers)
            response.raise_for_status()
            return response.json()
        else:
            # Create a standalone section
            print(f"Creating standalone section with data: {json.dumps(section_data, indent=2)}")
            response = requests.post(f"{BASE_URL}/sections", json=section_data, headers=headers)
            response.raise_for_status()
            return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"Error creating section: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response content: {e.response.text}")
        raise

def create_card(card_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a card and return the created object"""
    headers = get_auth_headers()
    
    try:
        print(f"Creating card with data: {card_data}")
        print(f"Sending request to: {BASE_URL}/cards")
        print(f"Headers: {headers}")
        
        response = requests.post(f"{BASE_URL}/cards", json=card_data, headers=headers)
        
        print(f"Response status code: {response.status_code}")
        print(f"Response content: {response.text}")
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        # Try the generate-card endpoint as a fallback
        try:
            generate_data = {
                "keyword": card_data["keyword"],
                "context": card_data.get("explanation", "")
            }
            response = requests.post(f"{BASE_URL}/generate-card", json=generate_data, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"Generate card HTTP Error: {e}")
            raise

def add_course_to_learning_path(learning_path_id: int, course_id: int, order_index: int) -> None:
    """Add a course to a learning path"""
    headers = get_auth_headers()
    
    # The API expects query parameters, not JSON body
    response = requests.post(
        f"{BASE_URL}/learning-path-courses?learning_path_id={learning_path_id}&course_id={course_id}&order_index={order_index}", 
        headers=headers
    )
    response.raise_for_status()

def add_section_to_course(course_id: int, section_id: int, order_index: int) -> None:
    """Add a section to a course"""
    headers = get_auth_headers()
    
    # Try different endpoints that might handle adding sections to courses
    try:
        # Try the course/{id}/sections endpoint
        data = {
            "section_id": section_id,
            "order_index": order_index
        }
        response = requests.post(f"{BASE_URL}/courses/{course_id}/sections", json=data, headers=headers)
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        try:
            # Try the course-sections endpoint with query parameters
            response = requests.post(
                f"{BASE_URL}/course-sections?course_id={course_id}&section_id={section_id}&order_index={order_index}", 
                headers=headers
            )
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            # Try the users/me/courses/{id}/sections endpoint as a last resort
            data = {
                "section_id": section_id,
                "order_index": order_index
            }
            response = requests.post(f"{BASE_URL}/users/me/courses/{course_id}/sections", json=data, headers=headers)
            response.raise_for_status()

def add_card_to_section(section_id: int, card_id: int, order_index: int) -> None:
    """Add a card to a section"""
    headers = get_auth_headers()
    data = {
        "card_id": card_id,
        "order_index": order_index,
        "is_custom": False
    }
    
    # For user sections, we need to use the /users/me/sections/{section_id}/cards endpoint
    try:
        print(f"Adding card {card_id} to section {section_id} at position {order_index}")
        response = requests.post(
            f"{BASE_URL}/users/me/sections/{section_id}/cards", 
            json=data, 
            headers=headers
        )
        response.raise_for_status()
        print(f"Successfully added card to section")
    except requests.exceptions.HTTPError as e:
        print(f"Error adding card to section: {e}")
        print(f"Response content: {e.response.text if hasattr(e, 'response') else 'No response'}")
        raise

def generate_card_content(keyword: str) -> Dict[str, Any]:
    """Generate content for a card based on its keyword"""
    # This would ideally call your AI service, but for testing we'll use templates
    return {
        "keyword": keyword,
        "explanation": f"This card explains the concept of {keyword} and its importance in the learning journey.",
        "resources": [
            {"title": f"{keyword} Fundamentals", "url": f"https://example.com/{keyword.lower().replace(' ', '-')}"},
            {"title": f"Advanced {keyword}", "url": f"https://advanced-learning.com/{keyword.lower().replace(' ', '-')}"}
        ],
        "level": random.choice(["beginner", "intermediate", "advanced"]),
        "tags": [keyword.split()[0], "essential", random.choice(["practical", "theoretical", "foundational"])]
    }

def get_learning_paths() -> List[Dict[str, Any]]:
    """Get all existing learning paths"""
    headers = get_auth_headers()
    response = requests.get(f"{BASE_URL}/learning-paths", headers=headers)
    response.raise_for_status()
    return response.json()

def learning_path_exists(title: str) -> bool:
    """Check if a learning path with the given title already exists"""
    existing_paths = get_learning_paths()
    return any(path["title"].lower() == title.lower() for path in existing_paths)

def get_courses() -> List[Dict[str, Any]]:
    """Get all existing courses"""
    headers = get_auth_headers()
    response = requests.get(f"{BASE_URL}/courses", headers=headers)
    response.raise_for_status()
    return response.json()

def course_exists(title: str) -> bool:
    """Check if a course with the given title already exists"""
    existing_courses = get_courses()
    return any(course["title"].lower() == title.lower() for course in existing_courses)

def get_sections() -> List[Dict[str, Any]]:
    """Get all existing sections"""
    headers = get_auth_headers()
    try:
        response = requests.get(f"{BASE_URL}/sections", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"Warning: Could not get sections: {e}")
        # Return empty list if we can't get sections
        return []

def section_exists(title: str) -> bool:
    """Check if a section with the given title already exists"""
    existing_sections = get_sections()
    return any(section["title"].lower() == title.lower() for section in existing_sections)

def get_cards() -> List[Dict[str, Any]]:
    """Get all existing cards"""
    headers = get_auth_headers()
    
    # Try different possible endpoints for cards
    possible_endpoints = [
        f"{BASE_URL}/cards",           # If cards router is at /api/cards
        "http://localhost:8000/cards", # If cards router is at /cards (without /api prefix)
        f"{BASE_URL}/api/cards",       # If cards router is at /api/api/cards (double prefix)
        f"{BASE_URL}/v1/cards"         # If cards router is at /api/v1/cards
    ]
    
    for endpoint in possible_endpoints:
        try:
            print(f"Trying to get cards from: {endpoint}")
            response = requests.get(endpoint, headers=headers)
            response.raise_for_status()
            print(f"Successfully got cards from: {endpoint}")
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"Warning: Could not get cards from {endpoint}: {e}")
            continue
    
    # If all endpoints fail, return empty list
    print("All card endpoints failed, returning empty list")
    return []

def card_exists(keyword: str) -> bool:
    """Check if a card with the given keyword already exists"""
    try:
        existing_cards = get_cards()
        return any(card.get("keyword", "").lower() == keyword.lower() for card in existing_cards)
    except Exception as e:
        print(f"Warning: Error checking if card exists: {e}")
        # If we can't check, assume it doesn't exist
        return False

def get_learning_path_details(learning_path_id: int) -> Dict[str, Any]:
    """Get details of a specific learning path including its courses"""
    headers = get_auth_headers()
    response = requests.get(f"{BASE_URL}/learning-paths/{learning_path_id}", headers=headers)
    response.raise_for_status()
    return response.json()

def get_course_details(course_id: int) -> Dict[str, Any]:
    """Get details of a specific course including its sections"""
    headers = get_auth_headers()
    response = requests.get(f"{BASE_URL}/courses/{course_id}", headers=headers)
    response.raise_for_status()
    return response.json()

def get_section_details(section_id: int) -> Dict[str, Any]:
    """Get details of a specific section including its cards"""
    headers = get_auth_headers()
    response = requests.get(f"{BASE_URL}/sections/{section_id}", headers=headers)
    response.raise_for_status()
    return response.json()

def main():
    """Main function to generate all learning paths, courses, sections, and cards"""
    created_paths = []
    
    # Add some debug prints to understand the structure
    print(f"Length of CARD_KEYWORDS_BY_PATH: {len(CARD_KEYWORDS_BY_PATH)}")
    
    for i, path in enumerate(CARD_KEYWORDS_BY_PATH):
        if i < len(CARD_KEYWORDS_BY_PATH):
            for j, course in enumerate(path):
                if j < len(path):
                    for k, section in enumerate(course):
                        if k < len(course):
                            # Only proceed if all indices are valid
                            for l, keyword in enumerate(CARD_KEYWORDS_BY_PATH[i][j][k]):
                                # Original code continues here
                                pass
        else:
            print(f"  Warning: Trying to access course {j} but path only has {len(path)} courses")
    
    # Create learning paths
    for i, path_data in enumerate(LEARNING_PATHS):
        existing_path = None
        
        # Check if learning path with this title already exists
        existing_paths = get_learning_paths()
        for path in existing_paths:
            if path["title"].lower() == path_data['title'].lower():
                existing_path = path
                print(f"Learning path already exists: {path_data['title']} - checking its contents")
                break
                
        if existing_path:
            # Learning path exists, get its details
            path_details = get_learning_path_details(existing_path["id"])
            path = existing_path
        else:
            # Create new learning path
            print(f"Creating learning path: {path_data['title']}")
            path = create_learning_path(path_data)
            created_paths.append(path)
        
        # Get existing courses for this path
        existing_courses = path_details.get("courses", []) if existing_path else []
        existing_course_titles = [c["title"].lower() for c in existing_courses]
        
        # Create courses for this path
        for j, course_data in enumerate(COURSES_BY_PATH[i]):
            # Check if course already exists in this learning path
            if course_data['title'].lower() in existing_course_titles:
                print(f"  Course already exists in this path: {course_data['title']} - checking its contents")
                # Find the existing course
                existing_course = next(c for c in existing_courses if c["title"].lower() == course_data['title'].lower())
                course = existing_course
            else:
                # Check if course exists elsewhere
                if course_exists(course_data['title']):
                    print(f"  Course exists elsewhere: {course_data['title']} - skipping")
                    continue
                    
                print(f"  Creating course: {course_data['title']}")
                course_data["estimated_days"] = random.randint(5, 10)
                course = create_course(course_data)
                
                # Add course to learning path
                add_course_to_learning_path(path["id"], course["id"], j)
            
            # Get existing sections for this course
            course_details = get_course_details(course["id"])
            existing_sections = course_details.get("sections", [])
            existing_section_titles = [s["title"].lower() for s in existing_sections]
            
            # Create sections for this course
            for k, section_template in enumerate(SECTIONS_TEMPLATE):
                section_title = f"{section_template['title']} for {course_data['title']}"
                
                # Check if section already exists in this course
                if section_title.lower() in existing_section_titles:
                    print(f"    Section already exists in this course: {section_title} - checking its contents")
                    # Find the existing section
                    existing_section = next(s for s in existing_sections if s["title"].lower() == section_title.lower())
                    section = existing_section
                else:
                    # Check if section exists elsewhere
                    if section_exists(section_title):
                        print(f"    Section exists elsewhere: {section_title} - skipping")
                        continue
                        
                print(f"    Creating section: {section_title}")
                # Customize section title for the course
                section_data = {
                    "title": section_title,
                    "description": section_template['description'],
                    "order_index": k,
                    "estimated_days": random.randint(1, 3)
                }
                
                try:
                    # Create section directly with course association
                    section = create_section(section_data, course_id=course["id"])
                except requests.exceptions.HTTPError as e:
                    print(f"    Error creating section: {e}")
                    continue
                
                # Get existing cards for this section
                try:
                    section_details = get_section_details(section["id"])
                    existing_cards = section_details.get("cards", [])
                    existing_card_keywords = [c.get("keyword", "").lower() for c in existing_cards if "keyword" in c]
                except requests.exceptions.HTTPError as e:
                    print(f"    Warning: Could not get section details: {e}")
                    existing_cards = []
                    existing_card_keywords = []
                
                # Create cards for this section
                for l, keyword in enumerate(CARD_KEYWORDS_BY_PATH[i][j][k]):
                    # Check if card already exists in this section
                    if keyword.lower() in existing_card_keywords:
                        print(f"      Card already exists in this section: {keyword} - skipping")
                        continue
                    
                    # Check if card exists elsewhere
                    if card_exists(keyword):
                        print(f"      Card exists elsewhere: {keyword} - skipping")
                        continue
                        
                    print(f"      Creating card: {keyword}")
                    card_data = generate_card_content(keyword)
                    
                    try:
                        card = create_card(card_data)
                    except requests.exceptions.HTTPError as e:
                        print(f"      Error creating card: {e}")
                        continue
                    
                    # Add card to section
                    try:
                        add_card_to_section(section["id"], card["id"], l)
                    except requests.exceptions.HTTPError as e:
                        print(f"      Error adding card to section: {e}")
                        continue
    
    print("\nSuccessfully processed learning paths with courses, sections, and cards!")
    for path in created_paths:
        print(f"- {path['title']} (ID: {path['id']})")

if __name__ == "__main__":
    main()