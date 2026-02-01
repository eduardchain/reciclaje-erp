from typing import Generator
from uuid import UUID

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.services.user import get_user_by_id
from app.services.organization import get_user_role_in_org
from app.models.user import User

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get database session.
    Yields a new database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Get current authenticated user from JWT token.
    
    Args:
        token: JWT token from Authorization header
        db: Database session
        
    Returns:
        Current User object
        
    Raises:
        HTTPException: 401 if token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Decode token to get user_id
    user_id_str = decode_access_token(token)
    
    if user_id_str is None:
        raise credentials_exception
    
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise credentials_exception
    
    # Get user from database
    user = get_user_by_id(db, user_id)
    
    if user is None:
        raise credentials_exception
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current active user (must be active).
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current active User object
        
    Raises:
        HTTPException: 403 if user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Get current superuser (must be active and superuser).
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current superuser User object
        
    Raises:
        HTTPException: 403 if user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    return current_user


# Organization Context Dependencies


async def get_required_org_context(
    x_organization_id: str = Header(..., alias="X-Organization-ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get organization context from header (REQUIRED).
    Use this dependency for endpoints that operate within a specific organization
    (e.g., materials, purchases, sales, inventory).
    
    Validates:
    - Header contains valid UUID
    - User is a member of the organization
    - Returns user's role in that organization
    
    Args:
        x_organization_id: Organization ID from X-Organization-ID header
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Dictionary with organization_id, user_id, user_role, and user object
        
    Raises:
        HTTPException: 400 if invalid UUID format
        HTTPException: 403 if user is not a member of the organization
    """
    # Validate UUID format
    try:
        org_uuid = UUID(x_organization_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid organization ID format. Must be a valid UUID.",
        )
    
    # Get user's role in organization
    # NOTE: This makes a DB query on every request
    # In Phase 2, we will cache this with Redis
    role = get_user_role_in_org(db, org_uuid, current_user.id)
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization",
        )
    
    return {
        "organization_id": org_uuid,
        "user_id": current_user.id,
        "user_role": role,
        "user": current_user,
    }


async def get_optional_org_context(
    x_organization_id: str | None = Header(None, alias="X-Organization-ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict | None:
    """
    Get organization context from header (OPTIONAL).
    Use this dependency for endpoints that can work with or without organization context
    (e.g., listing user's organizations, creating organization).
    
    If header is provided:
    - Validates UUID format
    - Validates user is member
    - Returns context dict
    
    If header is NOT provided:
    - Returns None
    
    Args:
        x_organization_id: Optional organization ID from header
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Dictionary with context or None if header not provided
        
    Raises:
        HTTPException: 400 if invalid UUID format (only if header provided)
        HTTPException: 403 if not member (only if header provided)
    """
    if not x_organization_id:
        return None
    
    # Validate UUID format
    try:
        org_uuid = UUID(x_organization_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid organization ID format. Must be a valid UUID.",
        )
    
    # Get user's role in organization
    role = get_user_role_in_org(db, org_uuid, current_user.id)
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization",
        )
    
    return {
        "organization_id": org_uuid,
        "user_id": current_user.id,
        "user_role": role,
        "user": current_user,
    }
