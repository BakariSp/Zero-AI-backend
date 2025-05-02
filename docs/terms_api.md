# Terms of Service API Documentation

This document describes the API endpoints available for managing user acceptance of terms and conditions.

## Overview

The Terms of Service API allows you to:
1. Record when a user accepts the terms of service
2. Check if a user has accepted a specific version of terms
3. Retrieve the user's history of terms acceptances

## Base URL

All API endpoints are relative to your backend's base URL, typically:
- Development: `http://localhost:8000`
- Production: `https://api.yourdomain.com`

## Authentication

All endpoints require authentication. Include a valid JWT token in the Authorization header:

```
Authorization: Bearer {your_access_token}
```

## Endpoints

### Record Terms Acceptance

Record that a user has accepted a specific version of the terms of service.

**URL**: `/users/terms/accept`  
**Method**: `POST`  
**Authentication**: Required

**Request Body**:

```json
{
  "terms_version": "v1.0",
  "ip_address": "192.0.2.1"  // Optional, will be auto-detected if not provided
}
```

**Response** (201 Created):

```json
{
  "id": 1,
  "user_id": 123,
  "terms_version": "v1.0",
  "signed_at": "2025-05-01T12:34:56.789Z",
  "ip_address": "192.0.2.1"
}
```

### Check Terms Acceptance Status

Check if a user has accepted a specific version of the terms.

**URL**: `/users/terms/status/{terms_version}`  
**Method**: `GET`  
**Authentication**: Required

**Parameters**:
- `terms_version`: The version of terms to check (e.g., "v1.0")

**Response** (200 OK):

```json
{
  "user_id": 123,
  "terms_version": "v1.0",
  "has_accepted": true
}
```

### Get Terms Acceptance History

Retrieve the history of all terms acceptances for the current user.

**URL**: `/users/terms/history`  
**Method**: `GET`  
**Authentication**: Required

**Query Parameters**:
- `skip`: Number of records to skip (default: 0)
- `limit`: Maximum number of records to return (default: 100)

**Response** (200 OK):

```json
[
  {
    "id": 1,
    "user_id": 123,
    "terms_version": "v1.0",
    "signed_at": "2025-05-01T12:34:56.789Z",
    "ip_address": "192.0.2.1"
  },
  {
    "id": 2,
    "user_id": 123,
    "terms_version": "v1.1",
    "signed_at": "2025-06-15T10:22:33.456Z",
    "ip_address": "192.0.2.1"
  }
]
```

## Implementation Guide for Frontend

### Recording User Acceptance

When a user clicks "Accept" on your terms of service dialog:

```javascript
async function acceptTerms() {
  try {
    const response = await fetch('/users/terms/accept', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${userToken}`
      },
      body: JSON.stringify({
        terms_version: 'v1.0'
        // ip_address is optional and will be auto-detected by the server
      })
    });
    
    if (response.ok) {
      // Terms acceptance was recorded successfully
      // Proceed with user flow, e.g., redirect to dashboard
    } else {
      // Handle error
      console.error('Failed to record terms acceptance');
    }
  } catch (error) {
    console.error('Error:', error);
  }
}
```

### Checking if User Has Accepted Terms

Use this to determine if you need to show the terms dialog to a user:

```javascript
async function checkTermsAcceptance(version = 'v1.0') {
  try {
    const response = await fetch(`/users/terms/status/${version}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${userToken}`
      }
    });
    
    const data = await response.json();
    
    if (data.has_accepted) {
      // User has already accepted this version, proceed with normal flow
      return true;
    } else {
      // User needs to accept terms, show the terms dialog
      showTermsDialog();
      return false;
    }
  } catch (error) {
    console.error('Error checking terms acceptance:', error);
    return false;
  }
}
```

### OAuth Users

For users who sign in through OAuth providers (Google, Microsoft), terms are automatically accepted on their behalf. This ensures all users are covered by the terms of service, even if they skip the standard registration flow.

The system:
1. Records acceptance with the user's IP address when available
2. Uses the current terms version (currently set to "v1.0")
3. Only records this once per terms version per user

This behavior is implemented using the `auto_accept_terms_for_oauth_user` function from the `app/users/crud.py` module, which is called during the OAuth authentication flow. The implementation can be customized by modifying the `oauth_terms_patch.py` script and running it again.

## Best Practices

1. **Version Format**: Use semantic versioning (e.g., "v1.0", "v1.1") for your terms versions.
2. **Check on Important Actions**: Check for terms acceptance whenever a user performs important actions or signs in.
3. **Store Terms Content**: Although not tracked by this API, make sure you store the actual content of each terms version separately for audit purposes.
4. **Re-acceptance**: When terms are updated, prompt the user to accept the new version.
5. **OAuth Users**: Be aware that OAuth users automatically accept terms upon login - consider displaying a notice about this during their first session.

## Error Handling

The API returns standard HTTP status codes:

- `200 OK`: The request was successful
- `201 Created`: The resource was successfully created
- `400 Bad Request`: The request was malformed or invalid
- `401 Unauthorized`: Authentication is required or token is invalid
- `403 Forbidden`: The authenticated user doesn't have permission
- `404 Not Found`: The requested resource doesn't exist
- `500 Internal Server Error`: An unexpected error occurred on the server

## Data Model

The `UserTermsAcceptance` model includes:

- `id`: Unique identifier for the acceptance record
- `user_id`: ID of the user who accepted the terms
- `terms_version`: Version of the terms that was accepted (e.g., "v1.0")
- `signed_at`: Timestamp when the user accepted the terms
- `ip_address`: IP address from which the user accepted the terms (for audit purposes)

## Administration

For administrative purposes, the system includes two utility scripts:

1. **accept_terms_for_users.py**: Allows administrators to manually accept terms for all users or specific users:
   ```bash
   # Accept terms for all users
   python accept_terms_for_users.py --all
   
   # Accept terms for a specific user
   python accept_terms_for_users.py --email user@example.com
   ```

2. **oauth_terms_patch.py**: Patches the OAuth authentication flow to automatically accept terms for OAuth users:
   ```bash
   # Apply the patch
   python oauth_terms_patch.py
   ```
