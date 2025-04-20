# Task Status API Documentation

This API allows the frontend to track the status and progress of background operations, such as learning path generation or card creation. It uses a database table (`user_tasks`) to store persistent task information.

---

## 1. Get Status of a Specific Task

Retrieves the current status, progress, and details of a single background task using its unique `task_id`. This is the primary endpoint for polling task progress after initiating a background operation.

*   **Method:** `GET`
*   **Path:** `/api/tasks/{task_id}/status`
*   **Description:** Fetches the details of the task identified by `task_id`.
*   **Path Parameters:**
    *   `task_id` (string): The unique identifier of the task, obtained when the background operation was initiated (e.g., from `POST /recommendation/learning-paths/generate`).
*   **Authentication:** Requires `Authorization: Bearer <token>` header. The user must either own the task or be an administrator.
*   **Success Response (200 OK):** `UserTaskResponse`
    ```json
    {
      "task_id": "full_path_gen_USERID_TIMESTAMP", // The unique task ID
      "user_id": 123, // ID of the user who initiated the task
      "learning_path_id": 456, // ID of the associated learning path (if applicable, might be null initially)
      "status": "running", // Current status: "pending", "queued", "starting", "running", "completed", "failed", "timeout"
      "stage": "generating_cards", // Current stage: "initializing", "planning_path_structure", "saving_structure", "generating_cards", "finished", etc. (Nullable)
      "progress": 45.0, // Overall progress percentage (0.0 to 100.0)
      "total_items": 50, // Estimated total items (e.g., cards) to process (Nullable)
      "completed_items": 23, // Items completed so far (e.g., cards)
      "result_message": null, // Short message on completion or failure (Nullable)
      "error_details": null, // Detailed error message or traceback if status is "failed" (Nullable)
      "started_at": "2023-10-27T10:05:00Z", // Timestamp when the task started processing (Nullable)
      "ended_at": null, // Timestamp when the task finished (completed, failed, timeout) (Nullable)
      "id": 789, // Database ID of the task record
      "created_at": "2023-10-27T10:00:00Z", // Timestamp when the task was created/scheduled
      "updated_at": "2023-10-27T10:15:00Z" // Timestamp of the last status update
    }
    ```
*   **Error Responses:**
    *   `401 Unauthorized`: If the user is not logged in.
    *   `403 Forbidden`: If the user is logged in but does not own the task and is not an admin.
    *   `404 Not Found`: If no task exists with the given `task_id`.

---

## 2. Get Tasks for Current User

Retrieves a list of background tasks initiated by the currently authenticated user, ordered by creation date (most recent first). Useful for displaying a user's task history.

*   **Method:** `GET`
*   **Path:** `/api/tasks/users/me`
*   **Description:** Fetches a paginated list of tasks belonging to the current user.
*   **Query Parameters:**
    *   `skip` (int, optional, default: 0): Number of tasks to skip for pagination.
    *   `limit` (int, optional, default: 20): Maximum number of tasks to return.
*   **Authentication:** Requires `Authorization: Bearer <token>` header.
*   **Success Response (200 OK):** `List[UserTaskResponse]`
    ```json
    [
      {
        "task_id": "full_path_gen_USERID_TIMESTAMP_2",
        "user_id": 123,
        "learning_path_id": 789,
        "status": "completed",
        "stage": "finished",
        "progress": 100.0,
        // ... other fields as in UserTaskResponse ...
        "id": 999,
        "created_at": "2023-10-28T11:00:00Z",
        "updated_at": "2023-10-28T11:30:00Z"
      },
      {
        "task_id": "full_path_gen_USERID_TIMESTAMP_1",
        "user_id": 123,
        "learning_path_id": 456,
        "status": "failed",
        "stage": "generating_cards",
        "progress": 50.0,
        "result_message": "Task failed during execution.",
        "error_details": "...",
        // ... other fields ...
        "id": 789,
        "created_at": "2023-10-27T10:00:00Z",
        "updated_at": "2023-10-27T10:20:00Z"
      }
      // ... more tasks up to the limit ...
    ]
    ```
*   **Error Responses:**
    *   `401 Unauthorized`: If the user is not logged in.

---

## 3. Get Latest Task for a Learning Path

Retrieves the most recent background task associated with a specific learning path ID. This is useful for checking the status of the latest operation (e.g., generation or card update) performed on a particular path.

*   **Method:** `GET`
*   **Path:** `/api/tasks/learning-paths/{learning_path_id}`
*   **Description:** Fetches the latest task record linked to the given `learning_path_id`.
*   **Path Parameters:**
    *   `learning_path_id` (int): The ID of the learning path.
*   **Authentication:** Requires `Authorization: Bearer <token>` header. The user must have permission to view the task (e.g., own it or be an admin).
*   **Success Response (200 OK):** `UserTaskResponse`
    ```json
    {
      "task_id": "card_gen_LPID_TIMESTAMP", // The unique task ID
      "user_id": 123,
      "learning_path_id": 456, // The requested learning path ID
      "status": "running",
      "stage": "generating_cards",
      "progress": 75.0,
      // ... other fields as in UserTaskResponse ...
      "id": 1001,
      "created_at": "2023-10-29T09:00:00Z",
      "updated_at": "2023-10-29T09:45:00Z"
    }
    ```
*   **Error Responses:**
    *   `401 Unauthorized`: If the user is not logged in.
    *   `403 Forbidden`: If the user is logged in but does not have permission to view the task associated with this learning path.
    *   `404 Not Found`: If no task is found associated with the given `learning_path_id`.

---