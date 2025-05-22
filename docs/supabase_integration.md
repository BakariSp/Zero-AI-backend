# Supabase Authentication Integration

This document outlines how to set up and configure Supabase authentication for the Zero AI backend application.

## Overview

The Zero AI backend now supports authentication through Supabase, while maintaining backward compatibility with the existing JWT authentication system. This allows for a smooth transition to Supabase Auth.

## Setup Steps

### 1. Create a Supabase Project

1. Sign up for a Supabase account at [https://supabase.com/](https://supabase.com/)
2. Create a new project
3. Note your project's URL and API keys (public anon key and service_role key)

### 2. Configure Environment Variables

Add the following environment variables to your `.env` file or deployment environment:

```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_SERVICE_KEY=your-supabase-service-role-key
```

### 3. Configure Supabase Authentication Settings

In the Supabase dashboard:

1. Go to **Authentication** → **Settings**
2. Under **Email Auth**, enable "Enable Email Signup" 
3. Configure email templates if desired
4. Set up site URL and redirect URLs for your frontend application

### 4. Frontend Integration

Update your frontend to use Supabase Auth. Here's a basic example using the Supabase JavaScript client:

```javascript
import { createClient } from '@supabase/supabase-js'

// Initialize the Supabase client
const supabaseUrl = 'https://your-project-id.supabase.co'
const supabaseKey = 'your-supabase-anon-key'
const supabase = createClient(supabaseUrl, supabaseKey)

// Sign up
async function signUp(email, password) {
  const { user, error } = await supabase.auth.signUp({
    email,
    password,
  })
  
  if (error) {
    console.error('Error signing up:', error)
    return null
  }
  
  return user
}

// Sign in
async function signIn(email, password) {
  const { user, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  })
  
  if (error) {
    console.error('Error signing in:', error)
    return null
  }
  
  return user
}

// Sign out
async function signOut() {
  const { error } = await supabase.auth.signOut()
  
  if (error) {
    console.error('Error signing out:', error)
  }
}
```

### 5. Backend Integration

The backend has been updated to support Supabase authentication. The integration includes:

1. A `SupabaseAuthMiddleware` that extracts and verifies Supabase JWT tokens
2. A unified authentication system that works with both Supabase and the existing JWT system
3. User synchronization between Supabase Auth and the application's user database

## How It Works

1. When a user authenticates with Supabase from the frontend, Supabase issues a JWT token
2. This token is sent in the `Authorization` header with requests to the backend
3. The `SupabaseAuthMiddleware` extracts and verifies this token
4. If valid, the user information is retrieved or created in the application's database
5. The user is then available for authorization in protected routes

## User Data Synchronization

The system automatically synchronizes user data between Supabase Auth and the application's database:

1. When a user authenticates with Supabase for the first time, a corresponding user record is created in the application database
2. If a user already exists in the application database (based on email), their record is updated with Supabase authentication information
3. User profile data like name and profile picture is synced between Supabase and the application database

## Database Schema

The existing `users` table is maintained, with the following fields used for Supabase integration:

- `oauth_provider`: Set to "supabase" for Supabase-authenticated users
- `oauth_id`: Stores the Supabase user ID
- `email`: Used to match users between Supabase and the application database
- `profile_picture`: Can be synced with Supabase user avatar URL

## Testing Authentication

To test the Supabase authentication:

1. Set up the environment variables as described above
2. Implement Supabase authentication in your frontend
3. Send requests to protected endpoints with the Supabase JWT token in the Authorization header
4. The backend will automatically create or update user records as needed

## Fallback to Existing JWT

For backward compatibility, the existing JWT authentication system is still supported. If a request doesn't have a valid Supabase token but has a valid JWT token, the user will still be authenticated.

## Troubleshooting

### Common Issues

1. **Authentication fails with 401 Unauthorized**
   - Verify that the Supabase token is being sent in the Authorization header
   - Check that the token is not expired
   - Ensure that the Supabase URL and key in the environment variables are correct

2. **User created in Supabase but not in the application database**
   - Check the application logs for errors during user creation
   - Verify that the user has a valid email address
   - Ensure the database connection is working properly

3. **Missing Supabase credentials**
   - Make sure SUPABASE_URL and SUPABASE_KEY are set in your environment
   - Restart the application after setting these variables

### Debugging

The application includes several debugging aids:

1. Detailed logging of authentication processes
2. The `/api/auth/debug` endpoint which provides information about the current authentication state
3. The Supabase client utility for directly interacting with Supabase APIs

## Next Steps

1. Implement social authentication providers in Supabase (Google, Microsoft, GitHub, etc.)
2. Set up email verification if required
3. Configure password reset flow
4. Consider implementing row-level security in Supabase for direct database access from the frontend 