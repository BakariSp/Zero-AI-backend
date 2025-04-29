## API Updates for Learning Paths (Update 01)

This document outlines recent updates to the Learning Path API endpoints.

**New Endpoints:**

*   `/generate-learning-courses`: Generates course outlines and initial sections based on user interests.
*   `/generate-course-titles`: Generates potential course titles based on user interests, excluding existing ones.
*   `/generate-sections`: Generates sections for given course titles.
*   `/users/me/learning-paths/basic`: Retrieves a simplified list of learning paths assigned to the current user.
*   `DELETE /users/me/learning-paths/{path_id}`: Allows a user to delete a learning path assigned to them.

**Endpoint Details:**

*   **`/generate-learning-courses`**
    *   **Method:** `POST`
    *   **Request Body:** `GenerateLearningPathRequest` (same as `/generate-learning-path`)
        ```json
        {
          "interests": ["Python programming", "web development"],
          "difficulty_level": "Intermediate",
          "estimated_days": 10,
          "existing_items": ["Introduction to Python"]
        }
        ```
    *   **Response Body:**
        ```json
        {
          "courses": [
            {
              "title": "Advanced Python Concepts",
              "sections": ["Decorators", "Generators", "Context Managers", "Metaclasses"]
            },
            {
              "title": "Flask Web Framework",
              "sections": ["Routing", "Templates", "Forms", "Database Integration"]
            }
            // ... up to 5 new courses, each with up to 4 sections
          ]
        }
        ```
    *   **Description:** Takes user interests, difficulty, duration, and *optionally* a list of existing course titles. It generates *new* course titles (up to 5) and then generates corresponding section titles (up to 4 per course) for those new courses.

*   **`/generate-course-titles`**
    *   **Method:** `POST`
    *   **Request Body:** `GenerateCourseTitleRequest`
        ```json
        {
          "interests": ["Data Science", "Machine Learning"],
          "difficulty_level": "Beginner",
          "estimated_days": 15,
          "existing_items": ["Introduction to Python for Data Science"]
        }
        ```
    *   **Response Body:**
        ```json
        {
          "titles": [
            "Data Cleaning and Preparation",
            "Exploratory Data Analysis",
            "Introduction to Scikit-learn",
            "Basic Regression Models",
            "Data Visualization with Matplotlib"
          ]
        }
        ```
    *   **Description:** Generates a list of potential course titles based on the provided criteria, filtering out any titles provided in `existing_items`. Returns up to 5 new titles.

*   **`/generate-sections`**
    *   **Method:** `POST`
    *   **Request Body:** `GenerateDetailsFromOutlineRequest`
        ```json
        {
          "titles": ["Advanced Python Concepts", "Flask Web Framework"],
          "difficulty_level": "Intermediate",
          "estimated_days": 10 // Note: estimated_days might influence section detail/scope
        }
        ```
    *   **Response Body:**
        ```json
        {
          "courses": [
            {
              "title": "Advanced Python Concepts",
              "sections": ["Decorators", "Generators", "Context Managers", "Metaclasses"]
            },
            {
              "title": "Flask Web Framework",
              "sections": ["Routing", "Templates", "Forms", "Database Integration"]
            }
            // ... sections for each title provided, up to 4 sections per title
          ]
        }
        ```
    *   **Description:** Takes a list of course titles and generates corresponding section titles (up to 4 per course).

*   **`/users/me/learning-paths/basic`**
    *   **Method:** `GET`
    *   **Authentication:** Required (JWT Token in Authorization header)
    *   **Request Body:** None
    *   **Response Body:** A list of `LearningPathBasicInfo` objects.
        ```json
        [
          {
            "id": 1,
            "name": "Introduction to Python",
            "description": "Learn the fundamentals of Python programming.",
            "state": "published"
          },
          {
            "id": 5,
            "name": "Web Development Basics",
            "description": "HTML, CSS, and JavaScript essentials.",
            "state": "draft"
          }
          // ... other learning paths assigned to the user
        ]
        ```
    *   **Description:** Retrieves a simplified list containing only the `id`, `name`, `description`, and `state` for all learning paths currently assigned to the authenticated user. This is useful for displaying a quick overview or a dropdown list of the user's paths without fetching all the detailed course/section data.

*   **`DELETE /users/me/learning-paths/{path_id}`**
    *   **Method:** `DELETE`
    *   **Authentication:** Required (JWT Token in Authorization header)
    *   **Path Parameter:** `path_id` (integer) - The ID of the learning path to delete.
    *   **Request Body:** None
    *   **Success Response:** `204 No Content`
    *   **Error Responses:**
        *   `404 Not Found`: If the specified `path_id` does not correspond to a learning path assigned to the current user.
        *   `401 Unauthorized`: If the user is not authenticated.
        *   `500 Internal Server Error`: If an unexpected error occurs during deletion.
    *   **Description:** Allows the currently authenticated user to delete a learning path *that is assigned to them*. This attempts to remove the `LearningPath` record itself. Ensure database cascading is set up correctly if you want associated courses, sections, etc., to be deleted automatically. Otherwise, manual cleanup might be required.

**Notes for Frontend:**

*   Use `/users/me/learning-paths/basic` when you need to display a list of the user's assigned learning paths (e.g., in a sidebar or dropdown) without needing the full course structure immediately.
*   Use the standard `/users/me/learning-paths` or `/learning-paths/{path_id}` when you need the complete details of a specific learning path, including its courses and sections.
*   The generation endpoints (`/generate-course-titles`, `/generate-sections`, `/generate-learning-courses`) can be used sequentially or independently to build a learning path interactively.
*   Provide a confirmation dialog before calling the `DELETE /users/me/learning-paths/{path_id}` endpoint, as this action is destructive.
