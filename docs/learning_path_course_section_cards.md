# Learning Path, Course, Section, and Card API Endpoints

This document outlines the key API endpoints for retrieving and managing learning paths, courses, sections, and cards.

**Base Path:** `/api` (Assumed prefix for all endpoints below)

---

## Learning Path Endpoints

### 1. Fetch Full Learning Path Structure

Retrieves a complete learning path, including its courses, sections, and cards. This is the recommended endpoint for displaying a full learning path view.

*   **Method:** `GET`
*   **Path:** `/recommendation/learning-paths/{path_id}/full`
*   **Description:** Retrieves a single learning path object by its ID, fully populated with its nested courses, sections, and cards.
*   **Path Parameters:**
    *   `path_id` (int): The ID of the learning path to retrieve.
*   **Request Body:** None
*   **Response Body:** `LearningPathResponse`
    ```json
    {
      "id": 0,
      "title": "string",
      "description": "string",
      "category": "string",
      "difficulty_level": "string",
      "estimated_days": 0,
      "courses": [
        {
          "id": 0,
          "title": "string",
          "description": "string",
          "estimated_days": 0,
          "sections": [
            {
              "id": 0,
              "title": "string",
              "description": "string",
              "order_index": 0,
              "estimated_days": 0,
              "cards": [
                {
                  "id": 0,
                  "keyword": "string",
                  "explanation": "string",
                  "resources": {},
                  "level": "string",
                  "tags": [],
                  "created_at": "2023-10-27T10:00:00Z",
                  "updated_at": "2023-10-27T10:00:00Z"
                }
              ],
              "created_at": "2023-10-27T10:00:00Z", // Section creation time
              "updated_at": "2023-10-27T10:00:00Z"  // Section update time
            }
          ],
          "created_at": "2023-10-27T10:00:00Z", // Course creation time
          "updated_at": "2023-10-27T10:00:00Z"  // Course update time
        }
      ],
      "sections": [], // Note: Included for backwards compatibility, prefer sections nested under courses
      "created_at": "2023-10-27T10:00:00Z", // Learning Path creation time
      "updated_at": "2023-10-27T10:00:00Z"  // Learning Path update time
    }
    ```

### 2. Fetch List of Learning Path Templates

Retrieves a list of available learning path templates (public paths).

*   **Method:** `GET`
*   **Path:** `/learning-paths/learning-paths`
*   **Description:** Retrieves a list of all available learning path templates. Supports pagination and category filtering. Note: Nested courses/sections might not be fully populated in this list view; use the `/full` endpoint for complete details of a specific path.
*   **Query Parameters:**
    *   `skip` (int, optional, default: 0): Number of paths to skip for pagination.
    *   `limit` (int, optional, default: 100): Maximum number of paths to return.
    *   `category` (str, optional): Filter paths by category name.
*   **Request Body:** None
*   **Response Body:** `List[LearningPathResponse]` (See schema above, but nested lists might be empty).

### 3. Fetch User's Assigned Learning Paths

Retrieves the learning paths assigned to the currently authenticated user.

*   **Method:** `GET`
*   **Path:** `/learning-paths/users/me/learning-paths`
*   **Description:** Retrieves a list of learning paths specifically assigned to the current user, including progress information.
*   **Request Body:** None
*   **Response Body:** `List[UserLearningPathResponse]`
    ```json
    [
      {
        "id": 0, // UserLearningPath association ID
        "user_id": 0,
        "progress": 0.0, // e.g., 0.75 for 75%
        "start_date": "2023-10-27T10:00:00Z",
        "completed_at": "2023-10-27T10:00:00Z", // null if not completed
        "learning_path": { // LearningPathResponse object (may or may not be fully nested)
          "id": 0,
          "title": "string",
          // ... other LearningPath fields
        }
      }
    ]
    ```

### 4. Generate and Save Learning Path

Generates a new learning path based on user input, saves it, assigns it to the user, and starts background card generation.

*   **Method:** `POST`
*   **Path:** `/recommendation/learning-paths/generate`
*   **Description:** Creates a new learning path structure (Path, Courses, Sections) based on interests, saves it, assigns it to the user, and triggers background card generation.
*   **Request Body:** `LearningPathRequest`
    ```json
    {
      "interests": ["string"],
      "difficulty_level": "string", // e.g., "beginner", "intermediate", "advanced"
      "estimated_days": 0 // Optional total duration
    }
    ```
*   **Response Body:** `Dict[str, Any]`
    ```json
    {
      "learning_path": { // LearningPathResponse object (without cards initially)
        "id": 0,
        "title": "string",
        // ... other LearningPath fields
        "courses": [ // Courses and Sections are created
          {
            "id": 0,
            "title": "string",
            "sections": [
              { "id": 0, "title": "string" /* ... */ }
            ]
            // ... other Course fields
          }
        ]
      },
      "task_id": "string", // ID to track background card generation status
      "message": "Learning path created. Cards are being generated in the background."
    }
    ```

### 5. Generate Cards for Existing Learning Path

Triggers background card generation for a learning path that already exists.

*   **Method:** `POST`
*   **Path:** `/recommendation/learning-paths/{learning_path_id}/generate-cards`
*   **Description:** Starts the background process to generate cards for all sections within an existing learning path. Useful if initial generation failed or needs re-running.
*   **Path Parameters:**
    *   `learning_path_id` (int): The ID of the learning path.
*   **Request Body:** None
*   **Response Body:** `Dict[str, Any]`
    ```json
    {
      "learning_path_id": 0,
      "task_id": "string", // ID to track background card generation status
      "message": "Card generation started. Cards are being generated in the background."
    }
    ```

### 6. Get Specific Learning Path (Template Info)

Retrieves basic information about a specific learning path template. For full details including courses/sections/cards, use the `/full` endpoint.

*   **Method:** `GET`
*   **Path:** `/learning-paths/learning-paths/{path_id}`
*   **Description:** Retrieves top-level details for a specific learning path template by ID.
*   **Path Parameters:**
    *   `path_id` (int): The ID of the learning path template.
*   **Request Body:** None
*   **Response Body:** `LearningPathResponse` (Nested `courses` and `sections` might be empty or partially populated).

---

## Course Endpoints

### 1. Fetch Courses for a Public Learning Path

Retrieves the list of courses associated with a specific public learning path template.

*   **Method:** `GET`
*   **Path:** `/courses/learning-paths/{path_id}/courses`
*   **Description:** Gets all courses associated with a specific public learning path template ID.
*   **Path Parameters:**
    *   `path_id` (int): The ID of the learning path template.
*   **Request Body:** None
*   **Response Body:** `List[CourseResponse]`
    ```json
    [
      {
        "id": 0,
        "title": "string",
        "description": "string",
        "estimated_days": 0,
        "sections": [ // Sections might be included here depending on implementation
          {
            "id": 0,
            "title": "string",
            // ... other Section fields (cards likely omitted here)
          }
        ],
        "created_at": "2023-10-27T10:00:00Z",
        "updated_at": "2023-10-27T10:00:00Z"
      }
    ]
    ```

### 2. Fetch Courses for a User's Learning Path

Retrieves the courses for a specific learning path assigned to the current user, including progress.

*   **Method:** `GET`
*   **Path:** `/courses/users/me/learning-paths/{path_id}/courses`
*   **Description:** Retrieves the list of courses for a specific learning path assigned to the current user, including user-specific progress data for each course.
*   **Path Parameters:**
    *   `path_id` (int): The ID of the learning path assigned to the user.
*   **Request Body:** None
*   **Response Body:** `List[UserCourseResponse]` (Schema details depend on `UserCourseResponse` definition, typically includes `CourseResponse` and user progress fields like `status`, `completed_at`, etc.)

### 3. Fetch Specific Course Template

Retrieves details for a single course template.

*   **Method:** `GET`
*   **Path:** `/courses/courses/{course_id}`
*   **Description:** Get details of a specific course template by its ID.
*   **Path Parameters:**
    *   `course_id` (int): The ID of the course template.
*   **Request Body:** None
*   **Response Body:** `CourseResponse` (See schema under Learning Path Endpoints -> Fetch Full Structure). Includes nested sections, but likely not cards.

---

## Section Endpoints

*(Note: Sections are typically retrieved as part of a Course or Learning Path. Direct section endpoints might be less common for frontend use unless managing sections directly).*

---

## Card Endpoints

### 1. Fetch Cards for a Specific Section

Retrieves all cards belonging to a specific section. Useful for lazy-loading cards within a section.

*   **Method:** `GET`
*   **Path:** `/cards/sections/{section_id}/cards`
*   **Description:** Retrieves all cards associated with a specific course section ID.
*   **Path Parameters:**
    *   `section_id` (int): The ID of the section.
*   **Request Body:** None
*   **Response Body:** `List[CardResponse]`
    ```json
    [
      {
        "id": 0,
        "keyword": "string",
        "explanation": "string",
        "resources": {},
        "level": "string",
        "tags": [],
        "created_at": "2023-10-27T10:00:00Z",
        "updated_at": "2023-10-27T10:00:00Z"
      }
    ]
    ```

### 2. Fetch Cards (General Query)

Retrieves a list of cards, potentially filtered.

*   **Method:** `GET`
*   **Path:** `/cards/cards`
*   **Description:** Get a list of cards with optional filtering and pagination.
*   **Query Parameters:**
    *   `skip` (int, optional, default: 0): Number of cards to skip.
    *   `limit` (int, optional, default: 100): Maximum number of cards to return.
    *   `keyword` (str, optional): Filter cards by keyword (partial match).
    *   `section_id` (int, optional): Filter cards belonging to a specific section.
*   **Request Body:** None
*   **Response Body:** `List[CardResponse]` (See schema above).

---

## Recommendation Endpoints

### 1. Fetch Generic Recommendations

Retrieves general recommendations for display (e.g., on a landing page).

*   **Method:** `GET`
*   **Path:** `/recommendation/recommendations`
*   **Description:** Get generic recommendations: top learning paths, courses, and cards.
*   **Request Body:** None
*   **Response Body:** `RecommendationResponse`
    ```json
    {
      "learning_paths": [ /* List[LearningPathResponse] */ ],
      "courses": [ /* List[CourseResponse] */ ],
      "cards": [ /* List[CardResponse] */ ]
    }
    ```

### 2. Fetch Personalized Recommendations (Preview)

Generates *temporary* recommendations based on user interests without saving anything.

*   **Method:** `POST`
*   **Path:** `/recommendation/recommendations/personalized`
*   **Description:** Generates temporary, personalized learning path, course, and card recommendations based on user interests for preview purposes. Does not save the generated path.
*   **Request Body:**
    ```json
    {
      "interests": ["string"],
      "difficulty_level": "string" // Optional, e.g., "intermediate"
    }
    ```
*   **Response Body:** `RecommendationResponse` (Contains the generated path/course/card suggestions).
