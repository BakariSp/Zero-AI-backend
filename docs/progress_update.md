# Backend Progress Update Logic

This document outlines the expected behavior and design for updating user progress within learning paths, courses, sections, and cards. Consistent and accurate progress tracking is crucial for a good user experience.

## Core Principle: Cascading Updates from Card Completion

When a user marks a card as completed or not completed, the backend should not only update the status of that individual card but also automatically recalculate and update the progress for all related parent entities:

1.  **Section Progress:** Based on the completion status of its constituent cards.
2.  **Course Progress:** Based on the progress of its constituent sections.
3.  **Learning Path Progress:** Based on the progress of its constituent courses.

This ensures that progress percentages at all levels are always synchronized and reflect the true state of the user's engagement.

## Card Completion Endpoint

To facilitate accurate cascading updates, the primary endpoint for marking a card's completion status *within the context of a user actively engaged in a specific learning path* should be:

**`PUT /api/users/me/learning-paths/{learning_path_id}/sections/{section_id}/cards/{card_id}`**

### Request

*   **Method:** `PUT`
*   **Path Parameters:**
    *   `learning_path_id`: The ID of the learning path the user is currently in.
    *   `section_id`: The ID of the section containing the card.
    *   `card_id`: The ID of the card whose completion status is being updated.
*   **Body (JSON):**
    ```json
    {
      "is_completed": true
    }
    ```
    or
    ```json
    {
      "is_completed": false
    }
    ```

### Behavior

1.  **Update Card Status:** The `is_completed` status of the specified `card_id` for the current user should be updated in the database.
2.  **Recalculate Section Progress:** After updating the card, the progress for `section_id` (within the context of `learning_path_id` and the current user) must be recalculated. This typically involves:
    *   Counting the number of completed cards in the section.
    *   Dividing by the total number of cards in the section.
    *   Storing the new progress percentage for the section.
3.  **Recalculate Course Progress:** After the section progress is updated, the progress for the course containing this section (within `learning_path_id` for the user) must be recalculated. This involves:
    *   Aggregating progress from all sections within the course (e.g., average, weighted average based on section length/difficulty, etc. - to be defined by business logic).
    *   Storing the new progress percentage for the course.
4.  **Recalculate Learning Path Progress:** After the course progress is updated, the overall progress for `learning_path_id` for the user must be recalculated. This involves:
    *   Aggregating progress from all courses within the learning path.
    *   Storing the new progress percentage for the learning path.

### Response

*   **Success (e.g., 200 OK or 204 No Content):**
    *   Should ideally return the updated entities (card, section, course, path) with their new progress, or at least confirm success. A 200 OK with the updated card and its parent section (with updated progress) could be very useful for the frontend to reduce follow-up GET requests.
    ```json
    // Example 200 OK response
    {
      "updated_card": { "id": 123, "is_completed": true, "..." },
      "updated_section_progress": 75, // Percentage
      "updated_course_progress": 50,  // Percentage
      "updated_learning_path_progress": 25 // Percentage
    }
    ```
*   **Error (e.g., 400 Bad Request, 404 Not Found, 500 Internal Server Error):**
    *   Standard error JSON response.

## Deprecation/Clarification of Other Endpoints

*   **`PUT /api/users/me/cards/{card_id}`:**
    *   This endpoint, if it exists for updating card completion, should be considered a more general update and *might not* have the full context of the `learning_path_id` and `section_id` to trigger the precise cascading progress updates outlined above.
    *   Its use for marking cards complete *while a user is actively navigating a learning path* is discouraged in favor of the more specific endpoint.
    *   If it *is* intended to also trigger full progress roll-up, it would need a mechanism to determine the relevant active learning path and section, which can be complex.

*   **`PUT /api/users/me/sections/{section_id}/progress`**
*   **`PUT /api/users/me/courses/{course_id}/progress`**
*   **`PUT /api/users/me/learning-paths/{path_id}/progress`**
    *   These endpoints are for directly setting progress percentages. They should primarily be reserved for administrative purposes or very specific scenarios where progress isn't derived from card completions (e.g., manual overrides, bulk imports).
    *   They should **not** be the primary mechanism for updating progress based on user interaction with cards.

## Frontend Considerations

The frontend should primarily use the `PUT /api/users/me/learning-paths/{learning_path_id}/sections/{section_id}/cards/{card_id}` endpoint when a user marks a card as complete/incomplete within a learning path.

Upon a successful response, the frontend should update its local state to reflect the new completion status and progress percentages provided by the backend, or re-fetch the relevant section/course data if the API response is minimal (e.g., 204 No Content).
