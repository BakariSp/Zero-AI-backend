# Progress Tracking Documentation

This document outlines how progress tracking is implemented across different entities in the Zero-AI learning platform.

## Overview

The Zero-AI platform tracks user progress at multiple levels:

1. **Learning Path Progress** - Overall progress through a learning path
2. **Course Progress** - Progress through individual courses
3. **Section Progress** - Progress through individual sections
4. **Card Completion** - Completion status of individual flashcards

## New Backend-Driven Progress System

As of the latest update, the Zero-AI backend now automatically manages all progress calculation and updates. When a card's completion status changes, the backend will:

1. Update all sections containing that card
2. Update all courses containing those sections
3. Update all learning paths containing those courses

This means the frontend only needs to mark cards as completed/uncompleted, and the backend will handle all progress calculations automatically.

## Database Schema

### Progress Fields in Models

| Entity | Table | Progress Field | Type | Range |
|--------|-------|---------------|------|-------|
| Learning Path | user_learning_paths | progress | Float | 0.0 to 100.0 |
| Course | user_courses | progress | Float | 0.0 to 100.0 |
| Section | user_sections | progress | Float | 0.0 to 100.0 |
| Card | user_cards | is_completed | Boolean | true/false |

## API Endpoints

### Card Completion (Primary Method)

This is now the recommended way to update progress. Simply mark a card as completed, and the backend will update all related progress values.

```http
PUT /users/me/cards/{card_id}
```

Request body:
```json
{
  "is_completed": true
}
```

Response includes the updated card data:
```json
{
  "card": { "id": 123, "keyword": "Example", ... },
  "card_id": 123,
  "user_id": 456,
  "is_completed": true,
  ...
}
```

### Section-Based Card Completion

Alternative method for marking a card as completed within a specific section:

```http
PUT /users/me/sections/{section_id}/cards/{card_id}/completion?is_completed=true
```

Response includes the updated section with all cards and their completion status.

### Direct Progress Updates (For Special Cases Only)

These endpoints still exist but are now primarily for admin use or special cases. The frontend should prefer the card completion endpoints above.

#### Learning Path Progress (Admin Use)

```http
PUT /learning-paths/{path_id}
```

Request body:
```json
{
  "progress": 75.5
}
```

#### Course Progress (Admin Use)

```http
PUT /users/me/courses/{course_id}
```

Request body:
```json
{
  "progress": 75.5
}
```

#### Section Progress (Admin Use)

```http
PUT /users/me/sections/{section_id}/progress?progress=75.5
```

## Card Completion Status in Responses

When fetching user sections, each card in the section includes its completion status:

```json
{
  "id": 123,
  "title": "Introduction to AI",
  "order_index": 1,
  "progress": 50.0,
  "cards": [
    {
      "card": { 
        "id": 456, 
        "keyword": "Machine Learning",
        "question": "What is machine learning?",
        "answer": "..."
      },
      "order_index": 1,
      "is_custom": false,
      "is_completed": true
    },
    {
      "card": { 
        "id": 457, 
        "keyword": "Neural Networks",
        "question": "What are neural networks?",
        "answer": "..."
      },
      "order_index": 2,
      "is_custom": false,
      "is_completed": false
    }
  ]
}
```

## Frontend Implementation

### Progress Bars

The frontend should implement progress bars at each level, but now only needs to GET the data, not calculate it:

1. **Learning Path Progress** - Display the `progress` value from the learning path API response
2. **Course Progress** - Display the `progress` value from the course API response
3. **Section Progress** - Display the `progress` value from the section API response

### Progress Updates

For updating progress, the frontend now only needs to:

1. Mark cards as completed/uncompleted using the card completion endpoints
2. Fetch updated progress values after card completion to update UI

### Frontend Code Example

```typescript
// Example function to mark a card as completed
async function markCardCompleted(cardId: number, isCompleted: boolean) {
  try {
    // Call the API to mark the card as completed
    const response = await api.put(`/users/me/cards/${cardId}`, {
      is_completed: isCompleted
    });
    
    // Card data is updated in the response
    return response.data;
  } catch (error) {
    console.error("Failed to update card completion status:", error);
    throw error;
  }
}

// Example function to mark a card as completed within a section
async function markCardCompletedInSection(sectionId: number, cardId: number, isCompleted: boolean) {
  try {
    const response = await api.put(
      `/users/me/sections/${sectionId}/cards/${cardId}/completion?is_completed=${isCompleted}`
    );
    
    // The entire section with updated progress is returned
    return response.data;
  } catch (error) {
    console.error("Failed to update card completion status:", error);
    throw error;
  }
}

// Example function to refresh learning path data after card completion
async function refreshLearningPathAfterCardCompletion(pathId: number) {
  try {
    // Get updated learning path data with new progress values
    const response = await api.get(`/users/me/learning-paths/${pathId}`);
    return response.data;
  } catch (error) {
    console.error("Failed to refresh learning path data:", error);
    throw error;
  }
}
```

### Achievement Notifications

The backend automatically checks for completion-based achievements when cards are marked as completed. The frontend should check for new achievements after card completion:

```typescript
async function checkForAchievements() {
  try {
    const response = await api.post('/achievements/users/me/check-achievements');
    if (response.data.length > 0) {
      // Show notification for new achievements
      showAchievementNotification(response.data);
    }
    return response.data;
  } catch (error) {
    console.error("Failed to check for achievements:", error);
    return [];
  }
}
```

## UI Components

### Progress Component Examples

1. **Linear Progress Bar**: Use for learning paths, courses, and sections
   ```html
   <div class="progress-container">
     <div class="progress-label">Section 1: Introduction</div>
     <div class="progress-bar">
       <div class="progress-fill" style="width: 75%"></div>
     </div>
     <div class="progress-percentage">75%</div>
   </div>
   ```

2. **Circular Progress**: Alternative visualization for overall progress
   ```html
   <div class="circular-progress" style="--progress: 75">
     <div class="progress-value">75%</div>
   </div>
   ```

### Completion Indicators

For cards:

```html
<div class="card-item ${card.is_completed ? 'completed' : ''}">
  <div class="card-title">${card.title}</div>
  <div class="completion-indicator">
    <i class="icon ${card.is_completed ? 'icon-check' : 'icon-circle'}"></i>
  </div>
  <button 
    class="completion-toggle" 
    onclick="markCardCompleted(${card.id}, !card.is_completed)">
    ${card.is_completed ? 'Mark Incomplete' : 'Mark Complete'}
  </button>
</div>
```

## Best Practices

1. **Single Source of Truth**: Rely on the backend for all progress calculations - don't recalculate on the frontend.

2. **Real-time Updates**: When a user completes a card, immediately update the UI with the received progress value.

3. **Batch Operations**: If updating multiple cards at once, consider refreshing progress data after all updates are complete.

4. **Error Handling**: Implement proper error handling for progress update failures.

5. **Loading States**: Show loading states during progress updates to provide user feedback.

6. **Progress Animations**: Consider animating progress changes for a better user experience.

7. **Caching**: Cache progress data appropriately but refresh after card completion operations.

8. **Optimistic Updates**: Consider implementing optimistic UI updates while waiting for backend confirmation.

## Migration Guide

If you're updating from a previous version:

1. Remove any frontend progress calculation logic - the backend now handles this
2. Update progress bar components to use the backend-provided progress values
3. Replace any direct progress update calls with card completion calls where possible
4. Update UI components to reflect the latest progress after card completion operations
