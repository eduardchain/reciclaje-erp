"""Endpoints para gestion de roles y permisos."""
from uuid import UUID

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_required_org_context, require_permission
from app.schemas.role import (
    PermissionsByModule,
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleListItem,
    PermissionResponse,
    UserRoleAssignment,
    MyPermissionsResponse,
)
from app.services.role import role_service

router = APIRouter()


@router.get(
    "/permissions",
    response_model=list[PermissionsByModule],
    summary="Listar permisos agrupados por modulo",
)
def list_permissions(
    ctx: dict = Depends(require_permission("admin.manage_roles")),
    db: Session = Depends(get_db),
) -> list[PermissionsByModule]:
    """Obtener todos los permisos del sistema agrupados por modulo."""
    modules = role_service.get_permissions_by_module(db)
    return [
        PermissionsByModule(
            module=m["module"],
            module_display=m["module_display"],
            permissions=[PermissionResponse.model_validate(p) for p in m["permissions"]],
        )
        for m in modules
    ]


@router.get(
    "/my-permissions",
    response_model=MyPermissionsResponse,
    summary="Mis permisos en esta organizacion",
)
def get_my_permissions(
    ctx: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
) -> MyPermissionsResponse:
    """Obtener rol y permisos del usuario actual."""
    from app.services.organization import get_user_account_assignments

    # Determinar display_name del rol
    if ctx["user_role_id"]:
        # Usuario normal con membership: cargar rol de DB
        role = role_service.get_role_by_id(db, ctx["user_role_id"], ctx["organization_id"])
        display_name = role.display_name if role else ctx["user_role"]
    else:
        # Superuser sin membership: usar nombre del contexto
        display_name = "Super Admin"

    # Permisos: usar los ya resueltos por deps.py (respeta superuser bypass)
    perms = ctx["user_permissions"]

    acc_ids = get_user_account_assignments(db, ctx["user_id"], ctx["organization_id"])

    return MyPermissionsResponse(
        role_id=ctx["user_role_id"],
        role_name=ctx["user_role"],
        role_display_name=display_name,
        is_admin=ctx["is_admin"],
        permissions=sorted(perms),
        assigned_account_ids=[str(a) for a in acc_ids],
    )


@router.get(
    "",
    response_model=list[RoleListItem],
    summary="Listar roles de la organizacion",
)
def list_roles(
    ctx: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
) -> list[RoleListItem]:
    """Listar todos los roles de la organizacion con conteos."""
    roles = role_service.get_roles_by_org(db, ctx["organization_id"])
    return [RoleListItem(**r) for r in roles]


@router.get(
    "/{role_id}",
    response_model=RoleResponse,
    summary="Detalle de un rol",
)
def get_role(
    role_id: UUID,
    ctx: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
) -> RoleResponse:
    """Obtener detalle de un rol con sus permisos."""
    role = role_service.get_role_by_id(db, role_id, ctx["organization_id"])
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rol no encontrado",
        )

    perms = [
        PermissionResponse.model_validate(rp.permission)
        for rp in role.permissions
    ]

    return RoleResponse(
        id=role.id,
        organization_id=role.organization_id,
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        is_system_role=role.is_system_role,
        created_at=role.created_at,
        updated_at=role.updated_at,
        permissions=perms,
    )


@router.post(
    "",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear rol personalizado",
)
def create_role(
    role_in: RoleCreate,
    ctx: dict = Depends(require_permission("admin.manage_roles")),
    db: Session = Depends(get_db),
) -> RoleResponse:
    """Crear un nuevo rol personalizado para la organizacion."""
    try:
        role = role_service.create_role(db, ctx["organization_id"], role_in)
        # Reload con permisos
        role = role_service.get_role_by_id(db, role.id, ctx["organization_id"])
        perms = [
            PermissionResponse.model_validate(rp.permission)
            for rp in role.permissions
        ]
        return RoleResponse(
            id=role.id,
            organization_id=role.organization_id,
            name=role.name,
            display_name=role.display_name,
            description=role.description,
            is_system_role=role.is_system_role,
            created_at=role.created_at,
            updated_at=role.updated_at,
            permissions=perms,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch(
    "/{role_id}",
    response_model=RoleResponse,
    summary="Actualizar rol",
)
def update_role(
    role_id: UUID,
    role_in: RoleUpdate,
    ctx: dict = Depends(require_permission("admin.manage_roles")),
    db: Session = Depends(get_db),
) -> RoleResponse:
    """Actualizar un rol (display_name, description, permisos)."""
    role = role_service.update_role(db, role_id, ctx["organization_id"], role_in)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rol no encontrado",
        )

    role = role_service.get_role_by_id(db, role.id, ctx["organization_id"])
    perms = [
        PermissionResponse.model_validate(rp.permission)
        for rp in role.permissions
    ]
    return RoleResponse(
        id=role.id,
        organization_id=role.organization_id,
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        is_system_role=role.is_system_role,
        created_at=role.created_at,
        updated_at=role.updated_at,
        permissions=perms,
    )


@router.delete(
    "/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar rol",
)
def delete_role(
    role_id: UUID,
    reassign_to: Optional[UUID] = Query(None, description="Rol al que reasignar usuarios"),
    ctx: dict = Depends(require_permission("admin.manage_roles")),
    db: Session = Depends(get_db),
) -> None:
    """Eliminar un rol. Si tiene usuarios, reasignarlos a otro rol."""
    try:
        deleted = role_service.delete_role(
            db, role_id, ctx["organization_id"], reassign_to=reassign_to
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rol no encontrado",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{role_id}/assign",
    status_code=status.HTTP_200_OK,
    summary="Asignar rol a usuario",
)
def assign_role(
    role_id: UUID,
    assignment: UserRoleAssignment,
    ctx: dict = Depends(require_permission("admin.manage_users")),
    db: Session = Depends(get_db),
) -> dict:
    """Asignar un rol a un usuario en la organizacion."""
    from app.services.organization import update_member_role

    try:
        membership = update_member_role(
            db, ctx["organization_id"], assignment.user_id, assignment.role_id
        )
        return {"message": "Rol asignado correctamente"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
