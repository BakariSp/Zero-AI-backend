from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status, APIRouter, Form, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
import os
from sqlalchemy.orm import Session

from app.users.crud import get_user_by_email
from app.db import SessionLocal
from app.models import User
from passlib.context import CryptContext
import logging

# Get JWT settings from environment variables or use defaults
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-for-jwt-please-change-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
# Guest tokens can be longer-lived
GUEST_TOKEN_EXPIRE_DAYS = int(os.getenv("GUEST_TOKEN_EXPIRE_DAYS", "30"))

# Create a custom OAuth2 scheme that will be skipped for OPTIONS requests
class CustomOAuth2PasswordBearer(OAuth2PasswordBearer):
    async def __call__(self, request: Request):
        # Skip token validation for OPTIONS requests
        if request.method == "OPTIONS":
            logging.info(f"OPTIONS request detected in OAuth2 scheme for path: {request.url.path}")
            logging.info(f"Skipping token validation for OPTIONS request to: {request.url.path}")
            logging.info(f"Request headers for OPTIONS: {request.headers}")
            return None
            
        # Get the Authorization header
        authorization = request.headers.get("Authorization")
        
        # Log the request path and auth status for debugging
        logging.info(f"Authentication check for path: {request.url.path}")
        logging.info(f"Authorization header present: {authorization is not None}")
        
        # If no authorization header or it doesn't start with "Bearer", return None
        # This allows get_current_user_optional to work without requiring Authorization
        if not authorization or not authorization.startswith("Bearer "):
            logging.warning(f"No valid Authorization header for path: {request.url.path}")
            return None
            
        # For standard requests with Authorization header, use the parent class implementation
        try:
            result = await super().__call__(request)
            logging.info(f"Successfully validated token for {request.url.path}")
            return result
        except Exception as e:
            logging.error(f"Error in OAuth2 scheme for path {request.url.path}: {str(e)}")
            # For get_current_user_optional, we'll return None in the function itself
            # For get_current_user, we'll let it raise the exception
            raise

oauth2_scheme = CustomOAuth2PasswordBearer(tokenUrl="/api/token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter()

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    is_guest: Optional[bool] = False

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(db, email: str):
    return get_user_by_email(db, email)

def authenticate_user(db, email: str, password: str):
    user = get_user(db, email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    
    # Use longer expiration for guest users
    if to_encode.get("is_guest"):
        default_expiry = timedelta(days=GUEST_TOKEN_EXPIRE_DAYS)
    else:
        default_expiry = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + default_expiry
        
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    # For OPTIONS requests, our custom OAuth2 scheme returns None
    if token is None:
        # Return None for OPTIONS requests, this will be handled downstream
        return None
        
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        
        # Extract guest flag from token if present
        is_guest: bool = payload.get("is_guest", False)
        token_data = TokenData(email=email, is_guest=is_guest)
    except JWTError:
        raise credentials_exception
    
    user = get_user(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    
    # Handle guest users that have been merged into regular accounts
    if user.merged_into_user_id:
        # Get the real user that this guest was merged into
        real_user = db.query(User).filter_by(id=user.merged_into_user_id).first()
        if real_user:
            logging.info(f"Guest user {user.id} has been merged into user {real_user.id}, using the real user")
            return real_user
        else:
            logging.error(f"Guest user {user.id} was merged into user {user.merged_into_user_id} but that user was not found")
            raise credentials_exception
    
    # Update last_active_at for guest users
    if user.is_guest:
        user.last_active_at = datetime.utcnow()
        db.commit()
    
    return user

async def get_current_active_user(current_user = Depends(get_current_user), request: Request = None):
    # Special handling for OPTIONS requests
    if request and request.method == "OPTIONS":
        logging.info("OPTIONS request detected in get_current_active_user")
        # For OPTIONS, we bypass authentication entirely to avoid CORS preflight issues
        return None
    
    # For debugging purposes
    if request:
        logging.info(f"Request method in get_current_active_user: {request.method}")
    
    # Handle the case when current_user is None (for other requests)
    if current_user is None:
        # Log that the user wasn't authenticated and return 401
        logging.warning("Authentication failed: current_user is None")
        logging.info(f"[Auth] Resolved current user: {current_user}")
        if request and request.method == "OPTIONS":
            logging.info("Not raising exception for OPTIONS request")
            return None
        logging.warning("Note: If this is an OPTIONS request, this exception will cause a 401 response")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not current_user.is_active:
        logging.warning(f"User {current_user.id} is inactive")
        raise HTTPException(status_code=400, detail="Inactive user")
    
    logging.info(f"Successfully authenticated user: {current_user.id} (guest: {current_user.is_guest})")
    return current_user

async def get_current_user_optional(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Similar to get_current_user but doesn't raise an exception if token is invalid or missing.
    Returns None instead, making authentication optional.
    """
    # For OPTIONS requests or if no token is provided, our custom OAuth2 scheme returns None
    if token is None:
        return None
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        
        # Extract guest flag from token if present
        is_guest: bool = payload.get("is_guest", False)
        token_data = TokenData(email=email, is_guest=is_guest)
    except JWTError:
        return None
    
    user = get_user(db, email=token_data.email)
    if user is None or not user.is_active:
        return None
    
    # Handle guest users that have been merged into regular accounts
    if user.merged_into_user_id:
        # Get the real user that this guest was merged into
        real_user = db.query(User).filter_by(id=user.merged_into_user_id).first()
        if real_user:
            return real_user
    
    # Update last_active_at for guest users
    if user.is_guest:
        user.last_active_at = datetime.utcnow()
        db.commit()
        
    return user

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    print(f"Login attempt for user: {form_data.username}")
    try:
        user = authenticate_user(db, form_data.username, form_data.password)
        if not user:
            print(f"Authentication failed for user: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )
        print(f"Authentication successful for user: {form_data.username}")
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        print(f"Error during authentication: {str(e)}")
        raise