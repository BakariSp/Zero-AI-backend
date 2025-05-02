# app/recommendation/crud.py
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models import LearningPath, Course, Card, User, InterestLearningPathRecommendation
import random
from sqlalchemy import func

def get_recommended_learning_paths(
    db: Session, 
    user_id: Optional[int] = None,
    limit: int = 3
) -> List[LearningPath]:
    """Get recommended learning paths, potentially personalized for a user"""
    # Basic implementation - just get the most recent
    query = db.query(LearningPath).order_by(LearningPath.created_at.desc())
    
    # Here you could add personalization logic based on user_id
    # if user_id:
    #     user = db.query(User).filter(User.id == user_id).first()
    #     if user and user.interests:
    #         # Filter or order by user interests
    
    return query.limit(limit).all()

def get_recommended_courses(
    db: Session, 
    user_id: Optional[int] = None,
    limit: int = 3
) -> List[Course]:
    """Get recommended courses, potentially personalized for a user"""
    query = db.query(Course).order_by(Course.created_at.desc())
    return query.limit(limit).all()

def get_recommended_cards(
    db: Session, 
    user_id: Optional[int] = None,
    limit: int = 10
) -> List[Card]:
    """Get recommended cards, potentially personalized for a user"""
    # Based on your actual Card model fields from app/cards/schemas.py
    # Your Card model has 'keyword' and 'explanation' fields instead of 'title' and 'content'
    query = db.query(Card).order_by(Card.created_at.desc())
    return query.limit(limit).all()

def get_interest_learning_paths(
    db: Session, 
    interests: List[str],
    limit: int = 3,
    seed: Optional[float] = None,
    exclude_ids: Optional[List[int]] = None
) -> List[dict]:
    """
    Get recommended learning paths based on user interests with randomized results
    
    Parameters:
    - db: Database session
    - interests: List of interest IDs to find recommendations for
    - limit: Maximum number of paths to return
    - seed: Optional random seed for reproducible randomness
    - exclude_ids: Optional list of learning path IDs to exclude
    
    Returns:
    - List of dictionaries containing simplified learning path data and recommendation metadata
    """
    if seed is not None:
        # Set random seed for reproducible randomness if provided
        random.seed(seed)
    
    # Join InterestLearningPathRecommendation with LearningPath to get all data in one query
    query = db.query(
        InterestLearningPathRecommendation, 
        LearningPath
    ).join(
        LearningPath, 
        InterestLearningPathRecommendation.learning_path_id == LearningPath.id
    ).filter(
        InterestLearningPathRecommendation.interest_id.in_(interests)
    )
    
    # Exclude specific learning path IDs if provided
    if exclude_ids:
        query = query.filter(
            ~InterestLearningPathRecommendation.learning_path_id.in_(exclude_ids)
        )
    
    # Get all matching recommendations
    recommendation_data = query.all()
    
    if not recommendation_data:
        return []
    
    # Convert query results to list of dictionaries
    recommendations = [
        {
            "recommendation": {
                "interest_id": rec.interest_id,
                "score": rec.score,
                "priority": rec.priority,
                "tags": rec.tags
            },
            "learning_path": path
        }
        for rec, path in recommendation_data
    ]
    
    # Shuffle recommendations to get different results on each call
    random.shuffle(recommendations)
    
    # Get unique learning paths up to the limit
    seen_path_ids = set()
    results = []
    
    for item in recommendations:
        if len(results) >= limit:
            break
            
        path = item["learning_path"]
        if path.id not in seen_path_ids:
            results.append(item)
            seen_path_ids.add(path.id)
    
    return results

def get_random_learning_paths(
    db: Session,
    limit: int = 3,
    exclude_ids: Optional[List[int]] = None
) -> List[dict]:
    """
    Get random learning paths as a fallback when interest-based recommendations fail
    
    Parameters:
    - db: Database session
    - limit: Maximum number of paths to return
    - exclude_ids: Optional list of learning path IDs to exclude
    
    Returns:
    - List of dictionaries with learning path data and dummy recommendation metadata
    """
    # Query learning paths that are in the recommendation table
    # Instead of querying all learning paths, we only query those that are in the recommendations
    query = db.query(
        InterestLearningPathRecommendation, 
        LearningPath
    ).join(
        LearningPath, 
        InterestLearningPathRecommendation.learning_path_id == LearningPath.id
    )
    
    # Exclude specific learning path IDs if provided
    if exclude_ids:
        query = query.filter(~LearningPath.id.in_(exclude_ids))
    
    # Get all recommended learning paths
    recommendation_data = query.all()
    
    if not recommendation_data:
        # If no recommended paths (unlikely), fall back to original behavior
        query = db.query(LearningPath)
        if exclude_ids:
            query = query.filter(~LearningPath.id.in_(exclude_ids))
        learning_paths = query.all()
        
        # Shuffle the paths to get a random selection
        random.shuffle(learning_paths)
        
        # Create results in the same format as get_interest_learning_paths
        results = []
        for path in learning_paths[:limit]:
            results.append({
                "learning_path": path,
                "recommendation": {
                    "interest_id": "random",
                    "score": 0.5,  # Neutral score
                    "priority": 10,  # Low priority
                    "tags": ["random"]
                }
            })
        
        return results
    
    # Convert query results to list of dictionaries with recommendation data
    recommendations = [
        {
            "recommendation": {
                "interest_id": "random",  # Mark as random selection but from recommendation pool
                "score": 0.5,  # Neutral score
                "priority": 10,  # Low priority
                "tags": rec.tags if rec.tags else ["recommended_random"]
            },
            "learning_path": path
        }
        for rec, path in recommendation_data
    ]
    
    # Shuffle recommendations to get a random selection
    random.shuffle(recommendations)
    
    # Get unique learning paths up to the limit
    seen_path_ids = set()
    results = []
    
    for item in recommendations:
        if len(results) >= limit:
            break
            
        path = item["learning_path"]
        if path.id not in seen_path_ids:
            results.append(item)
            seen_path_ids.add(path.id)
    
    return results