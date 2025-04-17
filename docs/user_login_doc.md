Backend Authentication Documentation for Frontend
This document outlines how the frontend should interact with the backend API for user authentication, including standard email/password login and OAuth (Google/Microsoft) login.
1. Authentication Overview
The backend supports two primary methods for user authentication:
1. Email/Password Login: Users provide their email and password, and the backend returns a JWT (JSON Web Token) upon successful authentication.
OAuth 2.0 Login (Google & Microsoft): Users are redirected to the respective provider (Google or Microsoft) to authenticate. Upon successful authentication, the provider redirects back to the backend, which then generates a JWT and redirects the user back to a specified frontend URL with the token.
2. Handling the JWT Token
Both authentication methods result in the frontend receiving a JWT access_token.
Storage: The frontend should securely store this token (e.g., in localStorage or sessionStorage).
Usage: For all subsequent requests to protected API endpoints, the frontend must include the token in the Authorization header using the Bearer scheme:
  Authorization: Bearer <your_access_token>
Expiration: Tokens have an expiration time (default 30 minutes, see app/auth/jwt.py line 18). The frontend might need to handle token expiration, potentially by redirecting to login or implementing a refresh token mechanism (Note: Refresh tokens are not explicitly implemented in the provided backend code).
3. Email/Password Login
Endpoint: POST /api/token
Request Body: application/x-www-form-urlencoded (Form Data), not JSON.
username: The user's registered email address.
password: The user's password.
Success Response (200 OK):
Content-Type: application/json
Body:
        {
          "access_token": "string (JWT token)",
          "token_type": "bearer"
        }
Error Response (401 Unauthorized):
If credentials are incorrect.
Body:
        {
          "detail": "Incorrect username or password"
        }
Backend Implementation: app/auth/jwt.py (lines 88-111)
4. OAuth Login (Google & Microsoft)
This is a multi-step process involving redirects:
Step 1: Initiate OAuth Flow (Frontend -> Backend -> Provider)
The frontend provides "Login with Google" or "Login with Microsoft" buttons.
When a user clicks one of these buttons, the frontend redirects the user's browser to one of the following backend endpoints:
Google: GET /oauth/google
Microsoft: GET /oauth/microsoft
The backend will then redirect the user to the respective provider's authentication page.
Backend Implementation:
Google initiation: app/auth/oauth.py (lines 41-45)
Microsoft initiation: app/auth/oauth.py (lines 61-65)
Step 2: Handle Callback (Provider -> Backend -> Frontend)
After the user successfully authenticates with the provider (Google/Microsoft), the provider redirects the user back to a backend callback URL (e.g., /oauth/google/callback). The frontend does not call this callback URL directly.
The backend handles this callback, verifies the authentication, retrieves user information, creates a user account in the database if one doesn't exist (using email as the primary identifier, see app/auth/oauth.py lines 81-158), and generates a JWT access_token.
The backend then redirects the user back to the frontend to a specific URL, appending the JWT token as a query parameter.
Redirect URL Pattern: {FRONTEND_URL}/oauth/callback?token={access_token}
FRONTEND_URL is configured via environment variable on the backend (defaults to http://localhost:3000).
Frontend Action: The frontend needs a specific route (e.g., /oauth/callback) that:
Parses the token query parameter from the URL.
Stores the token securely (see Section 2).
Redirects the user to their dashboard or intended page.
Backend Implementation:
Google callback: app/auth/oauth.py (lines 47-59)
Microsoft callback: app/auth/oauth.py (lines 67-79)
5. Fetching Logged-In User Data
Once authenticated (token is stored), the frontend can fetch the current user's profile information.
Endpoint: GET /api/users/me
Authentication: Requires Authorization: Bearer <token> header.
Success Response (200 OK):
Content-Type: application/json
Body: UserResponse schema (defined in app/users/schemas.py lines 28-42). Example:
        {
          "email": "user@example.com",
          "username": "exampleuser",
          "full_name": "Example User",
          "profile_picture": "url_or_null",
          "interests": ["interest1", "interest2"], // Added based on schema
          "id": 123,
          "is_active": true,
          "oauth_provider": "google", // or "microsoft" or null
          "created_at": "iso_timestamp_string_or_null",
          "is_superuser": false
        }
Error Response (401 Unauthorized): If the token is missing, invalid, or expired.
Error Response (400 Bad Request): If the user associated with the token is marked as inactive (is_active: false). Detail: "Inactive user".
Backend Implementation: app/users/routes.py (lines 70-72), uses dependency get_current_active_user from app/auth/jwt.py (lines 83-86).
6. Logout
The backend doesn't have a specific /logout endpoint to invalidate JWTs (this is typical for simple JWT implementations). Logout should be handled purely on the frontend by:
Removing the stored JWT access_token.
Redirecting the user to the login page or public area.