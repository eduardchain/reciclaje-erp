"""Endpoints de super admin para gestion global del sistema."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, get_current_superuser
from app.core.security import get_password_hash
from app.models.organization import Organization
from app.models.user import User, OrganizationMember
from app.models.role import Role
from app.schemas.system import (
    SystemOrgCreate,
    SystemOrgUpdate,
    SystemOrgResponse,
    SystemUserResponse,
    SystemUserMembership,
    AddUserToOrgRequest,
)
from app.schemas.organization import OrganizationCreate
from app.services.organization import create_organization, add_member

router = APIRouter()


# ---------------------------------------------------------------------------
# Organizaciones
# ---------------------------------------------------------------------------

@router.get("/organizations", response_model=list[SystemOrgResponse])
def list_all_organizations(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    _su: User = Depends(get_current_superuser),
):
    """Listar todas las organizaciones del sistema."""
    query = db.query(Organization)
    if not include_inactive:
        query = query.filter(Organization.is_active == True)
    orgs = query.order_by(Organization.name).all()

    # Contar miembros por org
    member_counts = dict(
        db.query(
            OrganizationMember.organization_id,
            func.count(OrganizationMember.id),
        ).group_by(OrganizationMember.organization_id).all()
    )

    return [
        SystemOrgResponse(
            id=org.id,
            name=org.name,
            slug=org.slug,
            subscription_plan=org.subscription_plan,
            subscription_status=org.subscription_status,
            max_users=org.max_users,
            is_active=org.is_active,
            member_count=member_counts.get(org.id, 0),
            created_at=org.created_at,
        )
        for org in orgs
    ]


@router.post("/organizations", response_model=SystemOrgResponse, status_code=201)
def create_system_organization(
    data: SystemOrgCreate,
    db: Session = Depends(get_db),
    _su: User = Depends(get_current_superuser),
):
    """Crear organizacion con admin inicial (usuario existente o nuevo)."""
    # Buscar o crear usuario admin
    admin_user = db.query(User).filter(User.email == data.admin_email).first()
    if not admin_user:
        if not data.admin_full_name:
            raise HTTPException(
                status_code=400,
                detail="admin_full_name es requerido cuando el email no existe",
            )
        admin_user = User(
            email=data.admin_email,
            hashed_password=get_password_hash("123456"),
            full_name=data.admin_full_name,
            is_active=True,
        )
        db.add(admin_user)
        db.flush()

    # Crear org usando servicio existente (seed roles + membership)
    org_create = OrganizationCreate(name=data.name)
    org = create_organization(db, org_create, admin_user.id)

    member_count = db.query(func.count(OrganizationMember.id)).filter(
        OrganizationMember.organization_id == org.id
    ).scalar()

    return SystemOrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        subscription_plan=org.subscription_plan,
        subscription_status=org.subscription_status,
        max_users=org.max_users,
        is_active=org.is_active,
        member_count=member_count,
        created_at=org.created_at,
    )


@router.patch("/organizations/{org_id}", response_model=SystemOrgResponse)
def update_system_organization(
    org_id: UUID,
    data: SystemOrgUpdate,
    db: Session = Depends(get_db),
    _su: User = Depends(get_current_superuser),
):
    """Actualizar organizacion (nombre, plan, estado, etc)."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organizacion no encontrada")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(org, field, value)

    db.commit()
    db.refresh(org)

    member_count = db.query(func.count(OrganizationMember.id)).filter(
        OrganizationMember.organization_id == org.id
    ).scalar()

    return SystemOrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        subscription_plan=org.subscription_plan,
        subscription_status=org.subscription_status,
        max_users=org.max_users,
        is_active=org.is_active,
        member_count=member_count,
        created_at=org.created_at,
    )


@router.delete("/organizations/{org_id}", status_code=200)
def delete_system_organization(
    org_id: UUID,
    db: Session = Depends(get_db),
    _su: User = Depends(get_current_superuser),
):
    """Soft delete: desactivar org y usuarios huerfanos."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organizacion no encontrada")

    # No permitir eliminar la ultima org activa
    active_count = db.query(func.count(Organization.id)).filter(
        Organization.is_active == True
    ).scalar()
    if active_count <= 1 and org.is_active:
        raise HTTPException(
            status_code=400,
            detail="No se puede desactivar la unica organizacion activa",
        )

    org.is_active = False

    # Desactivar usuarios que solo pertenecen a esta org
    members = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org_id
    ).all()
    orphaned = 0
    for member in members:
        other_count = db.query(func.count(OrganizationMember.id)).filter(
            OrganizationMember.user_id == member.user_id,
            OrganizationMember.organization_id != org_id,
        ).scalar()
        if other_count == 0:
            user = db.query(User).filter(User.id == member.user_id).first()
            if user:
                user.is_active = False
                orphaned += 1

    db.commit()
    return {
        "message": f"Organizacion '{org.name}' desactivada",
        "orphaned_users_deactivated": orphaned,
    }


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------

@router.get("/users", response_model=list[SystemUserResponse])
def list_all_users(
    db: Session = Depends(get_db),
    _su: User = Depends(get_current_superuser),
):
    """Listar todos los usuarios del sistema con sus memberships."""
    users = db.query(User).order_by(User.email).all()

    # Cargar memberships con org y role info
    memberships_query = (
        db.query(OrganizationMember)
        .options(
            joinedload(OrganizationMember.organization),
            joinedload(OrganizationMember.role),
        )
        .all()
    )

    # Agrupar por user_id
    user_memberships: dict[UUID, list[SystemUserMembership]] = {}
    for m in memberships_query:
        if m.user_id not in user_memberships:
            user_memberships[m.user_id] = []
        user_memberships[m.user_id].append(
            SystemUserMembership(
                organization_id=m.organization_id,
                organization_name=m.organization.name if m.organization else "—",
                role_name=m.role.name if m.role else "—",
                role_display_name=m.role.display_name if m.role else "—",
            )
        )

    return [
        SystemUserResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            is_superuser=u.is_superuser,
            created_at=u.created_at,
            memberships=user_memberships.get(u.id, []),
        )
        for u in users
    ]


@router.post("/users/{user_id}/add-to-org", status_code=201)
def add_user_to_organization(
    user_id: UUID,
    data: AddUserToOrgRequest,
    db: Session = Depends(get_db),
    _su: User = Depends(get_current_superuser),
):
    """Agregar usuario existente a una organizacion con un rol."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    org = db.query(Organization).filter(
        Organization.id == data.organization_id,
        Organization.is_active == True,
    ).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organizacion no encontrada o inactiva")

    # Verificar que no sea ya miembro
    existing = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == user_id,
        OrganizationMember.organization_id == data.organization_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="El usuario ya es miembro de esta organizacion")

    # Verificar que el rol pertenece a la org
    role = db.query(Role).filter(
        Role.id == data.role_id,
        Role.organization_id == data.organization_id,
    ).first()
    if not role:
        raise HTTPException(status_code=400, detail="Rol no encontrado en esta organizacion")

    member = OrganizationMember(
        user_id=user_id,
        organization_id=data.organization_id,
        role_id=data.role_id,
    )
    db.add(member)
    db.commit()

    return {"message": f"Usuario '{user.email}' agregado a '{org.name}' como {role.display_name}"}
