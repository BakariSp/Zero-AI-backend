# Progress Tracking Module

This module provides utilities for automatic progress tracking and updates across the learning hierarchy of Zero-AI:

1. Cards -> Sections -> Courses -> Learning Paths

## Key Features

- Automatic progress calculation based on completed cards
- Cascading updates that propagate progress changes up the hierarchy
- Progress synchronization across all levels of content
- Support for achievement tracking based on progress milestones

## Main Functions

### 1. `cascade_progress_update(db, user_id, card_id, update_all=False)`

The main utility function that handles progress updates throughout the entire hierarchy when a card's completion status changes.

**Usage:**
```python
from app.progress import cascade_progress_update

# When a user completes or uncompletes a card
result = cascade_progress_update(db, user_id=current_user.id, card_id=123)
```

**Returns:** A dictionary with information about what was updated:
```python
{
    "sections_updated": [{"id": 1, "progress": 75.0}, ...],
    "courses_updated": [50.0, 25.0, ...],
    "learning_paths_updated": [33.3, ...]
}
```

### 2. Individual Update Functions

These functions can be used to update specific parts of the hierarchy:

- `update_section_progress_based_on_cards(db, user_id, section_id)`
- `update_course_progress_based_on_sections(db, user_id, section_id=None)`
- `update_learning_path_progress_based_on_courses(db, user_id, course_id=None)`

## Progress Calculation Logic

1. **Section Progress:** Percentage of completed cards in the section
   ```
   section_progress = (completed_cards / total_cards) * 100
   ```

2. **Course Progress:** Average progress of all sections in the course
   ```
   course_progress = sum(section_progress for section in sections) / number_of_sections
   ```

3. **Learning Path Progress:** Average progress of all courses in the learning path
   ```
   learning_path_progress = sum(course_progress for course in courses) / number_of_courses
   ```

## Integration with API Endpoints

The progress tracking is integrated with several API endpoints:

1. **Card Completion:** When a card is marked as completed or uncompleted
   - `/users/me/cards/{card_id}` (PUT)
   - `/users/me/sections/{section_id}/cards/{card_id}/completion` (PUT)

2. **Section Progress:** When section progress is manually updated
   - `/users/me/sections/{section_id}/progress` (PUT)

3. **Course Progress:** When course progress is manually updated
   - `/users/me/courses/{course_id}` (PUT)

## Frontend Considerations

The frontend should:

1. Call the appropriate card completion endpoint when a user completes a card
2. Display the updated progress values returned by the API
3. No need to manually calculate progress on the frontend

## Example

```python
# Example: Updating a card's completion status
@router.put("/users/me/cards/{card_id}", response_model=UserCardResponse)
def update_saved_card(
    card_id: int,
    user_card: UserCardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Store the old card state
    old_card = get_user_card_by_id(db, user_id=current_user.id, card_id=card_id)
    old_completed = old_card.get("is_completed", False) if old_card else False

    # Update the card
    result = update_user_card(db, user_id=current_user.id, card_id=card_id, ...)
    
    # If completion status changed, update progress
    if user_card.is_completed is not None and user_card.is_completed != old_completed:
        progress_updates = cascade_progress_update(db, user_id=current_user.id, card_id=card_id)
        
    # Check for achievements if completed
    if user_card.is_completed:
        check_completion_achievements(db, user_id=current_user.id)
    
    return result
``` 