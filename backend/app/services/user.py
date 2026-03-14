from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import get_password_hash, verify_password


def get_user_by_email(db: Session, email: str) -> User | None:
    """
    Get a user by email address.
    
    Args:
        db: Database session
        email: User email address
        
    Returns:
        User object if found, None otherwise
    """
    statement = select(User).where(User.email == email)
    result = db.execute(statement)
    return result.scalar_one_or_none()


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    """
    Get a user by ID.
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        User object if found, None otherwise
    """
    statement = select(User).where(User.id == user_id)
    result = db.execute(statement)
    return result.scalar_one_or_none()


def create_user(db: Session, user: UserCreate, organization_id: UUID | None = None) -> User:
    """
    Create a new user.
    
    Args:
        db: Database session
        user: User creation schema
        organization_id: Optional organization ID for multi-tenant
        
    Returns:
        Created User object
    """
    hashed_password = get_password_hash(user.password)
    
    db_user = User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name,
        is_active=True,
        is_superuser=False,
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # If organization_id provided, create organization membership
    if organization_id:
        from app.models.user import OrganizationMember
        
        membership = OrganizationMember(
            user_id=db_user.id,
            organization_id=organization_id,
            role="user",
        )
        db.add(membership)
        db.commit()
    
    return db_user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """
    Authenticate a user with email and password.
    
    Args:
        db: Database session
        email: User email address
        password: Plain text password
        
    Returns:
        User object if authentication successful, None otherwise
    """
    user = get_user_by_email(db, email)
    
    if not user:
        return None
    
    if not verify_password(password, user.hashed_password):
        return None
    
    return user


def reset_password(db: Session, user_id: UUID) -> User | None:
    """Resetear contraseña a '123456'."""
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    user.hashed_password = get_password_hash("123456")
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: UUID) -> bool:
    """Eliminar usuario. Hard delete si no tiene datos, soft delete si tiene FKs."""
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    try:
        db.delete(user)
        db.flush()
        db.commit()
    except Exception:
        db.rollback()
        # FK constraint — desactivar en vez de eliminar
        user = get_user_by_id(db, user_id)
        if user:
            user.is_active = False
            db.commit()
    return True


def update_user(db: Session, user_id: UUID, **kwargs) -> User | None:
    """
    Update user attributes.
    
    Args:
        db: Database session
        user_id: User UUID
        **kwargs: Attributes to update
        
    Returns:
        Updated User object if found, None otherwise
    """
    user = get_user_by_id(db, user_id)
    
    if not user:
        return None
    
    for key, value in kwargs.items():
        if hasattr(user, key):
            setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    
    return user
