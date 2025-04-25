from fastapi import Depends, HTTPException, status, APIRouter
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from starlette.requests import Request
from fastapi.responses import RedirectResponse
import os

from app.users.crud import get_user_by_oauth, create_user, get_user_by_username
from app.db import SessionLocal
from app.auth.jwt import create_access_token
from app.users.schemas import UserCreate

# Create router
router = APIRouter()

# Load environment variables
config = Config(".env")

# Configure OAuth
oauth = OAuth(config)

# Configure Microsoft OAuth
oauth.register(
    name="microsoft",
    client_id=os.getenv("MICROSOFT_CLIENT_ID", ""),
    client_secret=os.getenv("MICROSOFT_CLIENT_SECRET", ""),
    server_metadata_url="https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# Configure Google OAuth
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# OAuth login routes
@router.get("/google")
async def login_via_google(request: Request):
    """Initiate Google OAuth login flow"""
    redirect_uri = str(request.url_for('auth_via_google'))
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/google/callback", name="auth_via_google")
async def auth_via_google(request: Request):
    """Handle Google OAuth callback"""
    user = await get_oauth_user("google", request)
    
    # Create access token
    access_token = create_access_token(data={"sub": user.email})
    
    # Redirect to frontend with token
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    redirect_url = f"{frontend_url}/oauth/callback?token={access_token}"
    
    return RedirectResponse(url=redirect_url)

@router.get("/microsoft")
async def login_via_microsoft(request: Request):
    """Initiate Microsoft OAuth login flow"""
    redirect_uri = str(request.url_for('auth_via_microsoft'))
    return await oauth.microsoft.authorize_redirect(request, redirect_uri)

@router.get("/microsoft/callback", name="auth_via_microsoft")
async def auth_via_microsoft(request: Request):
    """Handle Microsoft OAuth callback"""
    user = await get_oauth_user("microsoft", request)
    
    # Create access token
    access_token = create_access_token(data={"sub": user.email})
    
    # Redirect to frontend with token
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    redirect_url = f"{frontend_url}/oauth/callback?token={access_token}"
    
    return RedirectResponse(url=redirect_url)

async def get_oauth_user(provider: str, request: Request):
    """
    Get user information from OAuth provider and create/update user in database
    """
    if provider not in oauth._clients:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OAuth provider: {provider}"
        )
    
    client = oauth._clients[provider]
    token = await client.authorize_access_token(request)
    
    user_info = {}
    
    if provider == "google":
        user_info = token.get("userinfo")
        oauth_id = user_info.get("sub")
        email = user_info.get("email")
        name = user_info.get("name")
        picture = user_info.get("picture")
    
    elif provider == "microsoft":
        # Get user info from Microsoft Graph API
        resp = await client.get("https://graph.microsoft.com/v1.0/me")
        user_info = resp.json()
        oauth_id = user_info.get("id")
        email = user_info.get("mail") or user_info.get("userPrincipalName")
        name = user_info.get("displayName")
        picture = None  # Microsoft Graph API doesn't provide profile picture in basic response
    
    if not oauth_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not retrieve user information from OAuth provider"
        )
    
    # Check if user exists in database
    db = SessionLocal()
    try:
        user = get_user_by_oauth(db, provider=provider, oauth_id=oauth_id)
        
        # If user doesn't exist, create a new one
        if not user:
            # Generate a username from email if not available
            username = email.split("@")[0]
            
            # Check if username exists and append numbers if needed
            base_username = username
            counter = 1
            while get_user_by_username(db, username):
                username = f"{base_username}{counter}"
                counter += 1
            
            # Create a new user object with the correct parameters
            # Based on the error, we need to adjust how we call create_user
            
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
    finally:
        db.close()
    
    return user