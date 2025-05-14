# Backend Integration: Supporting Local Frontend Development with Remote API

## Overview

This document outlines the changes needed on the backend to support local frontend development while using the production/staging backend API. This allows developers to:

1. Debug frontend code locally
2. Connect to the actual production/staging backend 
3. Prevent unwanted redirects to the production frontend

## The Problem

Currently, when using the production API URL `https://zero-ai-d9e8f5hgczgremge.westus-01.azurewebsites.net` for local development, the backend redirects authentication and other requests to the production frontend URL. This makes local debugging impossible.

## The Solution

The frontend has been updated to include a special HTTP header `X-Force-Local-Frontend: true` when it is running in local development mode but connecting to a remote backend. The backend should check for this header and:

1. Skip any redirects to the production frontend URL
2. Return responses that would work in a local development environment

## Required Backend Changes

### 1. Authentication Flow Updates

Update the authentication middleware/controllers to check for the `X-Force-Local-Frontend` header:

```python
# Example in FastAPI
from fastapi import Request, Depends

async def auth_middleware(request: Request):
    # Check if this is a local frontend development request
    force_local_frontend = request.headers.get("X-Force-Local-Frontend") == "true"
    
    # Store this in request state for use in other parts of the application
    request.state.force_local_frontend = force_local_frontend
    
    # Rest of authentication logic...
    # ...

    # When deciding on redirects:
    if needs_redirect and not force_local_frontend:
        # Only redirect to production frontend if not in local development mode
        return RedirectResponse(url=f"{PRODUCTION_FRONTEND_URL}/login")
    
    # Otherwise, return the response as-is for local development
    return response
```

### 2. Response URL Handling

Anywhere the backend generates absolute URLs (like in API responses), check for the header:

```python
def get_frontend_base_url(request: Request) -> str:
    """Determine the correct frontend base URL to use in responses."""
    if request.state.force_local_frontend:
        # For local development - don't use absolute URLs or use localhost
        # Option 1: Return relative URL
        return ""
        
        # Option 2: Return localhost URL
        # return "http://localhost:3000"
    else:
        # For production
        return PRODUCTION_FRONTEND_URL
```

### 3. CORS Configuration

Ensure CORS is properly configured to allow requests from the local development server:

```python
# Example in FastAPI
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local Next.js frontend
        PRODUCTION_FRONTEND_URL,  # Production frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 4. OAuth / SSO Callback URLs

If using OAuth or SSO, make sure callback URLs can be directed to the local frontend:

```python
@app.get("/api/auth/callback/{provider}")
async def auth_callback(request: Request, provider: str):
    # Authentication logic...
    # ...
    
    # Determine where to redirect after successful authentication
    if request.state.force_local_frontend:
        # Get the current language from request or default to 'en'
        lang = request.headers.get("Accept-Language", "en").split(",")[0].split("-")[0]
        redirect_url = f"http://localhost:3000/{lang}/dashboard"
    else:
        redirect_url = f"{PRODUCTION_FRONTEND_URL}/dashboard"
    
    return RedirectResponse(url=redirect_url)
```

## Testing the Integration

To verify that the backend is correctly respecting the `X-Force-Local-Frontend` header:

1. Start the frontend with the remote API configuration:
   ```bash
   npm run dev:remote-api
   ```

2. Make requests to the backend and check that:
   - No redirects to production frontend occur
   - Authentication flows work properly
   - All API responses are properly formatted for local consumption

3. Test the OAuth/SSO flow to ensure it redirects back to the local frontend

## Security Considerations

The `X-Force-Local-Frontend` header should only be respected in development or staging environments, not in production. Ensure that:

1. Production environments either ignore this header or validate it against an allowed list of developer IPs
2. Sensitive operations still require proper authentication regardless of this header
3. Consider adding a configuration flag to completely disable this feature in production

## Implementation Checklist

- [ ] Update authentication middleware/controllers
- [ ] Modify URL generation in API responses
- [ ] Configure CORS for local development
- [ ] Update OAuth/SSO callbacks
- [ ] Add security measures for production
- [ ] Document the feature for the development team
- [ ] Test all authentication and redirection flows 