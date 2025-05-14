# Learning Paths

## Overview

Learning paths are a collection of courses that are designed to help users learn a specific topic.

## API Endpoints

### Getting Learning Path Details

#### Basic Path Information

To get basic information about a learning path, use:

```
GET /api/users/me/learning-paths/{path_id}
```

This returns the learning path with basic course information.

#### Full Path Information

For complete learning path details including all courses, sections, cards, and user progress information, use:

```
GET /api/users/me/learning-paths/{path_id}/full
```

This endpoint returns the complete structure of a learning path including:

- All courses within the learning path
- All sections within each course 
- All cards within each section
- Progress information for courses and sections
- Completion status for individual cards

Frontend applications should use this endpoint when displaying the detailed view of a learning path, including all its nested content and personalized progress information.

Example response format:
```json
{
  "id": 244,
  "title": "Intermediate 3-Week Fitness Plan",
  "description": "Custom learning path based on user structure",
  "category": "Strength Training Fundamentals",
  "difficulty_level": "Intermediate",
  "estimated_days": 30,
  "is_template": false,
  "created_at": "2025-05-06T03:17:13",
  "updated_at": "2025-05-06T03:17:13",
  "courses": [
    {
      "id": 670,
      "title": "Strength Training Fundamentals",
      "description": "Course within fitness plan path",
      "estimated_days": 7,
      "progress": 0.0,
      "completed_at": null,
      "sections": [
        {
          "id": 2032,
          "title": "Core Stability and Activation",
          "description": "Section within course",
          "progress": 0.0,
          "cards": [
            {
              "id": 5724,
              "keyword": "Core Activation",
              "is_completed": true
            },
            // ... more cards
          ]
        },
        // ... more sections
      ]
    },
    // ... more courses
  ]
}
```

Note: This endpoint returns user-specific information such as progress and completion status, so it requires authentication.

