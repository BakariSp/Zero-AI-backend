# Learning Assistant API Documentation

The Learning Assistant provides intelligent support for users while they're studying cards. It can answer questions about the current content, generate related cards, and add these cards to the user's study sections.

## API Endpoints

### 1. Ask a Question

`POST /api/learning-assistant/ask`

This endpoint allows users to ask questions about cards they're studying. The assistant will provide an answer and also suggest a related card.

#### Request

```json
{
  "query": "What is the difference between inheritance and polymorphism?",
  "card_id": 123,            // Optional: ID of the current card being viewed
  "section_id": 456,         // Optional: ID of the current section
  "difficulty_level": "intermediate" // Optional: Defaults to "intermediate"
}
```

#### Response

```json
{
  "answer": "Inheritance is a mechanism where a new class inherits properties and behaviors from an existing class. Polymorphism is the ability to present the same interface for different underlying data types. In object-oriented programming, inheritance helps with code reuse, while polymorphism helps with flexibility.",
  "related_card": {
    "keyword": "Method Overriding",
    "question": "What is method overriding in OOP?",
    "answer": "Method overriding is a feature that allows a subclass to provide a specific implementation of a method that is already defined in its parent class.",
    "explanation": "Method overriding is a key aspect of polymorphism. It enables a subclass to offer a different implementation of a method that's already defined in its parent class, allowing objects of different classes to respond differently to the same method call.",
    "difficulty": "intermediate",
    "resources": [
      {
        "url": "https://example.com/method-overriding",
        "title": "Method Overriding in Java"
      }
    ]
  },
  "context": {
    "current_card_id": 123,
    "section_id": 456,
    "section_title": "Object-Oriented Programming Concepts",
    "course_title": "Java Programming"
  },
  "status": {
    "success": true,
    "has_related_card": true
  }
}
```

### 2. Add a Related Card to a Section

`POST /api/learning-assistant/add-card`

This endpoint allows users to add a generated related card to their study section.

#### Request

```json
{
  "card_data": {
    "keyword": "Method Overriding",
    "question": "What is method overriding in OOP?",
    "answer": "Method overriding is a feature that allows a subclass to provide a specific implementation of a method that is already defined in its parent class.",
    "explanation": "Method overriding is a key aspect of polymorphism. It enables a subclass to offer a different implementation of a method that's already defined in its parent class, allowing objects of different classes to respond differently to the same method call.",
    "difficulty": "intermediate",
    "resources": [
      {
        "url": "https://example.com/method-overriding",
        "title": "Method Overriding in Java"
      }
    ]
  },
  "section_id": 456
}
```

#### Response

```json
{
  "card": {
    "id": 789, // The newly created card ID
    "keyword": "Method Overriding",
    "question": "What is method overriding in OOP?",
    "answer": "Method overriding is a feature that allows a subclass to provide a specific implementation of a method that is already defined in its parent class.",
    "explanation": "Method overriding is a key aspect of polymorphism. It enables a subclass to offer a different implementation of a method that's already defined in its parent class, allowing objects of different classes to respond differently to the same method call.",
    "difficulty": "intermediate",
    "section_id": 456
  },
  "status": {
    "success": true,
    "message": "Card successfully added to section 'Object-Oriented Programming Concepts'"
  }
}
```

### 3. Generate Multiple Cards for a Topic

`POST /api/learning-assistant/generate-cards`

This endpoint generates multiple cards related to a specific topic or concept.

#### Request

```json
{
  "topic": "Data Structures",
  "num_cards": 3,                   // Optional: Number of cards to generate (default: 3)
  "section_id": 456,                // Optional: Section ID for context
  "course_title": "Computer Science Fundamentals", // Optional: Course title for context
  "difficulty_level": "intermediate" // Optional: Difficulty level (default: "intermediate")
}
```

#### Response

```json
[
  {
    "keyword": "Array",
    "question": "What is an array in data structures?",
    "answer": "An array is a linear data structure that collects elements of the same data type and stores them in contiguous memory locations.",
    "explanation": "Arrays provide random access to elements via indices, making them efficient for operations where the index is known, but less efficient for insertions and deletions.",
    "difficulty": "intermediate",
    "resources": [
      {
        "url": "https://example.com/arrays",
        "title": "Understanding Arrays"
      }
    ]
  },
  {
    "keyword": "Linked List",
    "question": "What is a linked list in data structures?",
    "answer": "A linked list is a linear data structure where elements are stored in nodes that point to the next node in the sequence.",
    "explanation": "Unlike arrays, linked lists don't require contiguous memory allocation. They excel at insertions and deletions but have slower random access time.",
    "difficulty": "intermediate",
    "resources": [
      {
        "url": "https://example.com/linked-lists",
        "title": "Introduction to Linked Lists"
      }
    ]
  },
  {
    "keyword": "Hash Table",
    "question": "What is a hash table in data structures?",
    "answer": "A hash table is a data structure that maps keys to values using a hash function that computes an index into an array of buckets.",
    "explanation": "Hash tables provide fast insertion, deletion, and lookup operations (average O(1) time complexity), making them ideal for implementing dictionaries, caches, and database indexes.",
    "difficulty": "intermediate",
    "resources": [
      {
        "url": "https://example.com/hash-tables",
        "title": "Hash Tables Explained"
      }
    ]
  }
]
```

### 4. Managing Generated Cards

The Learning Assistant creates cards that are stored in the database. There are two ways to manage these cards:

#### Unsaving Cards (Regular Users)

If a user wants to remove a card from their saved collection:

`DELETE /api/cards/users/me/cards/{card_id}`

This endpoint removes the association between the user and the card, but the card remains in the system for other users.

**Request:** No body required

**Response:**
```json
{
  "detail": "Card removed successfully"
}
```

#### Deleting Cards (Admin Only)

Administrators can completely delete a card from the system, including all its relationships:

`DELETE /api/cards/{card_id}`

This removes the card and all its associations from the database. This is permanent and affects all users.

**Request:** No body required

**Response:**
```json
{
  "detail": "Card deleted successfully"
}
```

**Note:** This endpoint is restricted to superusers only. Regular users cannot completely delete cards from the system.

## Technical Implementation Details

### AI Integration

The Learning Assistant uses OpenAI-compatible models (e.g., Azure OpenAI Service) to generate responses and cards. The backend includes:

1. **LearningAssistantService** - The main service that handles:
   - Processing user questions with context
   - Adding generated cards to sections
   - Generating multiple cards for topics

2. **LearningAssistantAgent** - The underlying AI agent that:
   - Formats prompts with context information
   - Makes API calls to the language model
   - Parses and validates the responses

### Performance Considerations

#### Caching

The service implements response caching to improve performance and reduce API costs:

- Responses for the same question within the same context are cached
- Each cache entry includes a version number to invalidate when prompts change
- Card generation also uses caching based on topic and parameters
- Frontend developers should expect occasional instant responses due to cache hits

#### Response Times

- **First-time responses**: ~3-6 seconds (requires API call to language model)
- **Cached responses**: ~50-200ms (retrieved from memory/database)

For optimal user experience:

1. Implement loading states for all AI-dependent requests
2. Consider pre-loading common questions if your app has predictable usage patterns
3. If implementing your own caching layer, be aware of the backend's existing cache

### Error Handling

The backend implements robust error handling:

- For AI service failures, default fallback responses are provided instead of errors
- JSON parsing errors are handled with fallback card structures
- Rate limiting may occur if many requests are made in quick succession

Frontend applications should handle these cases:

1. AI service unavailable (backend will return a friendly error message)
2. Rate limiting (implement retry with exponential backoff)
3. Malformed responses (unlikely but possible)

## Integration Guide for Frontend

### Recommended Workflow

1. **Studying Flow:**
   - When a user is viewing a flashcard and has a question, they can use the "Ask" endpoint to get a detailed answer.
   - The response will include both a direct answer and a related card that expands on the topic.
   - Display both the answer and the related card, with an option to add the related card to their current section.

2. **Adding Cards:**
   - If the user wants to add the related card to their study materials, use the "Add Card" endpoint.
   - Pass the entire card data object from the previous response along with the desired section ID.
   - Confirm to the user when the card has been successfully added.

3. **Generating Topic Cards:**
   - For more exploratory learning, users can generate multiple cards on a specific topic.
   - Use the "Generate Cards" endpoint with the topic of interest.
   - Display the generated cards with options to add them to sections.

4. **Managing Cards:**
   - When a user no longer wants a card in their collection, they can remove it using the unsave endpoint.
   - For admin users, provide an option to completely delete problematic cards from the system.
   - Always confirm card deletion actions with users to prevent accidental data loss.

### Authentication Notes

- All Learning Assistant endpoints support optional authentication.
- If the user is logged in, include their authentication token in the Authorization header.
- If no token is provided, the endpoints will still function, but user-specific features (like tracking who added a card) will be limited.
- Card deletion endpoints require authentication:
  - The unsave endpoint requires a regular user token
  - The delete endpoint requires a superuser token

### UI/UX Recommendations

1. **Question Interface:**
   - Provide a prominent text input for questions
   - Include a "context" indicator showing what card/section the user is currently viewing
   - Support voice input for questions if possible

2. **Answer Display:**
   - Format the answer with proper headings, paragraphs, and bullet points
   - Highlight key terms or concepts
   - Show the related card in a separate panel or card view

3. **Card Management:**
   - Allow one-click addition of related cards
   - Provide confirmation when a card is added
   - Show visual feedback when generating multiple cards (progress indicator)
   - Include an "Unsave" or "Remove" option for saved cards
   - For admin interfaces, add a "Delete" option with appropriate warnings

### Error Handling

- Always check the `status.success` field in responses to determine if the operation was successful.
- If an error occurs, display the error message to the user and provide an option to retry the operation.
- For network errors, implement a retry mechanism with exponential backoff.

### Performance Considerations

- Responses may take a few seconds, especially for card generation, so implement loading states.
- Consider caching responses where appropriate to improve responsiveness.
- For sections with many cards, fetch cards on demand rather than all at once.

## Examples

### Example 1: Asking a question about a card

```javascript
// Example using fetch
async function askQuestion(question, cardId, sectionId) {
  const response = await fetch('/api/learning-assistant/ask', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + userToken // Optional
    },
    body: JSON.stringify({
      query: question,
      card_id: cardId,
      section_id: sectionId
    })
  });
  
  const data = await response.json();
  
  if (data.status.success) {
    // Display answer to the user
    displayAnswer(data.answer);
    
    // Display the related card with an option to add it
    if (data.status.has_related_card) {
      displayRelatedCard(data.related_card, data.context.section_id);
    }
  } else {
    // Handle error
    displayError(data.status.error_message);
  }
}
```

### Example 2: Adding a card to a section

```javascript
// Example using fetch
async function addCardToSection(cardData, sectionId) {
  const response = await fetch('/api/learning-assistant/add-card', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + userToken // Optional
    },
    body: JSON.stringify({
      card_data: cardData,
      section_id: sectionId
    })
  });
  
  const data = await response.json();
  
  if (data.status.success) {
    // Notify user of success
    showNotification(`Card "${data.card.keyword}" added to section!`);
    
    // Optionally refresh the section's card list
    refreshSectionCards(sectionId);
  } else {
    // Handle error
    displayError(data.status.error_message);
  }
}
```

### Example 3: Removing a card from user's saved collection

```javascript
// Example using fetch
async function unsaveCard(cardId) {
  const response = await fetch(`/api/cards/users/me/cards/${cardId}`, {
    method: 'DELETE',
    headers: {
      'Authorization': 'Bearer ' + userToken // Required
    }
  });
  
  if (response.ok) {
    // Notify user of success
    showNotification('Card removed from your collection');
    
    // Refresh the user's card list
    refreshUserCards();
  } else {
    // Handle error
    const errorData = await response.json();
    displayError(errorData.detail || 'Failed to remove card');
  }
}
```

### Example 4: Deleting a card from the system (Admin only)

```javascript
// Example using fetch
async function deleteCard(cardId) {
  // Show confirmation dialog first
  if (!confirm('Are you sure you want to permanently delete this card? This will affect all users.')) {
    return;
  }
  
  const response = await fetch(`/api/cards/${cardId}`, {
    method: 'DELETE',
    headers: {
      'Authorization': 'Bearer ' + adminToken // Requires admin token
    }
  });
  
  if (response.ok) {
    // Notify admin of success
    showNotification('Card permanently deleted from the system');
    
    // Refresh the card list
    refreshCardsList();
  } else {
    // Handle error
    const errorData = await response.json();
    displayError(errorData.detail || 'Failed to delete card');
  }
}
```
