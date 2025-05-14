# API Endpoints Update Documentation

## New User-Specific Endpoints with Progress Information

We've added several user-specific endpoints that return personalized data including progress information. These endpoints provide a more efficient way to access user-specific content without requiring additional client-side processing.

### Learning Paths API Updates

#### New Endpoint: Get User-Specific Learning Path

```
GET /users/me/learning-paths/{path_id}
```

**Response:** User-specific learning path data with progress information.

**Benefits:**
- Includes user's progress for the specific learning path
- Contains personalized data like completion status and start date
- Returns detailed information about the learning path structure

**Migration from existing endpoints:**

| Old Endpoint | New Endpoint | Benefits |
|--------------|--------------|----------|
| `GET /learning-paths/{path_id}` | `GET /users/me/learning-paths/{path_id}` | Includes progress information and user-specific data |

### Example Response

```json
{
  "id": 123,
  "user_id": 456,
  "learning_path_id": 789,
  "progress": 65.5,
  "start_date": "2023-08-15T10:00:00Z",
  "completed_at": null,
  "learning_path": {
    "id": 789,
    "title": "Advanced Machine Learning",
    "description": "Learn advanced ML techniques",
    "category": "AI & Machine Learning",
    "difficulty_level": "advanced",
    "estimated_days": 30,
    "sections": [...],
    "courses": [...]
  }
}
```

### Similar User-Specific Endpoints

We have implemented similar user-specific endpoints for other resources:

1. **Courses**: `GET /users/me/courses/{course_id}` - Returns user's course with progress
2. **Sections**: `GET /users/me/sections/{section_id}` - Returns user's section with progress
3. **Cards**: `GET /users/me/cards/{card_id}` - Returns user's saved card with completion status

### Implementation Notes for Frontend Developers

To get the most out of these endpoints:

1. When displaying a specific learning path page, use the new endpoint to get both the learning path content and user progress in a single request.
2. The user-specific endpoints should be used whenever you need to display user progress or completion status.
3. For public content display (not requiring user data), you can continue using the original endpoints.

### Migration Timeline

These new endpoints are available immediately and we recommend migrating to them for improved performance and user experience. The old endpoints will continue to function, but future enhancements will prioritize the user-specific endpoints. 