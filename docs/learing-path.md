# Frontend Guide: Learning Path Generation and Retrieval

This document explains how the frontend should interact with the backend API to generate and display learning paths for users.

**Key Concept:** Learning path generation, especially when involving AI (like generating from a prompt or generating cards), is performed as an **asynchronous background task**. This means the initial API call returns quickly with a `task_id`, and the frontend must then poll a status endpoint to track progress and get the final result.

---

## 1. Generating a Learning Path from a User Prompt

This workflow is used when the user provides a natural language prompt (e.g., "I want to learn about web development") to generate a personalized learning path.

**Workflow:**

1.  **Initiate Generation:**
    *   **Endpoint:** `POST /api/chat/generate-learning-path`
    *   **Request Body:**
        ```json
        {
          "prompt": "User's natural language request"
        }
        ```
    *   **Action:** Send the user's prompt to this endpoint.
    *   **Reference:** `docs/learning_path_api_update01.md` (Section 4.A)

2.  **Receive Task ID:**
    *   **Success Response (200 OK):**
        ```json
        {
          "task_id": "string (e.g., full_path_gen_USERID_TIMESTAMP)",
          "message": "Learning path generation has started..."
        }
        ```
    *   **Action:** Store the `task_id`. Display the `message` to the user (e.g., "Generating your learning path..."). Start the polling process (Step 3).
    *   **Reference:** `docs/learning_path_api_update01.md` (Section 3.2)

3.  **Poll for Status:**
    *   **Endpoint:** `GET /api/tasks/{task_id}/status` (replace `{task_id}` with the received ID)
    *   **Action:** Periodically (e.g., every 5-10 seconds) call this endpoint.
    *   **Success Response (200 OK):** A JSON object detailing the task status. Key fields:
        *   `status`: "pending", "starting", "running", "completed", "failed", "timeout"
        *   `stage`: "initializing", "extracting_goals", "planning_path_structure", "generating_cards", "finished", "queued"
        *   `progress`: Overall percentage (0-100)
        *   `cards_completed`, `total_cards`: For card generation progress
        *   `learning_path_id`: The ID of the created path (available once the structure is saved, even if cards are still generating)
        *   `errors`: List of error messages if `status` is "failed" or "timeout"
    *   **UI/UX:** Use `stage`, `progress`, `cards_completed`, `total_cards` to show informative feedback.
    *   **Reference:** `docs/learning_path_api_update01.md` (Section 3.4, Section 4.B)

4.  **Handle Completion or Failure:**
    *   **Action:** Continue polling until `status` is "completed", "failed", or "timeout".
    *   **If "completed":**
        *   Stop polling.
        *   Retrieve the `learning_path_id` from the final status response.
        *   Proceed to Step 5 (Fetch Full Path).
    *   **If "failed" or "timeout":**
        *   Stop polling.
        *   Display an error message to the user (use the `errors` array if available).
    *   **Reference:** `docs/learning_path_api_update01.md` (Section 3.5, 3.6)

5.  **Fetch Full Path:**
    *   **Endpoint:** `GET /recommendation/learning-paths/{learning_path_id}/full` (replace `{learning_path_id}` with the ID obtained in Step 4)
    *   **Action:** Call this endpoint to get the complete learning path data.
    *   **Success Response (200 OK):** `LearningPathResponse` JSON object containing the path details, nested courses, sections, and the generated cards.
    *   **UI/UX:** Display the fetched learning path to the user.
    *   **Reference:** `docs/learning_path_course_section_cards.md` (Section 1), `docs/learning_path_api_update01.md` (Section 3.5)

---

## 2. Generating a Learning Path from a Predefined Structure

This workflow might be used if the frontend allows users to select specific courses/topics to build a path, and the backend needs to save this structure and generate cards.

*(Note: The specific endpoint `/recommendation/learning-paths/create-from-structure` mentioned in the context seems designed for this, but the exact frontend interaction pattern depends on the UI flow. The general principle of background task + polling still applies.)*

**General Workflow:**

1.  **Initiate Generation:**
    *   **Endpoint:** Likely `POST /recommendation/learning-paths/create-from-structure` (Confirm exact usage if needed)
    *   **Request Body:** A structure defining the path title and course titles (e.g., `LearningPathStructureRequest` schema).
        ```json
        {
          "prompt": "Optional original user prompt",
          "title": "Overall Learning Path Title",
          "courses": [
            { "title": "Course Title 1" },
            { "title": "Course Title 2" }
          ],
          "difficulty_level": "intermediate",
          "estimated_days": 30 // Optional
        }
        ```
    *   **Action:** Send the structured data.

2.  **Receive Task ID:**
    *   **Success Response (200 OK):** Similar to the prompt-based generation, expect a response with a `task_id`.
        ```json
        {
          "task_id": "string",
          "message": "Learning path creation from structure started..."
        }
        ```
    *   **Action:** Store `task_id`, display message, start polling.

3.  **Poll for Status:**
    *   **Endpoint:** `GET /api/tasks/{task_id}/status`
    *   **Action:** Same polling mechanism as described in Section 1, Step 3. The `stage` might differ initially (e.g., "saving_structure" before "generating_cards").

4.  **Handle Completion or Failure:**
    *   **Action:** Same logic as Section 1, Step 4.

5.  **Fetch Full Path:**
    *   **Endpoint:** `GET /recommendation/learning-paths/{learning_path_id}/full`
    *   **Action:** Same logic as Section 1, Step 5.

---

## 3. Fetching Existing Learning Paths

**A. Fetch User's Assigned Paths:**

*   **Endpoint:** `GET /learning-paths/users/me/learning-paths`
*   **Authentication:** Requires `Authorization: Bearer <token>` header.
*   **Action:** Call this to get the list of paths the currently logged-in user is enrolled in.
*   **Response:** `List[UserLearningPathResponse]`. Each item contains the path details (`learning_path` object) and user-specific progress. Note that the nested `learning_path` object here might not contain the full card details; use the `/full` endpoint for that if needed.
*   **Reference:** `docs/learning_path_course_section_cards.md` (Section 3)

**B. Fetch Public Path Templates:**

*   **Endpoint:** `GET /learning-paths/learning-paths`
*   **Action:** Call this to get a list of available public learning path templates (e.g., for browsing). Supports pagination (`skip`, `limit`) and `category` filtering.
*   **Response:** `List[LearningPathResponse]`. Nested courses/sections/cards might not be fully populated. Use the `/full` endpoint for complete details of a specific template.
*   **Reference:** `docs/learning_path_course_section_cards.md` (Section 2)

**C. Fetch Full Details of ANY Path (User's or Template):**

*   **Endpoint:** `GET /recommendation/learning-paths/{path_id}/full`
*   **Action:** This is the primary endpoint to get the *complete* data (including courses, sections, cards) for *any* learning path, whether it's one the user generated, one assigned to them, or a public template, provided you have its `path_id`.
*   **Response:** `LearningPathResponse` (fully populated).
*   **Reference:** `docs/learning_path_course_section_cards.md` (Section 1)

---

## 4. (Optional) Re-triggering Card Generation

If card generation failed initially or needs to be re-run for an existing path:

*   **Endpoint:** `POST /recommendation/learning-paths/{learning_path_id}/generate-cards`
*   **Action:** Call this endpoint with the ID of the existing learning path.
*   **Response:** Returns a *new* `task_id` for tracking the card generation process.
    ```json
    {
      "learning_path_id": 0,
      "task_id": "string",
      "message": "Card generation started..."
    }
    ```
*   **Follow-up:** Use the new `task_id` to poll the `GET /api/tasks/{task_id}/status` endpoint as described in Section 1, Step 3. Once completed, the cards will be available when fetching the full path via `GET /recommendation/learning-paths/{learning_path_id}/full`.
*   **Reference:** `docs/learning_path_course_section_cards.md` (Section 5)

---

See `docs/learning_path_api_update01.md` for a more detailed example of frontend polling logic and UI/UX considerations.