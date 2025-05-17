from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Response
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional, Dict, Any
import logging
import hashlib
import json
from datetime import timedelta, datetime
from pydantic import BaseModel, ValidationError
import inspect
from sqlalchemy.sql import text
from sqlalchemy import func
from app.progress.utils import initialize_user_progress_records

from app.db import get_db
from app.auth.jwt import get_current_active_user, get_current_user
from app.models import User, LearningPath, UserLearningPath, CourseSection, UserCourse, UserSection, user_cards, Course, course_section_association, section_cards, Card, learning_path_courses, user_section_cards
from app.learning_paths.schemas import (
    LearningPathCreate,
    LearningPathResponse,
    LearningPathUpdate,
    UserLearningPathCreate,
    UserLearningPathResponse,
    UserLearningPathUpdate,
    GenerateLearningPathRequest,
    LearningPathBasicInfo,
    GenerateDetailsFromOutlineRequest,
    GenerateCourseTitleRequest,
    CourseSectionCreate,
    CourseSectionUpdate,
    CourseSectionResponse,
    UserCourseInfo,
    UserSectionInfo
)
from app.learning_paths.crud import (
    get_learning_path,
    get_learning_paths,
    create_learning_path,
    update_learning_path,
    delete_learning_path,
    get_user_learning_paths,
    get_user_learning_path,
    assign_learning_path_to_user,
    update_user_learning_path_progress,
    get_user_learning_path_by_ids,
    clone_learning_path_for_user
)
from app.services.ai_generator import generate_learning_path_with_ai
from app.services.learning_outline_service import LearningPathOutlineService
from app.services.ai_generator import LearningPathPlannerAgent
from app.services.learning_detail_service import LearningPathDetailService
from app.setup import increment_user_resource_usage, get_user_remaining_resources
from app.achievements.crud import check_completion_achievements
from app.sections.crud import find_user_section
from app.cards.crud import get_user_card_by_id as crud_get_user_card_by_id, save_card_for_user as crud_save_card_for_user, update_user_card as crud_update_user_card
from app.progress.utils import cascade_progress_update
from sqlalchemy import update
router = APIRouter()

# Pydantic models for the card completion endpoint (as per docs/progress_update.md)
class CardCompletionRequestBody(BaseModel):
    is_completed: bool

class UpdatedCardInfo(BaseModel):
    id: int
    is_completed: bool
    # Add other fields if needed from actual Card model if response requires more

class ProgressUpdateResponse(BaseModel):
    updated_card: UpdatedCardInfo
    updated_section_progress: float
    updated_course_progress: float
    updated_learning_path_progress: float

# Utility function to ensure a dictionary is fully serializable
def ensure_serializable(data, visited=None, field_name=None):
    """
    Recursively process a dictionary to ensure all values are serializable.
    Handles lists, dicts, and primitive types. Converts any SQLAlchemy models 
    or other complex objects to strings.
    """
    if isinstance(data, (str, int, float, bool, type(None))): # Handle primitives first
        return data

    if visited is None:
        visited = set()
    
    if id(data) in visited: 
        # Now, this block is less likely to affect already returned primitives
        if field_name and "estimated_days" in field_name: return None
        elif field_name and "progress" in field_name: return 0.0
        # Consider if this boolean override is still needed or how to make it safer
        elif field_name and any(x in field_name for x in ["is_", "has_", "completed"]):
            # This might still be problematic if a non-primitive object that was visited
            # happens to be passed again with one of these field names.
            # The original intent was likely for SQLAlchemy models that might be recursively referenced.
            return False 
        elif field_name and "_id" in field_name: return None
        return None # Default for other recursive references
    
    visited.add(id(data))
    
    if isinstance(data, dict):
        return {k: ensure_serializable(v, visited, k) for k, v in data.items()}
    elif isinstance(data, list):
        return [ensure_serializable(item, visited, field_name) for item in data]
    elif isinstance(data, (datetime)):
        return data.isoformat()
    else:
        # For complex types (like SQLAlchemy models), convert to string
        try:
            if hasattr(data, 'dict') and callable(data.dict):
                # Handle Pydantic models
                return ensure_serializable(data.dict(), visited, field_name)
            elif hasattr(data, 'model_dump') and callable(data.model_dump):
                # Newer Pydantic versions
                return ensure_serializable(data.model_dump(), visited, field_name)
            else:
                # For specific fields, provide appropriate defaults
                if field_name and "estimated_days" in field_name:
                    return None
                elif field_name and "progress" in field_name:
                    return 0.0
                # Return None for other complex objects
                return None
        except Exception:
            # Return None for exceptions
            return None


# Utility function to update is_completed and recalculate progress
@router.put("/users/me/learning-paths/{learning_path_id}/sections/{section_id}/cards/{card_id}", response_model=ProgressUpdateResponse)
def update_card_completion_in_learning_path_refactored(
    learning_path_id: int,
    section_id: int,
    card_id: int,
    body: CardCompletionRequestBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    is_completed = body.is_completed

    try:
        # 1. Find UserSection by template section id
        user_section = db.query(UserSection).filter(
            UserSection.user_id == current_user.id,
            UserSection.section_template_id == section_id
        ).first()

        if not user_section:
            logging.info(f"[MARK] ❌ UserSection not found for user {current_user.id}, template section {section_id}")
            raise HTTPException(status_code=404, detail="User section not found")

        # 2. Check if card is in the user_section
        card_entry = db.query(user_section_cards).filter(
            user_section_cards.c.user_section_id == user_section.id,
            user_section_cards.c.card_id == card_id
        ).first()

        if not card_entry:
            raise HTTPException(status_code=404, detail="Card not found in section")
    
        # 3. Update is_completed for that specific user_section_card
        db.execute(
        
            user_section_cards.update()
            .where(
                user_section_cards.c.user_section_id == user_section.id,
                user_section_cards.c.card_id == card_id
            )
            .values(is_completed=is_completed)
        )
        # 先查出原始 is_completed 状态
        original_entry = db.execute(
            user_cards.select().where(
                user_cards.c.user_id == current_user.id,
                user_cards.c.card_id == card_id
            )
        ).first()

        logging.info(f"[MARK] 🟡 Before update - user_id: {current_user.id}, card_id: {card_id}, is_completed: {original_entry.is_completed if original_entry else 'Not Found'}")

        # 执行更新
        db.execute(
            user_cards.update()
            .where(
                user_cards.c.user_id == current_user.id,
                user_cards.c.card_id == card_id
            )
            .values(is_completed=is_completed)
        )
        db.commit()

        # 再查出更新后的状态
        updated_entry = db.execute(
            user_cards.select().where(
                user_cards.c.user_id == current_user.id,
                user_cards.c.card_id == card_id
            )
        ).first()

        logging.info(f"[MARK] 🟢 After update - user_id: {current_user.id}, card_id: {card_id}, is_completed: {updated_entry.is_completed if updated_entry else 'Not Found'}")

        # 4. Recalculate section progress
        total_cards = db.query(user_section_cards).filter(
            user_section_cards.c.user_section_id == user_section.id
        ).count()

        completed_cards = db.query(user_section_cards).filter(
            user_section_cards.c.user_section_id == user_section.id,
            user_section_cards.c.is_completed == True
        ).count()

        section_progress = round((completed_cards / total_cards) * 100, 2) if total_cards > 0 else 0.0
        user_section.progress = section_progress
        db.commit()

        # 5. Get and update course progress
        course_progress = 0.0
        course_id = None
        if user_section.section_template_id:
            course_id_result = db.query(course_section_association.c.course_id).filter(
                course_section_association.c.section_id == user_section.section_template_id
            ).first()
            if course_id_result:
                course_id = course_id_result[0]

        if course_id:
            user_course = db.query(UserCourse).filter(
                UserCourse.user_id == current_user.id,
                UserCourse.course_id == course_id
            ).first()

            if user_course:
                # Get all sections under this course
                section_ids_in_course = db.query(course_section_association.c.section_id).filter(
                    course_section_association.c.course_id == course_id
                ).all()
                section_ids = [sid[0] for sid in section_ids_in_course]

                # Get all user sections for these section ids
                user_sections = db.query(UserSection).filter(
                    UserSection.user_id == current_user.id,
                    UserSection.section_template_id.in_(section_ids)
                ).all()

                total_progress = sum([s.progress for s in user_sections])
                course_progress = round(total_progress / len(user_sections), 2) if user_sections else 0.0

                user_course.progress = course_progress
                db.commit()

        # 6. Get and update learning path progress
        user_learning_path = db.query(UserLearningPath).filter(
            UserLearningPath.user_id == current_user.id,
            UserLearningPath.learning_path_id == learning_path_id
        ).first()

        lp_progress = 0.0
        if user_learning_path:
            # Get all courses in this LP
            lp_course_ids = db.query(learning_path_courses.c.course_id).filter(
                learning_path_courses.c.learning_path_id == learning_path_id
            ).all()
            course_ids = [cid[0] for cid in lp_course_ids]

            user_courses = db.query(UserCourse).filter(
                UserCourse.user_id == current_user.id,
                UserCourse.course_id.in_(course_ids)
            ).all()

            total_cp = sum([uc.progress for uc in user_courses])
            lp_progress = round(total_cp / len(user_courses), 2) if user_courses else 0.0

            user_learning_path.progress = lp_progress
            db.commit()

            # 7. Return response 前，插入 logging
            logging.info(
                f"[MARK] ✅ Update summary - user: {current_user.id}, LP: {learning_path_id}, "
                f"course: {course_id}, section: {user_section.id}, card: {card_id}, "
                f"is_completed: {is_completed}, section_progress: {section_progress}, "
                f"course_progress: {course_progress}, lp_progress: {lp_progress}"
            )


        # 7. Return response
        return ProgressUpdateResponse(
            updated_card=UpdatedCardInfo(
                id=card_id,
                is_completed=is_completed
            ),
            updated_section_progress=section_progress,
            updated_course_progress=course_progress,
            updated_learning_path_progress=lp_progress
        )


    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Error in refactored card completion endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update card completion status"
        )

@router.get("/learning-paths", response_model=List[LearningPathResponse])
def read_learning_paths(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all learning paths with optional category filter"""
    learning_paths = get_learning_paths(db, skip=skip, limit=limit, category=category)
    return learning_paths

@router.get("/learning-paths/basic", response_model=List[LearningPathBasicInfo])
def read_all_learning_paths_basic(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a basic list of all learning paths (id, name, description, state).
    Requires authentication.
    """
    learning_paths = get_learning_paths(db=db, limit=1000)
    return learning_paths

@router.get("/learning-paths/{path_id}", response_model=LearningPathResponse)
def read_learning_path(
    path_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific learning path by ID"""
    try:
        learning_path = get_learning_path(db, path_id=path_id)
        if learning_path is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learning path not found"
            )
        
        # Return the model, ensuring the courses data will use the CourseBaseResponse model
        return learning_path
    except Exception as e:
        logging.error(f"Error fetching learning path {path_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching learning path: {str(e)}"
        )

@router.post("/learning-paths", response_model=LearningPathResponse)
def create_new_learning_path(
    learning_path: LearningPathCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new learning path (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return create_learning_path(db=db, path_data=learning_path)

@router.put("/learning-paths/{path_id}", response_model=LearningPathResponse)
def update_existing_learning_path(
    path_id: int,
    learning_path: LearningPathUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an existing learning path (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return update_learning_path(
        db=db, 
        path_id=path_id, 
        path_data=learning_path.dict(exclude_unset=True)
    )

@router.delete("/learning-paths/{path_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_learning_path(
    path_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a learning path (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    delete_learning_path(db=db, path_id=path_id)
    return {"detail": "Learning path deleted successfully"}

@router.get("/users/me/learning-paths", response_model=List[UserLearningPathResponse])
def read_user_learning_paths(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all learning paths for the current user"""
    return get_user_learning_paths(db=db, user_id=current_user.id)

@router.get("/users/me/learning-paths/basic", response_model=List[LearningPathBasicInfo])
def read_my_learning_paths_basic(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a basic list (id, name, description, state) of learning paths
    assigned to the current user.
    """
    user_path_assignments = get_user_learning_paths(db=db, user_id=current_user.id)
    # Extract the LearningPath object from each assignment
    learning_paths = [assignment.learning_path for assignment in user_path_assignments]
    # Pydantic's response_model handles filtering the fields
    return learning_paths

@router.get("/users/me/learning-paths/{path_id}", response_model=UserLearningPathResponse)
def read_user_learning_path(
    path_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific learning path for the current user with progress information for all courses, sections, and cards.
    
    The response includes both user_section_id and section_template_id for each section:
    - section_template_id: This is the ID of the template section. Use this ID when making 
      API calls to update cards or sections. (RECOMMENDED for frontend implementation)
    - user_section_id: This is the ID of the user's personal copy of the section.
      This field is provided for reference, but the endpoints have been updated to work
      primarily with section_template_id.
    
    For consistency with the frontend implementation, use section_template_id (referred to as "id"
    or "section_id" in many contexts) for API calls.
    """

    # Generate cache key based on user ID, path ID and last updated timestamp
    try:
        # Check if path exists and get last update timestamp
        user_path = db.query(UserLearningPath).filter(
            UserLearningPath.user_id == current_user.id,
            UserLearningPath.learning_path_id == path_id
        ).first()
        
        if not user_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learning path not found for this user"
            )
        initialize_user_progress_records(
            user_id=current_user.id,
            learning_path_id=path_id,
            db=db
        )
        
        # Calculate cache key based on update timestamps
        cache_key = f"user_path:{current_user.id}:{path_id}:{user_path.updated_at}"
        
        # TODO: Check if data exists in cache and return it if valid
        # This would require a caching system like Redis or in-memory cache
        # cached_data = cache.get(cache_key)
        # if cached_data:
        #     return json.loads(cached_data)
        
        # If not in cache or cache expired, get the full data
        user_path = get_user_learning_path(db, user_id=current_user.id, path_id=path_id)
        
        # Initialize empty maps
        user_course_map = {}
        user_section_map = {}
        user_card_map = {}
        
        # Get course IDs and check if we have any
        course_ids = [course.id for course in user_path.learning_path.courses] if user_path.learning_path.courses else []
        
        # Use a single efficient query to get all user courses for this path - only if we have courses
        if course_ids:
            user_courses = db.query(UserCourse).filter(
                UserCourse.user_id == current_user.id,
                UserCourse.course_id.in_(course_ids)
            ).all()
            
            # Create a lookup dictionary for quick access
            user_course_map = {uc.course_id: uc for uc in user_courses}
        
        # Get all user sections for this user in a single query
        section_ids = []
        for course in user_path.learning_path.courses:
            for section in course.sections:
                section_ids.append(section.id)
        
        # Get user section map to find corresponding user sections for each template section
        user_section_template_map = {}
        if section_ids:
            all_user_sections = db.query(UserSection).filter(
                UserSection.user_id == current_user.id,
                UserSection.section_template_id.in_(section_ids)
            ).all()
            
            # Create a map of template_id -> user_section
            for user_section in all_user_sections:
                if user_section.section_template_id:
                    user_section_template_map[user_section.section_template_id] = user_section
                    
        # Only query if we have section IDs
        if section_ids:
            user_sections = db.query(UserSection).filter(
                UserSection.user_id == current_user.id,
                UserSection.section_template_id.in_(section_ids)
            ).all()
            
            # Create a lookup dictionary for quick access
            user_section_map = {us.section_template_id: us for us in user_sections}
        
        # Get all user card completion statuses in a single query
        card_ids = []
        for course in user_path.learning_path.courses:
            for section in course.sections:
                for card in section.cards:
                    card_ids.append(card.id)
        
        # Only query if we have card IDs to look up
        if card_ids:
            # Query the user_cards table directly using the SQLAlchemy Core Table
            user_card_records = db.query(
                user_cards.c.card_id,
                user_cards.c.is_completed
            ).filter(
                user_cards.c.user_id == current_user.id,
                user_cards.c.card_id.in_(card_ids)
            ).all()
            
            # Create a lookup dictionary for quick access
            user_card_map = {card_id: is_completed for card_id, is_completed in user_card_records}
        
        # Now build the response structure using the lookup dictionaries
        courses = []
        for course in user_path.learning_path.courses:
            # Get user course data
            user_course = user_course_map.get(course.id)
            progress = user_course.progress if user_course else 0.0
            completed_at = user_course.completed_at if user_course else None
            
            # Get sections with progress
            sections = []
            for section in course.sections:
                # Get user section data
                user_section = user_section_map.get(section.id)
                section_progress = user_section.progress if user_section else 0.0
                
                # Get the corresponding user section ID for this template section
                user_section_id = None
                if section.id in user_section_template_map:
                    user_section_id = user_section_template_map[section.id].id
                
                # Get cards with completion status
                cards = []
                for card in section.cards:
                    # Get user card data from the map
                    card_completed = user_card_map.get(card.id, False)
                    
                    # Add card with completion status - simplified to match CardProgressStatus
                    card_data_for_schema = {
                        "id": card.id,
                        "is_completed": card_completed,
                        "title": card.keyword
                    }
                    cards.append(card_data_for_schema)
                
                # Add section with cards and progress
                section_dict = {
                    "id": section.id,
                    "title": section.title,
                    "description": section.description,
                    "order_index": section.order_index,
                    "learning_path_id": section.learning_path_id,
                    "estimated_days": getattr(section, "estimated_days", None),
                    "created_at": section.created_at,
                    "updated_at": section.updated_at,
                    "progress": section_progress,
                    "cards": cards,
                    "user_section_id": user_section_id,  # Add the user-specific section ID
                    "section_template_id": section.id  # The original template section ID
                }
                sections.append(section_dict)
            
            # Add course with sections and progress
            course_info = {
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "progress": progress,
                "completed_at": completed_at,
                "sections": sections
            }
            courses.append(course_info)
        
        # Format each course as a UserCourseInfo object
        formatted_courses = []
        for course_info in courses:
            # Convert section dictionaries to UserSectionInfo objects
            formatted_sections = []
            for section_dict in course_info["sections"]:
                section_obj = UserSectionInfo(
                    id=section_dict["id"],
                    title=section_dict["title"],
                    description=section_dict["description"],
                    progress=section_dict["progress"],
                    cards=section_dict["cards"]
                )
                formatted_sections.append(section_obj)
                
            formatted_course = UserCourseInfo(
                id=course_info["id"],
                title=course_info["title"],
                description=course_info["description"],
                progress=course_info["progress"],
                completed_at=course_info["completed_at"],
                sections=formatted_sections
            )
            formatted_courses.append(formatted_course)
            
        # Format sections properly using the CourseSectionResponse model
        formatted_sections = []
        for section in user_path.learning_path.sections:
            formatted_section = CourseSectionResponse(
                id=section.id,
                learning_path_id=section.learning_path_id,
                title=section.title,
                description=section.description,
                order_index=section.order_index,
                estimated_days=section.estimated_days,
                created_at=section.created_at,
                updated_at=section.updated_at
            )
            formatted_sections.append(formatted_section)
        
        try:
            # Log the types of data being used for debugging
            logging.info(f"Courses type: {type(formatted_courses)}, count: {len(formatted_courses)}")
            if formatted_courses:
                logging.info(f"First course type: {type(formatted_courses[0])}")
                
            logging.info(f"Sections type: {type(formatted_sections)}, count: {len(formatted_sections)}")
            if formatted_sections:
                logging.info(f"First section type: {type(formatted_sections[0])}")
            
            # Use the formatted sections we already created
            # "sections": [section.model_dump() for section in formatted_sections],
            # The above line for top-level sections might need to be re-evaluated based on schema design.
            # If LearningPathResponse.sections refers to template sections without user progress, 
            # this should remain as is, or fetch CourseSectionResponse data.
            # For now, let's assume formatted_sections (template sections) is correct for lp_response_sections.
            lp_response_sections = []
            if hasattr(user_path.learning_path, 'sections'): # Check if the attribute exists
                for section in user_path.learning_path.sections:
                    lp_response_sections.append(CourseSectionResponse.model_validate(section).model_dump())

            learning_path_data_for_response = {
                "id": user_path.learning_path.id,
                "title": user_path.learning_path.title,
                "description": user_path.learning_path.description,
                "category": user_path.learning_path.category,
                "difficulty_level": user_path.learning_path.difficulty_level,
                "estimated_days": user_path.learning_path.estimated_days,
                "is_template": getattr(user_path.learning_path, "is_template", True),
                "created_at": user_path.learning_path.created_at,
                "updated_at": user_path.learning_path.updated_at,
                "sections": lp_response_sections, # For template sections directly under path
                "courses": [course.model_dump() for course in formatted_courses] # Uses UserCourseInfo with UserSectionInfo and CardProgressStatus
            }
            
            # Combine them into the structure expected by UserLearningPathResponse
            final_response_data = {
                "id": user_path.id,
                "user_id": user_path.user_id,
                "learning_path_id": user_path.learning_path_id,
                "progress": user_path.progress,
                "start_date": user_path.start_date,
                "completed_at": user_path.completed_at,
                "learning_path": learning_path_data_for_response
            }
            
            # Set cache control headers
            response.headers["Cache-Control"] = "max-age=60, private"
            
            # Directly return the dictionary; Pydantic will validate against UserLearningPathResponse
            return final_response_data
            
        except ValidationError as ve:
            # Log detailed Pydantic validation error info
            logging.error(f"Pydantic validation error: {ve}")
            
            # Extract detailed error information
            error_details = []
            for error in ve.errors():
                location = ".".join(str(loc) for loc in error["loc"])
                error_details.append(f"{location}: {error['msg']}")
            
            error_summary = "\n".join(error_details)
            logging.error(f"Validation errors:\n{error_summary}")
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Data validation error: {error_summary}"
            )
            
        except Exception as e:
            # Log the validation error details
            logging.error(f"Error creating response: {e}", exc_info=True)
            error_info = {
                "user_id": current_user.id,
                "path_id": path_id,
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
            logging.error(f"Error details: {error_info}")
            
            # Re-raise as HTTP exception with helpful message
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error serializing response data: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error retrieving user learning path: {e}", exc_info=True)
        # Add more detailed error context for debugging
        error_context = {
            "user_id": current_user.id,
            "path_id": path_id,
            "error_type": type(e).__name__,
            "error_message": str(e)
        }
        logging.error(f"Error context: {error_context}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the learning path"
        )

@router.get("/users/me/learning-paths/{path_id}/full", response_model=None)
def read_user_learning_path_full(
    path_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a complete learning path for the current user, including all courses, sections, and cards.
    
    The response includes both user_section_id and section_template_id for each section:
    - section_template_id: This is the ID of the template section. Use this ID when making 
      API calls to update cards or sections. (RECOMMENDED for frontend implementation)
    - user_section_id: This is the ID of the user's personal copy of the section.
      This field is provided for reference, but the endpoints have been updated to work
      primarily with section_template_id.
    
    For consistency with the frontend implementation, use section_template_id (referred to as "id"
    or "section_id" in many contexts) for API calls.
    """
    try:
        # First check if the user has this learning path assigned
        user_path = db.query(UserLearningPath).filter(
            UserLearningPath.user_id == current_user.id,
            UserLearningPath.learning_path_id == path_id
        ).first()
        
        if not user_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learning path not found for this user"
            )
        
        
        # Get the learning path with courses
        learning_path = db.query(LearningPath).options(
            selectinload(LearningPath.sections),
            selectinload(LearningPath.courses)
        ).filter(LearningPath.id == path_id).first()
        
        if not learning_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Learning path not found"
            )
            
        # Get all course IDs to fetch sections in batch
        course_ids = [course.id for course in learning_path.courses]
        section_map = {}
        card_map = {}
        
        # Get user section map to find corresponding user sections for each template section
        user_section_template_map = {}
        all_user_sections = db.query(UserSection).filter(
            UserSection.user_id == current_user.id,
            UserSection.section_template_id.in_([section.id for section in learning_path.sections])
        ).all()
        # Create a map of template_id -> user_section
        for user_section in all_user_sections:
            if user_section.section_template_id:
                user_section_template_map[user_section.section_template_id] = user_section
        
        # Fetch all sections for these courses
        if course_ids:
            # Get all section IDs from course-section associations
            section_assocs = db.query(course_section_association).filter(
                course_section_association.c.course_id.in_(course_ids)
            ).all()
            
            section_ids = [assoc.section_id for assoc in section_assocs]
            # Create a map of course_id -> list of section_ids
            course_to_sections = {}
            for assoc in section_assocs:
                if assoc.course_id not in course_to_sections:
                    course_to_sections[assoc.course_id] = []
                course_to_sections[assoc.course_id].append((assoc.section_id, assoc.order_index))
            
            # Fetch all the sections in one query
            if section_ids:
                sections = db.query(CourseSection).filter(
                    CourseSection.id.in_(section_ids)
                ).all()
                
                # Create a map of section_id -> section
                section_map = {section.id: section for section in sections}
                
                # Get all card IDs from section-card associations
                card_assocs = db.query(section_cards).filter(
                    section_cards.c.section_id.in_(section_ids)
                ).all()
                
                # Create a map of section_id -> list of card_ids
                section_to_cards = {}
                for assoc in card_assocs:
                    if assoc.section_id not in section_to_cards:
                        section_to_cards[assoc.section_id] = []
                    section_to_cards[assoc.section_id].append((assoc.card_id, assoc.order_index))
                
                # Fetch all cards in one query
                card_ids = [assoc.card_id for assoc in card_assocs]
                
                if card_ids:
                    cards = db.query(Card).filter(
                        Card.id.in_(card_ids)
                    ).all()
                    
                    # Create a map of card_id -> card
                    card_map = {card.id: card for card in cards}
        
        # Get all section IDs to track progress
        all_section_ids = []
        for course in learning_path.courses:
            if course.id in course_to_sections:
                for section_id, _ in course_to_sections[course.id]:
                    all_section_ids.append(section_id)
                    
        # Get all user sections for progress tracking in a single query
        user_sections = db.query(UserSection).filter(
            UserSection.user_id == current_user.id,
            UserSection.section_template_id.in_(all_section_ids)
        ).all()
        
        # Create a map of section_id -> user section (for progress info)
        user_section_map = {us.section_template_id: us for us in user_sections}
        
        # Get all card IDs for tracking completion
        all_card_ids = []
        for card_id in card_map.keys():
            all_card_ids.append(card_id)
            
        logging.info(f"Collected all_card_ids for path {path_id}: {all_card_ids}")
        logging.info(f"Is card 5724 in all_card_ids? {5724 in all_card_ids}")
        
        # Get completion status for all cards in a single query
        if all_card_ids:
            user_card_records = db.query(
                user_cards.c.card_id,
                user_cards.c.is_completed
            ).filter(
                user_cards.c.user_id == current_user.id,
                user_cards.c.card_id.in_(all_card_ids)
            ).all()
            
            # Create a lookup map for card completion status
            user_card_map = {card_id: is_completed for card_id, is_completed in user_card_records}
        
        # Create the LearningPathResponse structure with all nested content
        # First, build the CourseResponse objects with their sections
        courses_with_sections = []
        
        # Get user's course progress information
        user_courses = db.query(UserCourse).filter(
            UserCourse.user_id == current_user.id,
            UserCourse.course_id.in_([course.id for course in learning_path.courses])
        ).all()
        
        # Create a map of course_id -> user course (for progress info)
        user_course_map = {uc.course_id: uc for uc in user_courses}
        
        for course in learning_path.courses:
            # Initialize an empty list for this course's sections
            course_sections = []
            
            # Get progress info for this course (if available)
            user_course = user_course_map.get(course.id)
            progress = user_course.progress if user_course else 0.0
            completed_at = user_course.completed_at if user_course else None
            
            # Add sections to this course if we found any
            if course.id in course_to_sections:
                # Sort sections by order_index
                sorted_section_ids = sorted(course_to_sections[course.id], key=lambda x: x[1])
                
                for section_id, _ in sorted_section_ids:
                    if section_id in section_map:
                        section = section_map[section_id]
                        section_card_list = []
                        
                        # Get progress info for this section (if available)
                        user_section = user_section_map.get(section_id)
                        section_progress = user_section.progress if user_section else 0.0
                        
                        # Get the corresponding user section ID for this template section
                        user_section_id = None
                        if section_id in user_section_template_map:
                            user_section_id = user_section_template_map[section_id].id
                        
                        # Add cards to this section if we found any
                        if section_id in section_to_cards:
                            # Sort cards by order_index
                            sorted_card_ids = sorted(section_to_cards[section_id], key=lambda x: x[1])
                            
                            for card_id, _ in sorted_card_ids:
                                if card_id in card_map:
                                    card = card_map[card_id]
                                    # Create a detailed card dictionary with required fields
                                    if card.id == 5724:
                                        logging.info(f"Processing card ID 5724 in response construction. Status from map: {user_card_map.get(card.id, 'NOT_FOUND_DEFAULTING_FALSE')}")
                                    
                                    card_dict = {
                                        "id": card.id,
                                        "keyword": card.keyword,
                                        "question": card.question if hasattr(card, "question") else None,
                                        "answer": card.answer if hasattr(card, "answer") else None,
                                        "explanation": card.explanation if hasattr(card, "explanation") else None,
                                        "difficulty": card.difficulty if hasattr(card, "difficulty") else None,
                                        "resources": card.resources if hasattr(card, "resources") else [],
                                        "level": card.level if hasattr(card, "level") else None,
                                        "tags": card.tags if hasattr(card, "tags") else None,
                                        "created_at": card.created_at if hasattr(card, "created_at") else None,
                                        "updated_at": card.updated_at if hasattr(card, "updated_at") else None,
                                        "is_completed": user_card_map.get(card.id, False)
                                    }
                                    section_card_list.append(card_dict)
                        
                        # Manually create section with cards
                        section_dict = {
                            "id": section.id,
                            "title": section.title,
                            "description": section.description,
                            "order_index": section.order_index,
                            "learning_path_id": section.learning_path_id,
                            "estimated_days": getattr(section, "estimated_days", None),
                            "created_at": section.created_at,
                            "updated_at": section.updated_at,
                            "progress": section_progress,
                            "cards": section_card_list,
                            "user_section_id": user_section_id,  # Add the user-specific section ID
                            "section_template_id": section.id  # The original template section ID
                        }
                        course_sections.append(section_dict)
                        
            # Create a course response with sections
            course_dict = {
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "estimated_days": getattr(course, "estimated_days", None),  # Ensure it's an integer or None
                "is_template": getattr(course, "is_template", True),
                "created_at": course.created_at,
                "updated_at": course.updated_at,
                "progress": progress,
                "completed_at": completed_at,
                "sections": course_sections
            }
            courses_with_sections.append(course_dict)
        
        # Create the final response dictionary
        learning_path_dict = {
            "id": learning_path.id,
            "title": learning_path.title,
            "description": learning_path.description,
            "category": learning_path.category,
            "difficulty_level": learning_path.difficulty_level,
            "estimated_days": getattr(learning_path, "estimated_days", None),
            "is_template": getattr(learning_path, "is_template", False),
            "created_at": learning_path.created_at,
            "updated_at": learning_path.updated_at,
            # Convert sections to dicts to avoid SQLAlchemy lazy loading issues
            "sections": [{
                "id": section.id,
                "title": section.title,
                "description": section.description,
                "order_index": section.order_index,
                "learning_path_id": section.learning_path_id,
                "estimated_days": getattr(section, "estimated_days", None),
                "created_at": section.created_at,
                "updated_at": section.updated_at
            } for section in learning_path.sections],
            "courses": courses_with_sections
        }
        
        # Ensure the full structure is properly serialized
        clean_dict = ensure_serializable(learning_path_dict)
        
        # Set headers to indicate this is a raw dict response
        response.headers["X-Response-Type"] = "raw-dict"
        response.headers["Cache-Control"] = "max-age=60, private"
        
        # Return the dictionary directly instead of using Pydantic validation
        return clean_dict
    
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        logging.error(f"Error fetching full learning path {path_id} for user {current_user.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching full learning path: {str(e)}"
        )

@router.post("/users/me/learning-paths", response_model=UserLearningPathResponse)
def add_learning_path_to_user(
    user_path: UserLearningPathCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add an existing learning path to the current user"""
    # Check if learning path exists
    learning_path = get_learning_path(db, path_id=user_path.learning_path_id)
    if not learning_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning path not found"
        )
    
    # Assign the learning path to the user
    user_learning_path = assign_learning_path_to_user(
        db=db, 
        user_id=current_user.id, 
        learning_path_id=user_path.learning_path_id
    )
    
    # ✅ NEW: Initialize all user_* progress records in one shot
    try:
        initialize_user_progress_records(
            user_id=current_user.id,
            learning_path_id=user_path.learning_path_id,
            db=db
        )
        logging.info(f"[Init] Initialized progress records for LP {user_path.learning_path_id}, user {current_user.id}")
    except Exception as e:
        logging.error(f"[Init] Failed to initialize progress records: {e}")
        # 不 raise 异常，保持 assign 成功即可
    
    return user_learning_path

@router.put("/users/me/learning-paths/{path_id}", response_model=UserLearningPathResponse)
def update_user_learning_path(
    path_id: int,
    user_path_update: UserLearningPathUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update progress for a user's learning path"""
    user_path = get_user_learning_path(db, user_id=current_user.id, path_id=path_id)
    if not user_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning path not found for this user"
        )
    
    # Check if learning path is being completed
    path_completed = False
    
    # Update progress if provided
    if user_path_update.progress is not None:
        user_path = update_user_learning_path_progress(
            db=db,
            user_id=current_user.id,
            path_id=path_id,
            progress=user_path_update.progress
        )
        if user_path.progress >= 100.0:
            path_completed = True
    
    # Update completed_at if provided
    if user_path_update.completed_at is not None:
        user_path.completed_at = user_path_update.completed_at
        db.commit()
        db.refresh(user_path)
        path_completed = True
    
    # Check for achievements if learning path was completed
    if path_completed:
        check_completion_achievements(db, user_id=current_user.id)
    
    return user_path

@router.post("/generate-learning-path", response_model=LearningPathResponse)
async def generate_ai_learning_path(
    request: GenerateLearningPathRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate a learning path using AI based on user interests"""
    try:
        # Check user's daily usage limit for learning paths
        # Get current resources
        resources = get_user_remaining_resources(db, current_user.id)
        
        # Check if user has reached their daily limit
        if resources["paths"]["remaining"] <= 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Daily limit reached for learning paths. Your limit is {resources['paths']['limit']} paths per day."
            )
        
        # Generate learning path with AI
        learning_path_data = await generate_learning_path_with_ai(
            interests=request.interests,
            difficulty_level=request.difficulty_level,
            estimated_days=request.estimated_days
        )
        
        # Create the learning path in the database
        learning_path = create_learning_path(db=db, path_data=learning_path_data)
        
        # Assign the learning path to the user
        assign_learning_path_to_user(
            db=db,
            user_id=current_user.id,
            learning_path_id=learning_path.id
        )
        
        # ✅ 初始化 user 所有进度记录（课程、章节、卡片、连接器）
        try:
            initialize_user_progress_records(
                user_id=current_user.id,
                learning_path_id=learning_path.id,
                db=db
            )
            logging.info(f"[Init] Initialized all user progress records for LP {learning_path.id}, user {current_user.id}")
        except Exception as e:
            logging.error(f"[Init] Failed to initialize user progress records: {e}")
                
        # Increment user's daily usage for learning paths
        increment_user_resource_usage(db, current_user.id, "paths")
        
        return learning_path
    
    except Exception as e:
        logging.error(f"Error generating learning path: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate learning path: {str(e)}"
        )

@router.post("/generate-learning-courses")
async def generate_learning_courses(request: GenerateLearningPathRequest):
    try:
        outline_service = LearningPathOutlineService()
        detail_service = LearningPathDetailService()

        # 1. 生成 course outline（课程标题）
        all_titles = await outline_service.generate_outline(
            interests=request.interests,
            difficulty_level=request.difficulty_level,
            estimated_days=request.estimated_days
        )

        # 2. 去掉已有的，最多取 5 个
        new_titles = [title for title in all_titles if title not in request.existing_items][:5]

        # 3. 生成每个 title 对应的 detail（section），限制每个不超过 4 个
        detailed_results = await detail_service.generate_from_outline(
            titles=new_titles,
            difficulty_level=request.difficulty_level,
            estimated_days=request.estimated_days
        )

        # 4. 只保留每个 title 的前 4 个 sections（如果超出）
        structured = []
        for course in detailed_results.get("courses", []):
            structured.append({
                "title": course["title"],
                "sections": course.get("sections", [])[:4]
            })

        return {"courses": structured}

    except Exception as e:
        logging.error(f"Failed to generate courses with sections: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate courses with sections")

@router.post("/generate-course-titles")
async def generate_course_titles(request: GenerateCourseTitleRequest):
    try:
        service = LearningPathOutlineService()
        outline = await service.generate_outline(
            interests=request.interests,
            difficulty_level=request.difficulty_level,
            estimated_days=request.estimated_days
        )
        filtered = [item for item in outline if item not in request.existing_items]
        return {"titles": filtered[:5]}  # 最多返回5个
    except Exception as e:
        logging.error(f"Failed to generate course titles: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate course titles")

@router.post("/generate-sections")
async def generate_sections_from_titles(request: GenerateDetailsFromOutlineRequest):
    try:
        detail_service = LearningPathDetailService()
        detailed_results = await detail_service.generate_from_outline(
            titles=request.titles,
            difficulty_level=request.difficulty_level,
            estimated_days=request.estimated_days
        )

        # 最多保留每个 course 的前 4 个 section
        structured = []
        for course in detailed_results.get("courses", []):
            structured.append({
                "title": course["title"],
                "sections": course.get("sections", [])[:4]
            })

        return {"courses": structured}
    except Exception as e:
        logging.error(f"Failed to generate sections: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate sections")

@router.delete("/users/me/learning-paths/{path_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_learning_path(
    path_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a learning path assigned to the current user.
    This will also delete associated courses, sections, and cards
    if database cascading is configured.
    """
    # 1. Check if the user is actually assigned to this learning path
    user_path_assignment = get_user_learning_path_by_ids(
        db=db, user_id=current_user.id, learning_path_id=path_id
    )

    if not user_path_assignment:
        # If the user is not assigned, they cannot delete it.
        # Return 404 to avoid revealing if the path exists but belongs to someone else.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning path assignment not found for this user."
        )

    # 2. If assigned, proceed with deletion using the existing function
    #    (which relies on DB cascades or needs enhancement)
    try:
        deleted = delete_learning_path(db=db, path_id=path_id)
        if not deleted: # Should not happen if assignment check passed, but good practice
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learning path not found during deletion attempt."
            )
        # No explicit return body needed for 204 No Content
        return

    except HTTPException as e:
        # Re-raise specific HTTP exceptions (like 404 from delete_learning_path)
        raise e
    except Exception as e:
        # Catch potential errors during deletion
        logging.error(f"Error deleting learning path {path_id} for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the learning path."
        )

@router.post("/learning-paths/{path_id}/add-to-my-paths", response_model=UserLearningPathResponse)
def add_learning_path_to_user_collection(
    path_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add a learning path to the user's collection by creating a personal copy.
    
    This endpoint:
    1. Creates a clone of the learning path with all its courses and sections
    2. Associates the cloned path with the user
    3. Returns the new user-learning path association
    
    This allows users to have their own copy of learning paths they discover through recommendations.
    """
    try:
        # Clone the learning path for the user
        user_path = clone_learning_path_for_user(db, current_user.id, path_id)
        
        # Return the user learning path association
        return UserLearningPathResponse(
            id=user_path.id,
            user_id=user_path.user_id,
            learning_path_id=user_path.learning_path_id,
            progress=user_path.progress,
            start_date=user_path.start_date,
            completed_at=user_path.completed_at,
            created_at=user_path.created_at,
            updated_at=user_path.updated_at,
            learning_path=LearningPathResponse.model_validate(user_path.learning_path)
        )
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        # Log any other errors
        logging.error(f"Error adding learning path to user collection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add learning path to your collection: {str(e)}"
        )

@router.get("/users/me/section-ids", status_code=status.HTTP_200_OK)
def get_section_mapping(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a mapping of all user section IDs to template section IDs.
    This is a troubleshooting endpoint to help frontend developers determine
    which section ID to use in API calls.
    """
    try:
        # Get all user sections for this user
        all_user_sections = db.query(UserSection).filter(
            UserSection.user_id == current_user.id
        ).all()
        
        # Create mapping
        section_mapping = {}
        
        for section in all_user_sections:
            # Create a bidirectional mapping
            mapping_key = f"user_section_{section.id}"
            template_key = f"template_section_{section.section_template_id}" if section.section_template_id else "no_template"
            
            section_mapping[mapping_key] = {
                "id": section.id,
                "title": section.title,
                "template_section_id": section.section_template_id,
                "learning_path_ids": []  # Will be populated below if possible
            }
            
            # If there's a template section, map it back
            if section.section_template_id:
                if template_key not in section_mapping:
                    section_mapping[template_key] = {
                        "id": section.section_template_id,
                        "user_section_ids": [section.id]
                    }
                else:
                    section_mapping[template_key]["user_section_ids"].append(section.id)
        
        # Find which learning paths contain each section
        for section in all_user_sections:
            if not section.section_template_id:
                continue
                
            # Find learning paths containing this template section
            template_section = db.query(CourseSection).filter(
                CourseSection.id == section.section_template_id
            ).first()
            
            if not template_section:
                continue
                
            learning_path_id = template_section.learning_path_id
            if learning_path_id:
                mapping_key = f"user_section_{section.id}"
                section_mapping[mapping_key]["learning_path_ids"].append(learning_path_id)
        
        return {
            "user_id": current_user.id,
            "section_count": len(all_user_sections),
            "sections": section_mapping
        }
        
    except Exception as e:
        logging.error(f"Error getting section mapping: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting section mapping: {str(e)}"
        )

@router.get("/users/me/debug-section/{section_id}", status_code=status.HTTP_200_OK)
def debug_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Debug endpoint to get detailed information about a specific section.
    This helps diagnose section ID issues.
    """
    try:
        # Check for the section directly
        result = {
            "section_id": section_id,
            "user_id": current_user.id,
            "exists_in_db": {}
        }
        
        # Check if it exists as a user section
        user_section = find_user_section(db, user_id=current_user.id, section_id=section_id)
        if user_section:
            result["exists_in_db"]["as_user_section"] = True
            result["user_section"] = {
                "id": user_section.id,
                "title": user_section.title,
                "template_section_id": user_section.section_template_id,
                "description": user_section.description,
                "progress": user_section.progress
            }
        else:
            result["exists_in_db"]["as_user_section"] = False
        
        # Check if it exists as a template section
        template_section = db.query(CourseSection).filter(CourseSection.id == section_id).first()
        if template_section:
            result["exists_in_db"]["as_template_section"] = True
            result["template_section"] = {
                "id": template_section.id,
                "title": template_section.title,
                "description": template_section.description,
                "learning_path_id": template_section.learning_path_id
            }
            
            # Check if there's a user section linked to this template section
            linked_user_sections = db.query(UserSection).filter(
                UserSection.user_id == current_user.id,
                UserSection.section_template_id == section_id
            ).all()
            
            if linked_user_sections:
                result["linked_user_sections"] = [{
                    "id": s.id, 
                    "title": s.title,
                    "progress": s.progress
                } for s in linked_user_sections]
            else:
                result["linked_user_sections"] = []
        else:
            result["exists_in_db"]["as_template_section"] = False
        
        # Check cards in this section
        from app.models import section_cards, user_section_cards
        
        # Check template section cards if applicable
        if template_section:
            card_associations = db.query(section_cards).filter(
                section_cards.c.section_id == section_id
            ).all()
            
            if card_associations:
                result["template_section_cards"] = [{
                    "card_id": assoc.card_id,
                    "order_index": assoc.order_index
                } for assoc in card_associations]
            else:
                result["template_section_cards"] = []
        
        # Check user section cards if applicable
        if user_section:
            user_card_associations = db.query(user_section_cards).filter(
                user_section_cards.c.user_section_id == user_section.id
            ).all()
            
            if user_card_associations:
                result["user_section_cards"] = [{
                    "card_id": assoc.card_id,
                    "order_index": assoc.order_index,
                    "is_custom": assoc.is_custom
                } for assoc in user_card_associations]
            else:
                result["user_section_cards"] = []
        
        # Add specific information about problematic IDs
        if section_id in [2032, 2033]:
            # These are known problematic sections
            # Get ALL user sections that might relate
            all_user_sections = db.query(UserSection).filter(
                UserSection.user_id == current_user.id
            ).all()
            
            # Look for approximate matches
            possible_matches = []
            for section in all_user_sections:
                if abs(section.id - section_id) < 10 or (section.section_template_id and abs(section.section_template_id - section_id) < 10):
                    possible_matches.append({
                        "id": section.id,
                        "title": section.title,
                        "template_section_id": section.section_template_id,
                        "distance_from_target": abs(section.id - section_id)
                    })
            
            if possible_matches:
                result["possible_matches"] = sorted(possible_matches, key=lambda x: x["distance_from_target"])
        
        return result
        
    except Exception as e:
        logging.error(f"Error debugging section {section_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error debugging section: {str(e)}"
        )

def section_belongs_to_courses(db, section_id: int, course_ids: List[int]) -> bool:
    # 直接查询 association 表，看是否有对应关系
    assoc = db.query(course_section_association).filter(
        course_section_association.c.section_id == section_id,
        course_section_association.c.course_id.in_(course_ids)
    ).first()
    return assoc is not None

def get_course_id_for_section(db, section_id: int) -> Optional[int]:
    assoc = db.query(course_section_association.c.course_id).filter(
        course_section_association.c.section_id == section_id
    ).first()
    return assoc[0] if assoc else None

