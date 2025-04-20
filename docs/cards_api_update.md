# Card API Endpoints

This document outlines the key API endpoints for retrieving and managing cards, including how to fetch cards associated with specific sections and generate new cards using AI.

**Base Path:** `/api` (Assumed prefix for all endpoints below)

---

## Fetching Cards

### 1. Fetch Section with its Cards

Retrieves details for a specific section, including the list of cards directly associated with it. This is the **recommended** way to get all cards belonging to a known section.

*   **Method:** `GET`
*   **Path:** `/sections/{section_id}`
*   **Description:** Retrieves a single course section object by its ID, populated with its associated cards.
*   **Path Parameters:**
    *   `section_id` (int): The ID of the section to retrieve.
*   **Request Body:** None
*   **Response Body:** `SectionResponse` (Includes a list of `CardResponse` objects)
    ```json
    {
      "id": 123,
      "title": "Introduction to Python Basics",
      "description": "Covers fundamental Python concepts.",
      "order_index": 0,
      "cards": [
        {
          "id": 10,
          "keyword": "Python Variables",
          "question": "How do you declare a variable in Python?",
          "answer": "variable_name = value",
          "explanation": "Assign a value to a name.",
          "resources": [],
          "level": "beginner",
          "tags": ["python", "basics"],
          "created_at": "2023-10-27T10:00:00Z",
          "updated_at": "2023-10-27T10:00:00Z",
          "difficulty": "beginner"
        },
        // ... other cards in the section
      ],
      "learning_path_id": 1,
      "created_at": "2023-10-26T09:00:00Z",
      "updated_at": "2023-10-26T09:00:00Z"
    }
    ```
*   **Relevant Code:**
    *   Route Definition: `app/sections/routes.py` (startLine: 50, endLine: 60)
    *   Response Schema: `app/sections/schemas.py` (startLine: 43, endLine: 54)
    *   Card Schema: `app/cards/schemas.py` (startLine: 37, endLine: 53)

### 2. Fetch Cards (General Query with Section Filter)

Retrieves a list of cards, optionally filtered by various criteria, including the section they belong to. Useful for searching cards across sections or when `section_id` is just one filter among others.

*   **Method:** `GET`
*   **Path:** `/cards`
*   **Description:** Get a list of cards with optional filtering and pagination. Can filter by the section ID.
*   **Query Parameters:**
    *   `skip` (int, optional, default: 0): Number of cards to skip for pagination.
    *   `limit` (int, optional, default: 100): Maximum number of cards to return.
    *   `keyword` (str, optional): Filter cards by keyword (partial match).
    *   `section_id` (int, optional): Filter cards belonging to a specific section.
*   **Request Body:** None
*   **Response Body:** `List[CardResponse]`
    ```json
    [
      {
        "id": 10,
        "keyword": "Python Variables",
        "question": "How do you declare a variable in Python?",
        "answer": "variable_name = value",
        "explanation": "Assign a value to a name.",
        "resources": [],
        "level": "beginner",
        "tags": ["python", "basics"],
        "created_at": "2023-10-27T10:00:00Z",
        "updated_at": "2023-10-27T10:00:00Z",
        "difficulty": "beginner"
      },
      // ... other cards matching filters
    ]
    ```
*   **Relevant Code:**
    *   Route Definition: `app/cards/routes.py` (startLine: 45, endLine: 63)
    *   CRUD Logic: `app/cards/crud.py` (startLine: 24, endLine: 39)
    *   Response Schema: `app/cards/schemas.py` (startLine: 37, endLine: 53)

### 3. Fetch Single Card

Retrieves a single card by its unique ID.

*   **Method:** `GET`
*   **Path:** `/cards/{card_id}`
*   **Description:** Retrieves a single card object by its ID.
*   **Path Parameters:**
    *   `card_id` (int): The ID of the card to retrieve.
*   **Request Body:** None
*   **Response Body:** `CardResponse` (See schema example above)
*   **Relevant Code:**
    *   Route Definition: `app/cards/routes.py` (startLine: 65, endLine: 77)

---

## Generating & Managing Cards

### 1. Generate Single Card (AI)

Generates a new card using AI based on a keyword. If a `section_id` is provided in the request, the generated card (or an existing card with the same keyword found in the database) will be linked to that section.

*   **Method:** `POST`
*   **Path:** `/generate-card`
*   **Description:** Uses the configured AI model (`CardGeneratorAgent`) to generate card content (question, answer, explanation, difficulty) based on the provided keyword and optional context. Links to a section if `section_id` is given.
*   **Request Body:** `GenerateCardRequest`
    ```json
    {
      "keyword": "Python Lists",
      "context": "Explain how to create and access elements in Python lists.",
      "section_id": 123 // Optional: ID of the section to link this card to
    }
    ```
*   **Response Body:** `CardResponse` (The created or linked card)
*   **Relevant Code:**
    *   Route Definition: `app/cards/routes.py` (startLine: 191, endLine: 246)
    *   Request Schema: `app/cards/schemas.py` (startLine: 79, endLine: 82)
    *   AI Agent Logic: `app/services/ai_generator.py` (startLine: 599, endLine: 700)
    *   CRUD Logic (handles linking): `app/cards/crud.py` (startLine: 42, endLine: 76)

### 2. Generate Multiple Cards for Section (AI)

Generates multiple cards using AI based on the section's title and saves/links them to that section.

*   **Method:** `POST`
*   **Path:** `/sections/{section_id}/generate-cards`
*   **Description:** Generates a specified number of cards using the AI model based on the section's title and difficulty. The generated cards are saved to the database (or existing ones are linked) and associated with the specified section.
*   **Path Parameters:**
    *   `section_id` (int): The ID of the section to generate cards for.
*   **Query Parameters:**
    *   `num_cards` (int, optional, default: 5, min: 1, max: 10): Number of cards to generate.
    *   `difficulty` (str, optional): Overrides the section's default difficulty for generation.
*   **Request Body:** None
*   **Response Body:**
    ```json
    {
      "message": "Generated and linked 5 cards for section 123",
      "card_ids": [ 15, 16, 17, 18, 19 ]
    }
    ```
*   **Relevant Code:**
    *   Route Definition: `app/sections/routes.py` (startLine: 200, endLine: 245)
    *   AI Agent Logic: `app/services/ai_generator.py` (startLine: 599, endLine: 700)
    *   Card Creation CRUD: `app/cards/crud.py` (startLine: 42, endLine: 76)
    *   Section Card Linking CRUD: `app/sections/crud.py` (startLine: 160, endLine: 196)

### 3. Create Card Manually (Admin)

Allows an administrator to create a card directly by providing all its details.

*   **Method:** `POST`
*   **Path:** `/cards`
*   **Description:** Creates a new card entry in the database. Requires admin privileges.
*   **Request Body:** `CardCreate` (`app/cards/schemas.py`, startLine: 18, endLine: 23)
*   **Response Body:** `CardResponse`
*   **Relevant Code:**
    *   Route Definition: `app/cards/routes.py` (startLine: 79, endLine: 92)

*(Other endpoints like Update, Delete, User Save/Unsave exist but are omitted here for brevity as the focus was on fetching by section and generation)*

---