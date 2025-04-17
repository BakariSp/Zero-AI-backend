## Frontend Documentation: Update to Learning Path Generation API

**Date:** 2024-07-26

**Author:** AI Assistant

**Version:** 1.0

### 1. Summary of Change

The API endpoint for generating a learning path from a chat prompt (`POST /api/chat/generate-learning-path`) has been significantly updated to improve user experience and frontend responsiveness.

Previously, this endpoint would perform the entire generation process (extracting goals, planning the path structure via AI, saving to the database) before returning a response. This could take a considerable amount of time (potentially minutes), leaving the user waiting without feedback.

**The endpoint now returns almost immediately**, scheduling the entire generation process (including card generation) as a background task. The frontend will receive a `task_id` and must then poll a new status endpoint to track the progress and retrieve the final result.

### 2. Old Workflow (Deprecated)

1.  Frontend sends `POST /api/chat/generate-learning-path` with a `{ prompt: "..." }` body.
2.  Backend performs goal extraction (AI call), path planning (AI call), database writes.
3.  Backend schedules *only* card generation as a background task.
4.  Backend returns the learning path structure (without cards) and a `task_id` for *card generation only*.
5.  **Problem:** Steps 2 & 3 could take a long time, blocking the frontend.

### 3. New Workflow (Current)

1.  **Initiate Generation:**
    *   Frontend sends `POST /api/chat/generate-learning-path` with a `{ prompt: "..." }` body.
    *   Reference: `app/recommendation/routes.py` (lines 338-372)
2.  **Receive Task ID:**
    *   Backend immediately schedules the *entire* generation process (goal extraction, path planning, DB creation, card generation) as a single background task.
    *   Backend responds instantly with a `TaskCreationResponse`:
        ```json
        {
          "task_id": "full_path_gen_USERID_TIMESTAMP",
          "message": "Learning path generation has started. You can check the status using the task ID."
        }
        ```
    *   Reference: `app/recommendation/routes.py` (lines 334-336)
3.  **Start Polling:**
    *   Frontend receives the `task_id`.
    *   Frontend begins polling the new status endpoint: `GET /api/tasks/{task_id}/status` every few seconds (e.g., 5-10 seconds).
    *   **Note:** Ensure this endpoint is correctly registered in the main FastAPI application (likely mounting `task_router` from `app.services.background_tasks.py`).
4.  **Track Progress:**
    *   The status endpoint (`GET /api/tasks/{task_id}/status`) returns a JSON object detailing the task's current state. Example structure:
        ```json
        {
            "status": "running", // "pending", "starting", "running", "completed", "failed", "timeout"
            "stage": "generating_cards", // "initializing", "extracting_goals", "planning_path_structure", "generating_cards", "finished", "queued"
            "progress": 45, // Overall progress percentage (mainly based on card generation)
            "total_cards": 50, // Estimated total cards to generate
            "cards_completed": 23, // Cards generated so far
            "learning_path_id": 123, // Populated once the path structure is created
            "errors": [], // List of error messages if status is "failed" or "timeout"
            "start_time": 1678886400.0, // Task start timestamp
            "end_time": null, // Task end timestamp (null if running)
            "task_id": "full_path_gen_USERID_TIMESTAMP"
            // "error_details": "..." // Optional traceback if status is "failed"
        }
        ```
    *   Reference: `app/services/background_tasks.py` (lines 96-105, 178-189 for status structure)
    *   Use the `stage`, `progress`, `cards_completed`, and `total_cards` fields to provide informative feedback to the user (e.g., "Planning path...", "Generating cards (23/50)...").
5.  **Handle Completion:**
    *   Continue polling until the `status` field is `"completed"`.
    *   Once completed, retrieve the `learning_path_id` from the final status response.
    *   Use this `learning_path_id` to fetch the complete learning path data (including courses, sections, and now potentially the generated cards) using the existing endpoint, likely `GET /recommendation/learning-paths/{path_id}/full`.
    *   Reference: `app/recommendation/routes.py` (lines 48-66)
6.  **Handle Errors:**
    *   If the polling response shows `status` as `"failed"` or `"timeout"`, stop polling.
    *   Display an appropriate error message to the user. You can use the `errors` array from the status response for more details.

### 4. API Endpoint Details

**A. Initiate Learning Path Generation**

*   **Method:** `POST`
*   **Path:** `/api/chat/generate-learning-path`
*   **Request Body:**
    ```json
    {
      "prompt": "string" // User's natural language request
    }
    ```
*   **Success Response (200 OK):** `TaskCreationResponse`
    ```json
    {
      "task_id": "string",
      "message": "string"
    }
    ```
*   **Failure Response:** Standard HTTP errors (e.g., 400 for empty prompt, 500 for scheduling failure).

**B. Get Task Status**

*   **Method:** `GET`
*   **Path:** `/api/tasks/{task_id}/status`
*   **Path Parameter:**
    *   `task_id` (string): The ID received from the initiation endpoint.
*   **Success Response (200 OK):** Task Status JSON object (see example in section 3.4).
*   **Failure Response:**
    *   `404 Not Found`: If the `task_id` does not exist or doesn't belong to the user.

### 5. Example Frontend Logic (High-Level)
javascript
// State variables
const [isLoading, setIsLoading] = useState(false);
const [taskId, setTaskId] = useState(null);
const [taskStatus, setTaskStatus] = useState(null);
const [pollingIntervalId, setPollingIntervalId] = useState(null);
const [generatedPath, setGeneratedPath] = useState(null);
const [errorMessage, setErrorMessage] = useState(null);
// 1. Function to initiate generation
const handleGeneratePath = async (prompt) => {
setIsLoading(true);
setErrorMessage(null);
setTaskId(null);
setTaskStatus(null);
setGeneratedPath(null);
if (pollingIntervalId) clearInterval(pollingIntervalId);
try {
// Call POST /api/chat/generate-learning-path
const response = await apiGenerateLearningPathFromChat(prompt);
setTaskId(response.task_id);
// Start polling immediately
startPolling(response.task_id);
} catch (error) {
setErrorMessage("Failed to start learning path generation.");
setIsLoading(false);
}
};
// 2. Function to poll status
const pollStatus = async (currentTaskId) => {
try {
// Call GET /api/tasks/{currentTaskId}/status
const statusResponse = await apiGetTaskStatus(currentTaskId);
setTaskStatus(statusResponse);
// Check status and stop polling if needed
if (statusResponse.status === 'completed') {
clearInterval(pollingIntervalId);
setPollingIntervalId(null);
// Fetch the final path data
fetchGeneratedPath(statusResponse.learning_path_id);
} else if (statusResponse.status === 'failed' || statusResponse.status === 'timeout') {
clearInterval(pollingIntervalId);
setPollingIntervalId(null);
setErrorMessage(statusResponse.errors?.join(', ') || 'Generation failed or timed out.');
setIsLoading(false);
}
// If still running, the interval will call pollStatus again
} catch (error) {
// Handle polling errors (e.g., network issue, 404)
clearInterval(pollingIntervalId);
setPollingIntervalId(null);
setErrorMessage("Error checking generation status.");
setIsLoading(false);
}
};
// 3. Function to start polling
const startPolling = (currentTaskId) => {
// Poll immediately first time
pollStatus(currentTaskId);
// Then set interval
const intervalId = setInterval(() => {
pollStatus(currentTaskId);
}, 5000); // Poll every 5 seconds
setPollingIntervalId(intervalId);
};
// 4. Function to fetch the final path
const fetchGeneratedPath = async (pathId) => {
try {
// Call GET /recommendation/learning-paths/{pathId}/full
const pathData = await apiGetLearningPathFull(pathId);
setGeneratedPath(pathData);
setIsLoading(false);
// Navigate user or display the path
} catch (error) {
setErrorMessage("Failed to retrieve the generated learning path.");
setIsLoading(false);
}
};
// Remember to clear interval on component unmount
useEffect(() => {
return () => {
if (pollingIntervalId) {
clearInterval(pollingIntervalId);
}
};
}, [pollingIntervalId]);
// UI Rendering based on isLoading, taskStatus, generatedPath, errorMessage
// ... display progress messages based on taskStatus.stage, taskStatus.progress etc.



### 6. UI/UX Considerations

*   Provide immediate feedback after the user submits the prompt, indicating that generation has started (using the message from the initial response).
*   Display the current stage of the process (e.g., "Analyzing request...", "Planning curriculum...", "Generating learning cards...").
*   Show a progress indicator. If `total_cards` is available, showing "X / Y cards generated" is helpful. Otherwise, use the overall `progress` percentage or a more general indeterminate progress bar.
*   Clearly indicate success, failure, or timeout states.
*   Allow the user to potentially navigate away while generation happens in the background (though this requires more complex state management to resume tracking if they return).