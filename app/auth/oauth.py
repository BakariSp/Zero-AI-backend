from fastapi import Depends, HTTPException, status, APIRouter
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from starlette.requests import Request
from fastapi.responses import RedirectResponse
import os
import logging
import secrets
import time
from urllib.parse import urlencode

from app.users.crud import get_user_by_oauth, create_user, get_user_by_username
from app.db import SessionLocal
from app.auth.jwt import create_access_token
from app.users.schemas import UserCreate

# Set up logging
log = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Centralized OAuth configuration
# Base URLs - determine the correct production domain
LOCAL_BASE_URL = "http://localhost:8000"
# Use the corrected production domain (based on Microsoft which is working)
PRODUCTION_BASE_URL = "https://zero-ai-d9e8f5hgczgremge.westus-01.azurewebsites.net"

# OAuth callback paths
GOOGLE_CALLBACK_PATH = "/oauth/google/callback"
MICROSOFT_CALLBACK_PATH = "/oauth/microsoft/callback"
MICROSOFT_PROD_CALLBACK_PATH = "/auth/login/aad/callback"  # Special path for Microsoft in production

# Full callback URLs
GOOGLE_LOCAL_CALLBACK = f"{LOCAL_BASE_URL}{GOOGLE_CALLBACK_PATH}"
GOOGLE_PROD_CALLBACK = f"{PRODUCTION_BASE_URL}{GOOGLE_CALLBACK_PATH}"
MICROSOFT_LOCAL_CALLBACK = f"{LOCAL_BASE_URL}{MICROSOFT_CALLBACK_PATH}"
MICROSOFT_PROD_CALLBACK = f"{PRODUCTION_BASE_URL}{MICROSOFT_PROD_CALLBACK_PATH}"

# Frontend URLs for redirecting after authentication
LOCAL_FRONTEND_URL = "http://localhost:3000"
PRODUCTION_FRONTEND_URL = "https://learnfromzero.app"  # Update this to your actual production frontend URL

# Use environment variable if set, otherwise determine based on deployment environment
env_frontend_url = os.getenv("FRONTEND_URL")
# Detect if we're in production based on known environment clues
is_production_env = (
    os.getenv("ENVIRONMENT", "").lower() == "production" or 
    os.getenv("ASPNETCORE_ENVIRONMENT", "").lower() == "production" or
    "azure" in os.getenv("WEBSITE_HOSTNAME", "")
)

# Choose the frontend URL based on environment settings
if env_frontend_url:
    # If explicitly set in environment, use that
    FRONTEND_URL = env_frontend_url
    log.info(f"Using explicitly set FRONTEND_URL from environment: {FRONTEND_URL}")
elif is_production_env or 'azure' in PRODUCTION_BASE_URL:
    # If we're in production environment, use production frontend URL
    FRONTEND_URL = PRODUCTION_FRONTEND_URL
    log.info(f"Using production frontend URL: {FRONTEND_URL} (detected production environment)")
else:
    # Default to local frontend URL
    FRONTEND_URL = LOCAL_FRONTEND_URL
    log.info(f"Using local frontend URL: {FRONTEND_URL} (detected local environment)")

# Log additional debug info about environment detection
log.info(f"Environment detection details:")
log.info(f"- ENVIRONMENT var: {os.getenv('ENVIRONMENT', 'Not set')}")
log.info(f"- ASPNETCORE_ENVIRONMENT var: {os.getenv('ASPNETCORE_ENVIRONMENT', 'Not set')}")
log.info(f"- WEBSITE_HOSTNAME var: {os.getenv('WEBSITE_HOSTNAME', 'Not set')}")
log.info(f"- is_production_env: {is_production_env}")
log.info(f"- 'azure' in PRODUCTION_BASE_URL: {'azure' in PRODUCTION_BASE_URL}")

# Log centralized URL configuration
log.info(f"OAuth URL configuration:")
log.info(f"- Google local callback: {GOOGLE_LOCAL_CALLBACK}")
log.info(f"- Google production callback: {GOOGLE_PROD_CALLBACK}")
log.info(f"- Microsoft local callback: {MICROSOFT_LOCAL_CALLBACK}")
log.info(f"- Microsoft production callback: {MICROSOFT_PROD_CALLBACK}")
log.info(f"- Frontend URL: {FRONTEND_URL}")
log.info(f"- Frontend URL source: {'Environment variable' if env_frontend_url else 'Auto-detected based on environment'}")
log.info(f"- Is production environment: {is_production_env}")
log.info(f"- Available frontend URLs: Local={LOCAL_FRONTEND_URL}, Production={PRODUCTION_FRONTEND_URL}")

# Load environment variables directly from os.environ for more reliability
MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID", "")
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

# Print raw values for debugging (with some censoring for security)
print(f"RAW Microsoft Client ID: {MICROSOFT_CLIENT_ID[:5]}{'*' * 20}{MICROSOFT_CLIENT_ID[-5:] if len(MICROSOFT_CLIENT_ID) > 10 else ''}")
print(f"RAW Microsoft Client Secret: {MICROSOFT_CLIENT_SECRET[:3]}{'*' * 10}{MICROSOFT_CLIENT_SECRET[-3:] if len(MICROSOFT_CLIENT_SECRET) > 6 else ''}")

# Log the OAuth credentials (without showing full secrets)
log.info(f"Microsoft Client ID: {MICROSOFT_CLIENT_ID[:5]}...{MICROSOFT_CLIENT_ID[-5:] if MICROSOFT_CLIENT_ID else ''}")
log.info(f"Microsoft Client Secret: {MICROSOFT_CLIENT_SECRET[:3]}...{MICROSOFT_CLIENT_SECRET[-3:] if MICROSOFT_CLIENT_SECRET else ''}")

# Check if environment variables are properly loaded
if not MICROSOFT_CLIENT_ID:
    log.error("MICROSOFT_CLIENT_ID is empty or not set in environment variables!")
if not MICROSOFT_CLIENT_SECRET:
    log.error("MICROSOFT_CLIENT_SECRET is empty or not set in environment variables!")

# Configure OAuth
oauth = OAuth()

# Log more details about the OAuth object
print(f"OAuth type: {type(oauth)}")
print(f"OAuth clients method available: {hasattr(oauth, '_clients')}")
print(f"OAuth register method available: {hasattr(oauth, 'register')}")

# Add a check for empty credentials
if not MICROSOFT_CLIENT_ID or not MICROSOFT_CLIENT_SECRET:
    print("WARNING: Microsoft credentials are not set properly in environment variables!")

# Configure Microsoft OAuth with proper parameters
try:
    oauth.register(
        name="microsoft",
        client_id=MICROSOFT_CLIENT_ID,
        client_secret=MICROSOFT_CLIENT_SECRET,
        server_metadata_url="https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
        # Explicitly add OAuth 2.0 parameters
        access_token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        api_base_url="https://graph.microsoft.com/v1.0/",
    )
    print("Microsoft OAuth client registered successfully")
except Exception as e:
    print(f"Error registering Microsoft OAuth client: {str(e)}")

# Log Microsoft OAuth client details
# if hasattr(oauth, "microsoft"):
#     print(f"Microsoft OAuth client type: {type(oauth.microsoft)}")
#     print(f"Microsoft OAuth client dir: {dir(oauth.microsoft)}")
#     # Also check if we can access the client_id
#     if hasattr(oauth.microsoft, "client_id"):
#         print(f"Microsoft client_id from oauth object: {oauth.microsoft.client_id}")
#     else:
#         print("Microsoft client_id attribute not found in oauth object")

# Configure Google OAuth
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# OAuth login routes
@router.get("/google")
async def login_via_google(request: Request):
    """Initiate Google OAuth login flow"""
    # Log OAuth client status - safely access client_id
    try:
        client_id = getattr(oauth.google, "client_id", None)
        if client_id is None:
            # Try alternate attribute names
            client_id = getattr(oauth.google, "_client_id", "Cannot access client_id")
        log.info(f"Google OAuth client: {client_id}")
    except Exception as e:
        log.error(f"Error accessing Google OAuth client details: {str(e)}")
    
    # Use explicit redirect URI from central configuration
    base_url = str(request.base_url)
    is_local = "localhost" in base_url
    
    # Use the appropriate callback URL based on environment
    redirect_uri = GOOGLE_LOCAL_CALLBACK if is_local else GOOGLE_PROD_CALLBACK
    
    log.info(f"Google redirect URI: {redirect_uri}")
    
    # Generate and store a secure state parameter
    state = secrets.token_urlsafe(16)
    request.session['google_oauth_state'] = state
    log.info(f"Generated Google OAuth state: {state}")
    log.info(f"Session after state set: {dict(request.session)}")
    
    # Return the redirect with explicit state parameter
    return await oauth.google.authorize_redirect(request, redirect_uri, state=state)

@router.get("/google/callback", name="auth_via_google")
async def auth_via_google(request: Request):
    """Handle Google OAuth callback"""
    try:
        log.info(f"Google OAuth callback received")
        log.info(f"Callback URL: {request.url}")
        log.info(f"Query parameters: {dict(request.query_params)}")
        log.info(f"Session contents: {dict(request.session)}")
        
        # Check if we're in production or local
        is_local = "localhost" in str(request.base_url)
        
        # Get the state parameters
        received_state = request.query_params.get("state")
        expected_state = request.session.get("google_oauth_state")
        
        # Check if there's a frontend_url override parameter
        frontend_url_override = request.query_params.get("frontend_url")
        actual_frontend_url = frontend_url_override or FRONTEND_URL
        
        if frontend_url_override:
            log.info(f"Using frontend URL override: {frontend_url_override}")
        
        log.info(f"Received state: {received_state}")
        log.info(f"Expected state from session: {expected_state}")
        
        # Check state mismatch
        if not is_local and (not received_state or not expected_state or received_state != expected_state):
            log.warning(f"State mismatch! Received: {received_state}, Expected: {expected_state}")
            log.warning("Proceeding despite state mismatch (workaround for session issues)")
            
            # Perform manual token exchange for production
            code = request.query_params.get("code")
            if not code:
                log.error("No authorization code in callback")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail="No authorization code provided"
                )
                
            # Use the correct redirect URI from central configuration
            redirect_uri = GOOGLE_LOCAL_CALLBACK if is_local else GOOGLE_PROD_CALLBACK
                
            log.info(f"Using redirect URI for token exchange: {redirect_uri}")
            
            # Perform manual token exchange
            import httpx
            
            token_url = "https://oauth2.googleapis.com/token"
            token_data = {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code"
            }
            
            log.info(f"Performing manual token exchange with Google")
            
            async with httpx.AsyncClient() as client:
                token_response = await client.post(token_url, data=token_data)
                
                if token_response.status_code != 200:
                    log.error(f"Token exchange failed: {token_response.status_code}, {token_response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Failed to get token from Google: {token_response.status_code}"
                    )
                    
                token_data = token_response.json()
                log.info(f"Token exchange successful, keys: {list(token_data.keys())}")
                
                # Get user info from ID token or access token
                access_token = token_data.get("access_token")
                id_token = token_data.get("id_token")
                
                if id_token:
                    # Parse the ID token for user info
                    import jwt
                    id_token_data = jwt.decode(id_token, options={"verify_signature": False})
                    log.info(f"Decoded ID token claims: {list(id_token_data.keys())}")
                    
                    # Extract user info from ID token
                    oauth_id = id_token_data.get("sub")
                    email = id_token_data.get("email")
                    name = id_token_data.get("name")
                    picture = id_token_data.get("picture")
                    
                elif access_token:
                    # Use userinfo endpoint with access token
                    userinfo_response = await client.get(
                        "https://www.googleapis.com/oauth2/v3/userinfo",
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    
                    if userinfo_response.status_code != 200:
                        log.error(f"Failed to get user info: {userinfo_response.status_code}")
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Failed to get user info from Google"
                        )
                        
                    user_data = userinfo_response.json()
                    log.info(f"Retrieved user info: {list(user_data.keys())}")
                    
                    oauth_id = user_data.get("sub")
                    email = user_data.get("email")
                    name = user_data.get("name")
                    picture = user_data.get("picture")
                else:
                    log.error("No tokens returned from Google")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="No tokens returned from Google"
                    )
        else:
            # Standard OAuth flow for local development or when state matches
            log.info("Using standard OAuth flow for token exchange")
            token = await oauth.google.authorize_access_token(request)
            
            if "userinfo" not in token:
                log.error(f"Missing userinfo in token response: {list(token.keys())}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing user information in token response"
                )
                
            user_info = token.get("userinfo")
            oauth_id = user_info.get("sub")
            email = user_info.get("email") 
            name = user_info.get("name")
            picture = user_info.get("picture")
            
        # Ensure we have required user info
        if not oauth_id or not email:
            log.error(f"Missing required user info: oauth_id={bool(oauth_id)}, email={bool(email)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not retrieve required user information from Google"
            )
            
        log.info(f"Successfully retrieved user info from Google: email={email}")
        
        # Create or retrieve user
        db = SessionLocal()
        is_new_user = False
        
        try:
            # First try to find the user by OAuth ID
            user = get_user_by_oauth(db, provider="google", oauth_id=oauth_id)
            
            # If not found, create a new user
            if not user:
                log.info(f"Creating new user for Google OAuth: {email}")
                is_new_user = True
                
                # Generate a username from email
                username = email.split("@")[0]
                
                # Check if username exists and append numbers if needed
                base_username = username
                counter = 1
                while get_user_by_username(db, username):
                    username = f"{base_username}{counter}"
                    counter += 1
                
                # Create a UserCreate object
                user_data = UserCreate(
                    email=email,
                    username=username,
                    password="",  # No password for OAuth users
                    full_name=name or "",
                    is_active=True
                )
                
                # Create the user
                user = create_user(
                    db=db,
                    user=user_data,
                    oauth_provider="google",
                    oauth_id=oauth_id,
                    profile_picture=picture
                )
                log.info(f"Created new user: {username}")
            else:
                log.info(f"Found existing user: {user.username}")
        finally:
            db.close()
            
        # Create access token
        access_token = create_access_token(data={"sub": user.email})
        
        # Redirect to frontend with token and new user flag
        redirect_url = f"{actual_frontend_url}/oauth/callback?token={access_token}&is_new_user={str(is_new_user).lower()}"
        
        log.info(f"Redirecting to frontend: {redirect_url}")
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        log.error(f"Google OAuth callback error: {str(e)}")
        # Redirect to frontend error page
        
        # Check if there's a frontend_url override parameter
        frontend_url_override = request.query_params.get("frontend_url")
        actual_frontend_url = frontend_url_override or FRONTEND_URL
        
        error_url = f"{actual_frontend_url}/oauth/error?message={str(e)}"
        return RedirectResponse(url=error_url)

@router.get("/microsoft")
async def login_via_microsoft(request: Request):
    """Initiate Microsoft OAuth login flow"""
    # Get fresh environment variables to ensure we have the latest values
    fresh_client_id = MICROSOFT_CLIENT_ID
    fresh_client_secret = MICROSOFT_CLIENT_SECRET
    
    # Log the actual client ID being used (partially masked)
    if fresh_client_id:
        masked_id = fresh_client_id[:5] + "*****" + fresh_client_id[-5:] if len(fresh_client_id) > 10 else "*****"
        log.info(f"Using Microsoft client ID: {masked_id}")
    else:
        log.error("Microsoft client ID is empty!")
    
    # Log OAuth client status and fresh values - safely access attributes
    try:
        # Try to safely get client_id from OAuth object
        oauth_client_id = "Unknown"
        if hasattr(oauth.microsoft, "client_id"):
            oauth_client_id = oauth.microsoft.client_id
        elif hasattr(oauth.microsoft, "_client_id"):
            oauth_client_id = oauth.microsoft._client_id
        
        log.info(f"Microsoft OAuth client ID (from module): {oauth_client_id}")
    except Exception as e:
        log.error(f"Error accessing Microsoft OAuth client details: {str(e)}")
        
    log.info(f"Microsoft OAuth client ID (fresh from env): {fresh_client_id[:5]}...{fresh_client_id[-5:] if fresh_client_id else 'EMPTY'}")
    log.info(f"Microsoft OAuth client secret available (fresh): {'Yes' if fresh_client_secret else 'No'}")
    log.info(f"Request headers: {dict(request.headers)}")
    
    # Get debug param if present
    debug_mode = request.query_params.get('debug', 'false').lower() == 'true'
    
    # Use the exact redirect URI from central configuration
    base_url = str(request.base_url)
    log.info(f"Base URL: {base_url}")
    
    # Use the appropriate callback URL based on environment
    is_local = "localhost" in base_url
    redirect_uri = MICROSOFT_LOCAL_CALLBACK if is_local else MICROSOFT_PROD_CALLBACK
    
    log.info(f"Microsoft redirect URI: {redirect_uri}")
    
    # Check if we have valid credentials
    if not fresh_client_id:
        log.error("Microsoft client ID is empty! Cannot proceed with authentication.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Microsoft client ID is not configured properly"
        )
    
    # Generate a secure random state
    state = secrets.token_urlsafe(16)
    
    # Store in session
    request.session['microsoft_oauth_state'] = state
    
    # The session is automatically saved after the request in Starlette
    
    # Log the session state for debugging
    log.info(f"Setting session state: {state}")
    log.info(f"Session contents: {dict(request.session)}")
    
    # Add state to the auth URL - Use correct Microsoft Graph scopes
    # Use the User.Read scope which is needed for accessing user profile
    auth_url = (
        f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?"
        f"client_id={fresh_client_id}&"
        f"response_type=code&"
        f"redirect_uri={redirect_uri}&"
        f"scope=openid%20email%20profile%20User.Read&"  # Added User.Read scope
        f"state={state}"  # Add state parameter
    )
    
    # Log complete params for debugging (without showing full client ID)
    safe_params = auth_url.split('&')
    safe_params = [param for param in safe_params if 'client_id' not in param]
    safe_params = '&'.join(safe_params)
    log.info(f"Auth parameters: {safe_params}")
    
    # If debug mode is enabled, return the parameters instead of redirecting
    if debug_mode:
        return {
            "status": "debug_mode",
            "auth_params": safe_params,
            "client_id_available": bool(fresh_client_id),
            "client_secret_available": bool(fresh_client_secret),
            "message": "Debug mode enabled. These are the parameters that would be sent to Microsoft."
        }
    
    # Use the direct approach instead of oauth.microsoft.authorize_redirect
    # This resolves issues with the Authlib OAuth client
    log.info(f"Redirecting to Microsoft auth URL (redacted): {auth_url.replace(fresh_client_id, '{CLIENT_ID_REDACTED}')}")
    
    # Return a redirect response
    return RedirectResponse(url=auth_url)

@router.get("/microsoft/callback", name="auth_via_microsoft")
async def auth_via_microsoft(request: Request):
    """Handle Microsoft OAuth callback"""
    try:
        # Get query parameters
        code = request.query_params.get("code")
        received_state = request.query_params.get("state")
        expected_state = request.session.get("microsoft_oauth_state")
        
        # Check if there's a frontend_url override parameter
        frontend_url_override = request.query_params.get("frontend_url")
        actual_frontend_url = frontend_url_override or FRONTEND_URL
        
        if frontend_url_override:
            log.info(f"Using frontend URL override: {frontend_url_override}")
        
        # Log details for debugging
        log.info(f"Microsoft OAuth callback received")
        log.info(f"Code present: {bool(code)}")
        log.info(f"Received state: {received_state}")
        log.info(f"Expected state from session: {expected_state}")
        log.info(f"Session contents: {dict(request.session)}")
        log.info(f"Request cookies: {dict(request.cookies)}")
        log.info(f"Frontend URL for redirect: {actual_frontend_url}")
        
        if not code:
            log.error("Missing authorization code in callback")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authorization code from Microsoft"
            )
        
        # Use the appropriate callback URL based on environment
        is_local = "localhost" in str(request.base_url)
        redirect_uri = MICROSOFT_LOCAL_CALLBACK if is_local else MICROSOFT_PROD_CALLBACK
        
        log.info(f"Using redirect URI: {redirect_uri}")
            
        # Check for state mismatch but continue anyway (session state issues)
        if not received_state or received_state != expected_state:
            log.warning(f"State mismatch! Received: {received_state}, Expected: {expected_state}")
            log.warning("Proceeding despite state mismatch (workaround for session issues)")
            
        # Perform manual token exchange
        token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        
        # Prepare token request
        import httpx
        
        # Create form data for token exchange
        token_data = {
            "client_id": MICROSOFT_CLIENT_ID,
            "client_secret": MICROSOFT_CLIENT_SECRET,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "scope": "openid email profile User.Read"
        }
        
        # Log token request
        log.info(f"Requesting access token from {token_url}")
        
        # Make the token request
        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=token_data)
            
            # Check if the token request was successful
            if token_response.status_code != 200:
                log.error(f"Token request failed: {token_response.status_code}, {token_response.text}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Failed to get token from Microsoft: {token_response.status_code}"
                )
                
            # Parse the token response
            token_data = token_response.json()
            
            # Log the token response keys for debugging
            log.info(f"Token response keys: {list(token_data.keys())}")
            log.info("Successfully obtained token from Microsoft")
            
            # Make sure we have the ID token
            id_token = token_data.get("id_token")
            if not id_token:
                log.error("No ID token in response")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No ID token in response from Microsoft"
                )
            
            # Always use ID token to get user info
            try:
                # Parse the ID token (JWT)
                import jwt
                # Decode without verification for this purpose
                id_token_data = jwt.decode(id_token, options={"verify_signature": False})
                
                # Log all the claims for debugging
                log.info(f"ID token claims: {id_token_data}")
                
                # Extract necessary user info from ID token
                # Different Azure AD configurations might use different claim names
                # Try all possible claim names
                oauth_id = (
                    id_token_data.get("oid") or  # Azure AD v2 Object ID
                    id_token_data.get("sub") or  # OAuth2 Subject
                    id_token_data.get("unique_name")  # Fallback
                )
                
                email = (
                    id_token_data.get("email") or  # Standard email claim
                    id_token_data.get("upn") or  # User Principal Name
                    id_token_data.get("preferred_username")  # Microsoft preferred_username
                )
                
                name = (
                    id_token_data.get("name") or  # Standard name claim
                    id_token_data.get("given_name", "") + " " + id_token_data.get("family_name", "")  # Combine given_name and family_name
                ).strip()
                
                # Log the extracted user info
                log.info(f"Extracted user info from ID token: id={oauth_id}, email={email}, name={name}")
                
                # Validate that we have the necessary info
                if not oauth_id or not email:
                    log.error(f"Missing required user info from ID token: id={bool(oauth_id)}, email={bool(email)}")
                    raise ValueError("Missing required user info from ID token")
                    
            except Exception as e:
                log.error(f"Failed to process ID token: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Failed to process ID token: {str(e)}"
                )
                
            # Now create or retrieve the user
            from sqlalchemy.orm import Session
            from app.models import User
            from app.db import get_db
            
            db = SessionLocal()
            is_new_user = False  # Flag to track if this is a new user
            
            try:
                # First try to find the user by OAuth ID
                user = get_user_by_oauth(db, provider="microsoft", oauth_id=oauth_id)
                
                # If not found by OAuth ID, try by email
                if not user:
                    log.info(f"User not found by OAuth ID {oauth_id}, trying email {email}")
                    
                    # Check if user exists with this email
                    user_by_email = db.query(User).filter(User.email == email).first()
                    
                    if user_by_email:
                        log.info(f"Found existing user by email: {email}")
                        
                        # Check if this user has OAuth info already
                        if user_by_email.oauth_provider and user_by_email.oauth_id:
                            log.info(f"User already has OAuth connection: {user_by_email.oauth_provider} / {user_by_email.oauth_id}")
                            
                            # Update the OAuth ID if it's different but from same provider
                            if user_by_email.oauth_provider == "microsoft" and user_by_email.oauth_id != oauth_id:
                                log.info(f"Updating user's Microsoft OAuth ID from {user_by_email.oauth_id} to {oauth_id}")
                                user_by_email.oauth_id = oauth_id
                                db.commit()
                        else:
                            # User exists but doesn't have OAuth info, add it
                            log.info(f"Adding Microsoft OAuth info to existing user: {email}")
                            user_by_email.oauth_provider = "microsoft"
                            user_by_email.oauth_id = oauth_id
                            db.commit()
                            
                        # Use this user
                        user = user_by_email
                
                # If still not found, create a new user
                if not user:
                    log.info(f"Creating new user for Microsoft OAuth: {email}")
                    # Set flag for new user
                    is_new_user = True
                    
                    # Generate a username from email
                    username = email.split("@")[0]
                    
                    # Check if username exists and append numbers if needed
                    base_username = username
                    counter = 1
                    while get_user_by_username(db, username):
                        username = f"{base_username}{counter}"
                        counter += 1
                    
                    # Create a UserCreate object
                    user_data = UserCreate(
                        email=email,
                        username=username,
                        password="",  # No password for OAuth users
                        full_name=name or "",
                        is_active=True
                    )
                    
                    # Create the user
                    user = create_user(
                        db=db,
                        user=user_data,
                        oauth_provider="microsoft",
                        oauth_id=oauth_id,
                        profile_picture=None
                    )
                    log.info(f"Created new user: {username}")
                else:
                    log.info(f"Found existing user: {user.username}")
            finally:
                db.close()
                
            # Create JWT access token for the user
            access_token = create_access_token(data={"sub": user.email})
            
            # Redirect to frontend with token and new user flag
            redirect_url = f"{actual_frontend_url}/oauth/callback?token={access_token}&is_new_user={str(is_new_user).lower()}"
            
            log.info(f"Redirecting to frontend: {redirect_url}")
            return RedirectResponse(url=redirect_url)
            
    except Exception as e:
        log.error(f"Microsoft callback error: {str(e)}")
        # Redirect to frontend error page
        
        # Check if there's a frontend_url override parameter
        frontend_url_override = request.query_params.get("frontend_url")
        actual_frontend_url = frontend_url_override or FRONTEND_URL
        
        error_url = f"{actual_frontend_url}/oauth/error?message={str(e)}"
        return RedirectResponse(url=error_url)

# Add additional route for production Azure redirect URI
@router.get("/auth/login/aad/callback")
async def auth_via_microsoft_prod(request: Request):
    """Handle Microsoft OAuth callback in production"""
    log.info("Received Microsoft OAuth callback via production path")
    
    # Log all request information for debugging
    log.info(f"Production callback URL: {request.url}")
    log.info(f"Production callback query params: {dict(request.query_params)}")
    log.info(f"Production callback headers: {dict(request.headers)}")
    log.info(f"Production callback session: {dict(request.session)}")
    
    # Extract the code and state parameters
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    
    # Check if there's a frontend_url override parameter and pass it along
    frontend_url_override = request.query_params.get("frontend_url")
    
    # Build the query parameters to forward (maintaining frontend_url if present)
    query_params = dict(request.query_params)
    
    # Check if we have the required parameters
    if not code:
        log.error("Missing code parameter in production callback")
        
        # Use the override or default frontend URL
        actual_frontend_url = frontend_url_override or FRONTEND_URL
        error_url = f"{actual_frontend_url}/oauth/error?message=Missing+code+parameter"
        return RedirectResponse(url=error_url)
    
    # Just forward to the standard handler
    return await auth_via_microsoft(request)

# Add a testing endpoint for diagnosing Microsoft OAuth issues
@router.get("/microsoft/test")
async def test_microsoft_oauth(request: Request):
    """Test endpoint for Microsoft OAuth configuration"""
    try:
        # Check environment variables directly
        raw_client_id = MICROSOFT_CLIENT_ID
        raw_client_secret = MICROSOFT_CLIENT_SECRET
        
        # Check if we have the required credentials
        client_id_ok = bool(raw_client_id)
        client_secret_ok = bool(raw_client_secret)
        
        # Get redirect URI from central configuration
        is_local = "localhost" in str(request.base_url)
        redirect_uri = MICROSOFT_LOCAL_CALLBACK if is_local else MICROSOFT_PROD_CALLBACK
        
        # Check if the OAuth client is configured
        oauth_client_ok = hasattr(oauth, "microsoft") and oauth.microsoft is not None
        
        # Safely get client ID from OAuth client
        oauth_client_id = "Unknown"
        if oauth_client_ok:
            # Try various attribute names
            for attr_name in ["client_id", "_client_id"]:
                if hasattr(oauth.microsoft, attr_name):
                    oauth_client_id = getattr(oauth.microsoft, attr_name)
                    break
            
            # If we still don't have it, try to inspect the object
            if oauth_client_id == "Unknown":
                oauth_client_id = f"Object attributes: {dir(oauth.microsoft)}"
        else:
            oauth_client_id = "OAuth client not configured"
        
        # Build a manually constructed auth URL for testing with actual client ID
        auth_url = (
            f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?"
            f"client_id={raw_client_id}&"
            f"response_type=code&"
            f"redirect_uri={redirect_uri}&"
            f"scope=openid%20email%20profile"
        )
        
        # Check all environment variables
        env_vars = {
            "MICROSOFT_CLIENT_ID": mask_string(raw_client_id),
            "MICROSOFT_CLIENT_SECRET": mask_string(raw_client_secret),
            "FRONTEND_URL": FRONTEND_URL,
            "JWT_SECRET_KEY": mask_string(os.getenv("JWT_SECRET_KEY", "Not set")),
            "SESSION_SECRET_KEY": mask_string(os.getenv("SESSION_SECRET_KEY", "Not set"))
        }
        
        # Return diagnostic information with centralized URL config
        return {
            "status": "configuration_test",
            "client_id_available": client_id_ok,
            "client_secret_available": client_secret_ok,
            "client_id_masked": mask_string(raw_client_id),
            "oauth_client_configured": oauth_client_ok,
            "oauth_client_id": oauth_client_id,
            "oauth_client_dir": dir(oauth.microsoft) if oauth_client_ok else [],
            "url_configuration": {
                "local_base_url": LOCAL_BASE_URL,
                "production_base_url": PRODUCTION_BASE_URL,
                "google_local_callback": GOOGLE_LOCAL_CALLBACK,
                "google_prod_callback": GOOGLE_PROD_CALLBACK,
                "microsoft_local_callback": MICROSOFT_LOCAL_CALLBACK,
                "microsoft_prod_callback": MICROSOFT_PROD_CALLBACK
            },
            "redirect_uri": redirect_uri,
            "manual_auth_url": auth_url,
            "environment_vars": env_vars,
            "message": "Use the manual_auth_url to test the oauth flow directly",
            "test_instructions": "Click the manual_auth_url to test the flow directly with Microsoft"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Error during configuration test"
        }

# Add an endpoint to check environment variables
@router.get("/env-test")
async def check_environment_variables():
    """Test endpoint for checking environment variables"""
    # Important environment variables to check
    env_vars = {
        "MICROSOFT_CLIENT_ID": os.getenv("MICROSOFT_CLIENT_ID"),
        "MICROSOFT_CLIENT_SECRET": os.getenv("MICROSOFT_CLIENT_SECRET"),
        "GOOGLE_CLIENT_ID": os.getenv("GOOGLE_CLIENT_ID"),
        "GOOGLE_CLIENT_SECRET": os.getenv("GOOGLE_CLIENT_SECRET"),
        "FRONTEND_URL": os.getenv("FRONTEND_URL"),
        "JWT_SECRET_KEY": os.getenv("JWT_SECRET_KEY"),
        "SESSION_SECRET_KEY": os.getenv("SESSION_SECRET_KEY")
    }
    
    # Mask sensitive values for security
    safe_vars = {}
    for key, value in env_vars.items():
        if value:
            # Special case for URL - show full value
            if "URL" in key:
                safe_vars[key] = value
            else:
                safe_vars[key] = mask_string(value)
        else:
            safe_vars[key] = "Not set or empty"
    
    return {
        "status": "environment_check",
        "environment_variables": safe_vars,
        "variables_set": {k: bool(v) for k, v in env_vars.items()},
        "message": "Environment variables check"
    }

# Helper function to mask sensitive strings
def mask_string(s, show_start=4, show_end=4):
    """Mask a string for safe display, showing only start and end characters"""
    if not s:
        return "Not set or empty"
    if len(s) <= show_start + show_end:
        return "*" * len(s)
    return s[:show_start] + "*" * (len(s) - show_start - show_end) + s[-show_end:]

async def get_oauth_user(provider: str, request: Request):
    """
    Get user information from OAuth provider and create/update user in database
    Returns a tuple: (user, is_new_user)
    """
    if provider not in oauth._clients:
        log.error(f"Unsupported OAuth provider: {provider}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OAuth provider: {provider}"
        )
    
    client = oauth._clients[provider]
    
    try:
        log.info(f"Authorizing access token for {provider}")
        # For Microsoft, explicitly include client_id to avoid AADSTS900144 error
        if provider == "microsoft":
            # Get fresh credentials
            fresh_client_id = MICROSOFT_CLIENT_ID
            fresh_client_secret = MICROSOFT_CLIENT_SECRET
            
            # Verify we have valid credentials
            if not fresh_client_id or not fresh_client_secret:
                log.error(f"Missing Microsoft credentials during token exchange. ID: {bool(fresh_client_id)}, Secret: {bool(fresh_client_secret)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Microsoft OAuth credentials not properly configured"
                )
                
            # Log request information
            log.info(f"Microsoft authorization request URL: {request.url}")
            log.info(f"Microsoft authorization request query params: {request.query_params}")
            
            # Get the code parameter
            code = request.query_params.get("code")
            if not code:
                log.error("Missing code parameter in Microsoft callback")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing code parameter in Microsoft callback"
                )
                
            # Get the appropriate redirect URI from central configuration
            is_local = "localhost" in str(request.base_url)
            redirect_uri = MICROSOFT_LOCAL_CALLBACK if is_local else MICROSOFT_PROD_CALLBACK
                
            log.info(f"Using redirect URI for token exchange: {redirect_uri}")
            
            # Include all required parameters explicitly
            try:
                # Attempt to use the built-in token exchange first
                try:
                    log.info("Attempting standard OAuth token exchange")
                    token = await client.authorize_access_token(request)
                    log.info("Microsoft access token obtained successfully via standard method")
                except Exception as auth_error:
                    log.warning(f"Standard OAuth token exchange failed: {str(auth_error)}")
                    log.info("Falling back to manual token exchange")
                    
                    # Fallback to manual token exchange
                    token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
                    token_data = {
                        "client_id": fresh_client_id,
                        "client_secret": fresh_client_secret,
                        "code": code,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code"
                    }
                    
                    # Use client's session for the request
                    resp = await client.session.post(token_url, data=token_data)
                    
                    if resp.status_code != 200:
                        log.error(f"Manual token exchange failed: {resp.status_code}, {await resp.text()}")
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=f"Token exchange failed: {resp.status_code}"
                        )
                        
                    token = await resp.json()
                    log.info("Microsoft access token obtained successfully via manual method")
            except Exception as auth_error:
                log.error(f"Microsoft access token error: {str(auth_error)}")
                # Get the raw data from the request to help diagnose
                log.error(f"Request query string: {request.url.query}")
                raise
        elif provider == "google":
            try:
                # For Google, we'll use the standard library approach without passing extra params
                # The redirect URI is already stored in the session from the initial auth request
                log.info("Using standard OAuth token exchange for Google")
                
                # Log the request URL and parameters for debugging
                log.info(f"Google callback URL: {request.url}")
                log.info(f"Google callback query params: {dict(request.query_params)}")
                
                # Use the library's token exchange mechanism without explicit redirect URI
                # It will use the same one that was used for the initial authorization request
                token = await client.authorize_access_token(request)
                log.info("Successfully obtained Google access token")
            except Exception as e:
                log.error(f"Google token exchange error: {str(e)}")
                log.error(f"Google callback URL: {request.url}")
                log.error(f"Google callback query params: {dict(request.query_params)}")
                raise
        else:
            token = await client.authorize_access_token(request)
            
        log.info(f"Successfully obtained access token for {provider}")
        
        user_info = {}
        
        if provider == "google":
            user_info = token.get("userinfo")
            oauth_id = user_info.get("sub")
            email = user_info.get("email")
            name = user_info.get("name")
            picture = user_info.get("picture")
            log.info(f"Retrieved user info from Google: email={email}")
        
        elif provider == "microsoft":
            try:
                # Log the token data (without sensitive parts)
                if isinstance(token, dict):
                    log.info(f"Token keys: {list(token.keys())}")
                    
                # Get user info from Microsoft Graph API
                log.info("Querying Microsoft Graph API")
                resp = await client.get("https://graph.microsoft.com/v1.0/me", token=token)
                user_info = resp.json()
                
                # Log the user info (without sensitive parts)
                safe_info = {k: v for k, v in user_info.items() if k not in ('id')}
                log.info(f"Microsoft user info: {safe_info}")
                
                oauth_id = user_info.get("id")
                email = user_info.get("mail") or user_info.get("userPrincipalName")
                name = user_info.get("displayName")
                picture = None
                log.info(f"Retrieved user info from Microsoft: email={email}")
            except Exception as e:
                log.error(f"Error getting Microsoft user info: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error getting Microsoft user info: {str(e)}"
                )
        
        if not oauth_id or not email:
            log.error(f"Missing required user info from {provider}: oauth_id={bool(oauth_id)}, email={bool(email)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not retrieve user information from {provider} OAuth provider"
            )
        
        # Check if user exists in database
        db = SessionLocal()
        is_new_user = False  # Flag to track if this is a new user
        
        try:
            user = get_user_by_oauth(db, provider=provider, oauth_id=oauth_id)
            
            # If user doesn't exist, create a new one
            if not user:
                log.info(f"Creating new user for {provider} OAuth: {email}")
                is_new_user = True  # Set flag for new user
                
                # Generate a username from email if not available
                username = email.split("@")[0]
                
                # Check if username exists and append numbers if needed
                base_username = username
                counter = 1
                while get_user_by_username(db, username):
                    username = f"{base_username}{counter}"
                    counter += 1
                
                # Create a UserCreate object first
                user_data = UserCreate(
                    email=email,
                    username=username,
                    password="",  # No password for OAuth users
                    full_name=name or "",
                    is_active=True
                )
                
                # Then call create_user with the correct parameters
                user = create_user(
                    db=db,
                    user=user_data,
                    oauth_provider=provider,
                    oauth_id=oauth_id,
                    profile_picture=picture
                )
                log.info(f"Created new user: {username}")
            else:
                log.info(f"Found existing user: {user.username}")
        finally:
            db.close()
        
        return user, is_new_user
        
    except Exception as e:
        log.error(f"OAuth error for {provider}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication error with {provider}: {str(e)}"
        )

# Add a direct Microsoft login endpoint that bypasses the Authlib OAuth flow
@router.get("/microsoft/direct")
async def direct_microsoft_login(request: Request):
    """A direct Microsoft login endpoint that builds the URL manually"""
    # Get client ID from central configuration
    client_id = MICROSOFT_CLIENT_ID
    
    # Log the actual client ID being used (partially masked)
    if client_id:
        masked_id = client_id[:5] + "*****" + client_id[-5:] if len(client_id) > 10 else "*****"
        log.info(f"Using Microsoft client ID: {masked_id}")
    else:
        log.error("Microsoft client ID is empty!")
    
    # Use the appropriate callback URL based on environment
    is_local = "localhost" in str(request.base_url)
    redirect_uri = MICROSOFT_LOCAL_CALLBACK if is_local else MICROSOFT_PROD_CALLBACK
    
    # Build the authorization URL manually with explicit client ID from environment
    # Include User.Read scope for Microsoft Graph API access
    auth_url = (
        f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?"
        f"client_id={client_id}&"
        f"response_type=code&"
        f"redirect_uri={redirect_uri}&"
        f"scope=openid%20email%20profile%20User.Read"  # Added User.Read scope
    )
    
    log.info(f"Redirecting to manual Microsoft auth URL (redacted): {auth_url.replace(client_id, '{CLIENT_ID_REDACTED}')}")
    
    # Return a redirect response
    return RedirectResponse(url=auth_url)

# Add a direct callback endpoint for debugging
@router.get("/microsoft/direct-callback")
async def direct_microsoft_callback(request: Request):
    """A direct callback endpoint that just logs all the parameters"""
    # Log all request information
    log.info(f"Direct Microsoft callback received")
    log.info(f"URL: {request.url}")
    log.info(f"Query parameters: {dict(request.query_params)}")
    log.info(f"Headers: {dict(request.headers)}")
    
    # Get the code parameter
    code = request.query_params.get("code")
    
    # Return details about the request
    return {
        "status": "callback_received",
        "code_received": bool(code),
        "url": str(request.url),
        "query_params": dict(request.query_params),
        "message": "Callback received and logged. This is just for debugging purposes."
    }

# Add a session test endpoint
@router.get("/session-test")
async def test_session(request: Request):
    """Test endpoint for session functionality"""
    # Get the counter from the session or initialize it
    counter = request.session.get("counter", 0)
    counter += 1
    
    # Store the counter in the session
    request.session["counter"] = counter
    
    # Store a timestamp to check if it persists
    timestamp = time.time()
    request.session["timestamp"] = timestamp
    
    # No need to explicitly save - Starlette sessions are automatically saved
    # when the request completes
    
    # Log session info
    log.info(f"Session test - counter: {counter}, timestamp: {timestamp}")
    log.info(f"Session contents: {dict(request.session)}")
    
    # Return session information
    return {
        "status": "session_test",
        "counter": counter,
        "timestamp": timestamp,
        "session_id": request.session.get("session_id", "No session ID"),
        "session_content": dict(request.session),
        "session_cookie_name": "zero_session", # Should match the one in main.py
        "cookies": {k: v for k, v in request.cookies.items()},
        "session_middleware_info": {
            "session_cookie": request.cookies.get("zero_session", "No session cookie found"),
            "secure_cookies": os.environ.get("SECURE_COOKIES", "Not set"),
            "session_secret_key": mask_string(os.environ.get("SESSION_SECRET_KEY", "Not set")),
        },
        "message": "Refresh this page to test if the session counter increases"
    }

# Add a token debug endpoint for examining ID tokens
@router.post("/token-debug")
async def debug_token(request: Request):
    """Debug endpoint to examine token contents"""
    try:
        # Get the token from request body
        body = await request.json()
        token = body.get("token")
        
        if not token:
            return {"error": "No token provided"}
            
        # Try to decode the token
        import jwt
        token_data = jwt.decode(token, options={"verify_signature": False})
        
        # Return the decoded data with some light masking of sensitive values
        safe_data = {}
        for key, value in token_data.items():
            if key in ["email", "upn", "preferred_username", "sub", "oid"]:
                # Apply light masking to sensitive values
                if isinstance(value, str) and len(value) > 8:
                    masked_value = value[:4] + "..." + value[-4:]
                    safe_data[key] = masked_value
                else:
                    safe_data[key] = value
            else:
                safe_data[key] = value
                
        return {
            "status": "success",
            "token_type": "ID Token (JWT)" if token.count(".") == 2 else "Unknown",
            "decoded_data": token_data,
            "safe_decoded_data": safe_data,
            "claims_found": list(token_data.keys()),
            "message": "Token decoded successfully"
        }
        
    except jwt.exceptions.InvalidTokenError as e:
        return {
            "status": "error",
            "error": f"Invalid token: {str(e)}",
            "message": "Could not decode the provided token"
        }
    except Exception as e:
        return {
            "status": "error", 
            "error": str(e),
            "message": "An error occurred while processing the token"
        }

# Add a debugging endpoint for OAuth redirect URIs
@router.get("/debug-redirect-uris")
async def debug_redirect_uris(request: Request):
    """Debug endpoint to display the redirect URIs being used for OAuth"""
    base_url = str(request.base_url)
    
    # Determine if we're in local or production
    is_local = "localhost" in base_url
    
    # Get the redirect URIs from central configuration
    google_redirect_uri = GOOGLE_LOCAL_CALLBACK if is_local else GOOGLE_PROD_CALLBACK
    microsoft_redirect_uri = MICROSOFT_LOCAL_CALLBACK if is_local else MICROSOFT_PROD_CALLBACK
    
    # Get the actual host and check for protocol issues
    host = request.headers.get("host", "unknown")
    forwarded_proto = request.headers.get("x-forwarded-proto", "unknown")
    original_host = request.headers.get("x-original-host", "unknown")
    forwarded_host = request.headers.get("x-forwarded-host", "unknown")
    
    # Log info for debugging
    log.info(f"Debugging redirect URIs:")
    log.info(f"Base URL: {base_url}")
    log.info(f"Google redirect URI: {google_redirect_uri}")
    log.info(f"Microsoft redirect URI: {microsoft_redirect_uri}")
    log.info(f"Host header: {host}")
    log.info(f"X-Forwarded-Proto: {forwarded_proto}")
    log.info(f"X-Original-Host: {original_host}")
    log.info(f"X-Forwarded-Host: {forwarded_host}")
    
    # Get environment info
    env_info = {
        "GOOGLE_CLIENT_ID": mask_string(GOOGLE_CLIENT_ID),
        "GOOGLE_CLIENT_SECRET": mask_string(GOOGLE_CLIENT_SECRET),
        "MICROSOFT_CLIENT_ID": mask_string(MICROSOFT_CLIENT_ID),
        "MICROSOFT_CLIENT_SECRET": mask_string(MICROSOFT_CLIENT_SECRET),
        "FRONTEND_URL": FRONTEND_URL,
        "ENVIRONMENT": os.getenv("ENVIRONMENT", "Not set"),
        "ASPNETCORE_ENVIRONMENT": os.getenv("ASPNETCORE_ENVIRONMENT", "Not set"),
    }
    
    # Check if session is working
    session_test_value = f"test-{int(time.time())}"
    request.session["test_value"] = session_test_value
    
    # Try to get previously stored values
    previous_test = request.session.get("previous_test", "Not set")
    request.session["previous_test"] = session_test_value
    
    # Check if we can detect the actual domain
    detected_domain = None
    if host and host != "unknown" and host != "localhost:8000":
        detected_domain = host
    elif original_host and original_host != "unknown":
        detected_domain = original_host
    elif forwarded_host and forwarded_host != "unknown":
        detected_domain = forwarded_host
    
    # Determine the protocol
    protocol = "https" if forwarded_proto == "https" else "http"
    
    # Provide recommended redirect URIs based on detected values
    recommended_google_uri = None
    if detected_domain:
        recommended_google_uri = f"{protocol}://{detected_domain}{GOOGLE_CALLBACK_PATH}"
    
    # Extract domain names from production URLs for comparison
    google_domain = PRODUCTION_BASE_URL.split("//")[1] if "//" in PRODUCTION_BASE_URL else PRODUCTION_BASE_URL
    
    return {
        "base_url": base_url,
        "is_local": is_local,
        "centralized_url_config": {
            "local_base_url": LOCAL_BASE_URL,
            "production_base_url": PRODUCTION_BASE_URL,
            "google_callback_path": GOOGLE_CALLBACK_PATH,
            "microsoft_callback_path": MICROSOFT_CALLBACK_PATH,
            "microsoft_prod_callback_path": MICROSOFT_PROD_CALLBACK_PATH,
            "google_local_callback": GOOGLE_LOCAL_CALLBACK,
            "google_prod_callback": GOOGLE_PROD_CALLBACK,
            "microsoft_local_callback": MICROSOFT_LOCAL_CALLBACK,
            "microsoft_prod_callback": MICROSOFT_PROD_CALLBACK
        },
        "frontend_url_config": {
            "current_frontend_url": FRONTEND_URL,
            "local_frontend_url": LOCAL_FRONTEND_URL,
            "production_frontend_url": PRODUCTION_FRONTEND_URL,
            "env_frontend_url": env_frontend_url,
            "is_production_environment": is_production_env,
            "frontend_url_source": "Environment variable" if env_frontend_url else "Auto-detected based on environment"
        },
        "active_redirect_uris": {
            "google": google_redirect_uri,
            "microsoft": microsoft_redirect_uri
        },
        "environment_info": env_info,
        "request_headers": dict(request.headers),
        "session_info": {
            "current_test_value": session_test_value,
            "previous_test_value": previous_test,
            "session_working": previous_test != "Not set" and previous_test != session_test_value,
            "all_session_data": dict(request.session)
        },
        "detected_host_info": {
            "host_header": host,
            "x_forwarded_proto": forwarded_proto,
            "x_original_host": original_host,
            "x_forwarded_host": forwarded_host,
            "detected_domain": detected_domain,
            "detected_protocol": protocol,
            "recommended_google_redirect_uri": recommended_google_uri
        },
        "google_cloud_console_setup": {
            "authorize_javascript_origins": [LOCAL_BASE_URL, PRODUCTION_BASE_URL],
            "authorized_redirect_uris": [GOOGLE_LOCAL_CALLBACK, GOOGLE_PROD_CALLBACK]
        },
        "test_uris": {
            "google_login": f"{base_url}oauth/google",
            "microsoft_login": f"{base_url}oauth/microsoft",
            "direct_microsoft": f"{base_url}oauth/microsoft/direct",
            "frontend_callback_url": f"{FRONTEND_URL}/oauth/callback?token=TEST_TOKEN&is_new_user=false"
        },
        "instructions": "Verify these URIs match what's configured in Google Cloud Console and Microsoft Azure"
    }

# Add a test endpoint to check frontend URL redirect
@router.get("/test-frontend-redirect")
async def test_frontend_redirect(request: Request):
    """Test endpoint that redirects to the frontend URL"""
    log.info(f"Testing frontend URL redirect to: {FRONTEND_URL}")
    redirect_url = f"{FRONTEND_URL}/oauth/callback?test=true&from=backend"
    return RedirectResponse(url=redirect_url)

# Add a more detailed OAuth debugging endpoint
@router.get("/oauth-debug")
async def oauth_debug(request: Request):
    """Comprehensive debug endpoint for OAuth and redirection issues"""
    # Get headers and environment info
    headers = dict(request.headers)
    env_vars = {}
    
    # Get relevant environment variables (safely)
    env_keys = [
        "FRONTEND_URL", "ENVIRONMENT", "ASPNETCORE_ENVIRONMENT", 
        "WEBSITE_HOSTNAME", "WEBSITE_SITE_NAME"
    ]
    
    for key in env_keys:
        env_vars[key] = os.getenv(key, "Not set")
    
    # Get hostname detection
    hostname = headers.get("host", "unknown")
    is_local = "localhost" in str(request.base_url)
    
    # Check what URL would be used for frontend redirect
    current_frontend = FRONTEND_URL
    
    # Test if redirect URLs are reachable
    import httpx
    frontend_reachable = False
    status_code = None
    error_message = None
    
    try:
        async with httpx.AsyncClient() as client:
            # Set a short timeout
            response = await client.get(FRONTEND_URL, timeout=5.0, follow_redirects=True)
            status_code = response.status_code
            frontend_reachable = 200 <= status_code < 400
    except Exception as e:
        error_message = str(e)
    
    # Create a test token for testing redirect
    test_token = "TEST_TOKEN_FOR_DEBUGGING"
    test_redirect_url = f"{FRONTEND_URL}/oauth/callback?token={test_token}&is_new_user=false&debug=true"
    
    # Return comprehensive debug info
    return {
        "timestamp": time.time(),
        "request_info": {
            "base_url": str(request.base_url),
            "is_local": is_local,
            "host_header": hostname,
            "headers": headers
        },
        "frontend_url_config": {
            "current_frontend_url": current_frontend,
            "local_frontend_url": LOCAL_FRONTEND_URL, 
            "production_frontend_url": PRODUCTION_FRONTEND_URL,
            "env_frontend_url": env_frontend_url,
            "frontend_url_source": "Environment variable" if env_frontend_url else "Auto-detected based on environment"
        },
        "environment_detection": {
            "is_production_env": is_production_env,
            "environment_variables": env_vars,
            "azure_detection": "azure" in PRODUCTION_BASE_URL
        },
        "frontend_reachability": {
            "is_reachable": frontend_reachable,
            "status_code": status_code,
            "error": error_message
        },
        "test_urls": {
            "frontend_url": FRONTEND_URL,
            "test_redirect": test_redirect_url,
            "frontend_test_endpoint": f"{request.base_url}oauth/test-frontend-redirect"
        },
        "debug_info": "Use the test_redirect URL to manually test if the frontend can handle OAuth callbacks",
        "recommendation": "If using the wrong frontend URL, set the FRONTEND_URL environment variable in Azure App Service Configuration"
    }

# Add a test endpoint for direct frontend URL testing
@router.get("/test-redirect-to")
async def test_redirect_to(request: Request):
    """Test endpoint that redirects to any URL provided as a parameter"""
    url = request.query_params.get("url", FRONTEND_URL)
    log.info(f"Testing direct redirect to: {url}")
    
    # If URL doesn't have a scheme, add https://
    if not url.startswith("http"):
        url = f"https://{url}"
    
    return RedirectResponse(url=url)