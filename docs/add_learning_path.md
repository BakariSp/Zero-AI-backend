# Add Learning Path to My Collection API

## Overview

This API endpoint allows users to add a learning path to their personal collection by creating a clone of an existing learning path. 

This is particularly useful when users discover learning paths through recommendations and want to add them to their personal collection for learning.

## Endpoint Details

- **URL**: `/api/learning-paths/{path_id}/add-to-my-paths`
- **Method**: POST
- **Authentication**: Required (JWT token)
- **Parameters**:
  - `path_id` (path parameter): The ID of the learning path to add to your collection

## Functionality

When you call this endpoint, the backend will:

1. Create a complete clone of the specified learning path, including all its courses and sections
2. Associate this cloned copy with your user account
3. Return the new user-learning path association details

## Response Format

The endpoint returns a `UserLearningPathResponse` object containing:

```json
{
  "id": 123,                  // ID of the user-learning path association
  "user_id": 456,             // Your user ID
  "learning_path_id": 789,    // ID of the cloned learning path
  "progress": 0,              // Initial progress (0%)
  "start_date": "2023-07-15T00:00:00", // When you started the path
  "completed_at": null,       // Completion date (null if not completed)
  "created_at": "2023-07-15T00:00:00", // When the association was created
  "updated_at": "2023-07-15T00:00:00", // Last update timestamp
  "learning_path": {          // Full learning path details
    "id": 789,
    "name": "Path Name",
    "description": "Path Description",
    // ... other learning path properties
  }
}
```

## Error Handling

- **404 Not Found**: Returned if the specified learning path doesn't exist
- **500 Internal Server Error**: Returned for server-side errors with details in the response

## Usage Example

### Frontend Implementation (JavaScript)

```javascript
async function addLearningPathToMyCollection(pathId) {
  try {
    const response = await fetch(`/api/learning-paths/${pathId}/add-to-my-paths`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (!response.ok) {
      throw new Error(`Failed to add path: ${response.statusText}`);
    }
    
    const userPath = await response.json();
    return userPath;
  } catch (error) {
    console.error('Error adding learning path:', error);
    throw error;
  }
}
```

### React Example

```jsx
import { useState } from 'react';
import axios from 'axios';

function AddLearningPathButton({ pathId }) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleAddPath = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const token = localStorage.getItem('authToken'); // Get your auth token
      const response = await axios.post(
        `/api/learning-paths/${pathId}/add-to-my-paths`,
        {},  // No request body needed
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );
      
      // Handle successful addition
      console.log('Path added successfully:', response.data);
      
      // You might want to redirect or update UI here
      
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add learning path');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      <button 
        onClick={handleAddPath} 
        disabled={isLoading}
      >
        {isLoading ? 'Adding...' : 'Add to My Learning Paths'}
      </button>
      
      {error && <p className="error">{error}</p>}
    </div>
  );
}

export default AddLearningPathButton;
```

## Backend Implementation

On the backend, this endpoint:

1. Takes the `path_id` from the URL
2. Validates the user's authentication
3. Clones the learning path
4. Associates it with the user
5. Returns the user-learning path association

The main backend function responsible for this is `clone_learning_path_for_user`, which handles the creation of the clone and the association.
