from typing import Generator
from uuid import UUID

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.services.user import get_user_by_id
from app.services.organization import get_user_role_in_org
from app.services.role import role_service
from app.models.user import User
from app.models.organization import Organization

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
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id_str = decode_access_token(token)

    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    user = get_user_by_id(db, user_id)

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current active user (must be active).
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
    Validates user is member and loads role + permissions.

    Returns dict with:
        organization_id, user_id, user_role, user_role_id,
        user_permissions, is_admin, user
    """
    # Validate UUID format
    try:
        org_uuid = UUID(x_organization_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de ID de organizacion invalido. Debe ser un UUID valido.",
        )

    # Superuser siempre tiene acceso total a cualquier org
    if current_user.is_superuser:
        return _build_superuser_context(db, org_uuid, current_user)

    # Get user's role info
    role_info = get_user_role_in_org(db, org_uuid, current_user.id)

    if not role_info:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No eres miembro de esta organizacion",
        )

    # Load permissions
    role, perms = role_service.get_user_permissions(db, current_user.id, org_uuid)

    return {
        "organization_id": org_uuid,
        "user_id": current_user.id,
        "user_role": role_info["role_name"],
        "user_role_id": role_info["role_id"],
        "user_permissions": perms,
        "is_admin": role_info["is_admin"],
        "user": current_user,
    }


def _build_superuser_context(db: Session, org_uuid: UUID, user: User) -> dict:
    """Sintetiza contexto admin para superuser sin membership."""
    org = db.query(Organization).filter(
        Organization.id == org_uuid,
        Organization.is_active == True,
    ).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacion no encontrada o inactiva",
        )
    all_perms = role_service.get_all_permission_codes(db)
    return {
        "organization_id": org_uuid,
        "user_id": user.id,
        "user_role": "superadmin",
        "user_role_id": None,
        "user_permissions": all_perms,
        "is_admin": True,
        "user": user,
    }


async def get_optional_org_context(
    x_organization_id: str | None = Header(None, alias="X-Organization-ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict | None:
    """
    Get organization context from header (OPTIONAL).
    Returns None if header not provided.
    """
    if not x_organization_id:
        return None

    # Validate UUID format
    try:
        org_uuid = UUID(x_organization_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de ID de organizacion invalido. Debe ser un UUID valido.",
        )

    # Superuser siempre tiene acceso total
    if current_user.is_superuser:
        return _build_superuser_context(db, org_uuid, current_user)

    # Get user's role info
    role_info = get_user_role_in_org(db, org_uuid, current_user.id)

    if not role_info:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No eres miembro de esta organizacion",
        )

    role, perms = role_service.get_user_permissions(db, current_user.id, org_uuid)

    return {
        "organization_id": org_uuid,
        "user_id": current_user.id,
        "user_role": role_info["role_name"],
        "user_role_id": role_info["role_id"],
        "user_permissions": perms,
        "is_admin": role_info["is_admin"],
        "user": current_user,
    }


def require_permission(*perms: str):
    """
    Factory que retorna un Depends que verifica permisos.
    Admin bypassa todos los permisos.

    Uso:
        @router.post("")
        async def create_purchase(..., ctx=Depends(require_permission("purchases.create"))):
    """
    async def checker(
        org_context: dict = Depends(get_required_org_context),
    ) -> dict:
        if org_context["is_admin"]:
            return org_context

        missing = set(perms) - org_context["user_permissions"]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permisos insuficientes: {', '.join(sorted(missing))}",
            )
        return org_context

    return checker


def require_any_permission(*perms: str):
    """
    Factory que retorna un Depends que verifica que el usuario tenga AL MENOS UNO
    de los permisos dados (logica OR). Admin bypassa todos los permisos.

    Uso:
        @router.get("")
        async def list_items(..., ctx=Depends(require_any_permission("module.view", "module.view_sub"))):
    """
    async def checker(
        org_context: dict = Depends(get_required_org_context),
    ) -> dict:
        if org_context["is_admin"]:
            return org_context

        if not org_context["user_permissions"].intersection(perms):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permisos insuficientes: necesita al menos uno de {', '.join(sorted(perms))}",
            )
        return org_context

    return checker
