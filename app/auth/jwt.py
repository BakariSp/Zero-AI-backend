from datetime import datetime, timedelta
from typing import Optional
import uuid

from fastapi import Depends, HTTPException, status, APIRouter, Form, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
import os
from sqlalchemy.orm import Session

from app.users.crud import get_user_by_email, create_user, get_user_by_oauth, update_user
from app.db import SessionLocal
from app.models import User
from passlib.context import CryptContext
import logging
from app.utils.supabase import supabase_client
from app.users.schemas import UserCreate
from app.users import schemas

# Get JWT settings from environment variables or use defaults
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-for-jwt-please-change-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

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
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
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
        
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    user = get_user(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    
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
    
    logging.info(f"Successfully authenticated user: {current_user.id}")
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
        
        token_data = TokenData(email=email)
    except JWTError:
        return None
    
    user = get_user(db, email=token_data.email)
    if user is None or not user.is_active:
        return None
        
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

class SyncAnonymousUserRequest(BaseModel):
    auth_id: str

class SyncAnonymousUserResponse(BaseModel):
    status: str  # "created", "exists", "error"
    message: str
    user_id: Optional[int] = None

@router.post("/sync-anonymous-user", response_model=SyncAnonymousUserResponse)
async def sync_anonymous_user(
    request: SyncAnonymousUserRequest,
    db: Session = Depends(get_db)
):
    """
    同步匿名用户到自定义用户表
    接收前端传来的 Supabase auth_id，在自定义 users 表中创建对应记录
    """
    try:
        auth_id = request.auth_id
        
        # 验证 auth_id 格式（应该是 UUID）
        if not auth_id or len(auth_id) != 36:
            return SyncAnonymousUserResponse(
                status="error",
                message="Invalid auth_id format"
            )
        
        # 查询是否已经存在该匿名用户
        existing_user = get_user_by_oauth(db, "supabase", auth_id)
        
        if existing_user:
            logging.info(f"Anonymous user already exists: {existing_user.id}")
            return SyncAnonymousUserResponse(
                status="exists",
                message="Anonymous user already exists",
                user_id=existing_user.id
            )
        
        # 创建新的匿名用户
        try:
            # 为匿名用户生成唯一的 email 和 username
            unique_identifier = f"anonymous_{auth_id}"
            
            user_data = UserCreate(
                email=unique_identifier,
                username=unique_identifier,
                password="",  # 匿名用户不需要密码
                full_name="Anonymous User",
                is_active=True,
                subscription_type="free"
            )
            
            # 创建用户，设置为匿名用户
            new_user = create_user(
                db=db,
                user=user_data,
                oauth_provider="supabase",
                oauth_id=auth_id,
                is_guest=True
            )
            
            # 提交事务
            db.commit()
            db.refresh(new_user)
            
            logging.info(f"Successfully created anonymous user: {new_user.id} with auth_id: {auth_id}")
            
            return SyncAnonymousUserResponse(
                status="created",
                message="Anonymous user created successfully",
                user_id=new_user.id
            )
            
        except Exception as e:
            # 回滚事务
            db.rollback()
            logging.error(f"Error creating anonymous user: {str(e)}")
            
            return SyncAnonymousUserResponse(
                status="error",
                message=f"Failed to create anonymous user: {str(e)}"
            )
    
    except Exception as e:
        logging.error(f"Unexpected error in sync_anonymous_user: {str(e)}")
        return SyncAnonymousUserResponse(
            status="error",
            message="Internal server error"
        )