from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user
from app.core.security import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.schemas.user import UserCreate, UserResponse, UserLogin, Token
from app.services.user import create_user, authenticate_user, get_user_by_email
from app.models.user import User

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account",
)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
) -> User:
    """
    Register a new user.
    
    - **email**: Valid email address (unique)
    - **password**: Password (minimum 8 characters)
    - **full_name**: Optional full name
    """
    # Check if user already exists
    existing_user = get_user_by_email(db, user_data.email)
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Create new user
    user = create_user(db, user_data)
    
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Login",
    description="Login with email and password to get access token",
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> dict:
    """
    Login with email and password.
    
    - **username**: Email address (OAuth2 spec uses 'username')
    - **password**: User password
    
    Returns JWT access token.
    """
    # Authenticate user
    user = authenticate_user(db, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires,
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post(
    "/login/json",
    response_model=Token,
    summary="Login with JSON",
    description="Login with JSON body (alternative to form data)",
)
def login_json(
    user_data: UserLogin,
    db: Session = Depends(get_db),
) -> dict:
    """
    Login with JSON body.
    
    - **email**: Email address
    - **password**: User password
    
    Returns JWT access token.
    """
    # Authenticate user
    user = authenticate_user(db, user_data.email, user_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires,
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get current authenticated user profile",
)
def get_me(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Get current user profile.
    
    Requires valid authentication token.
    """
    return current_user
