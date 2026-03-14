from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user, get_optional_org_context
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    OrganizationMemberCreate,
    OrganizationMemberUpdate,
    OrganizationMemberResponse,
    AccountAssignmentsUpdate,
)
from app.services.organization import (
    create_organization,
    get_organization,
    get_user_organizations,
    add_member,
    remove_member,
    update_member_role,
    get_organization_members,
    get_user_role_in_org,
    update_organization,
    get_user_account_assignments,
    update_user_account_assignments,
)
from app.models.user import User

router = APIRouter()


@router.get(
    "",
    response_model=list[OrganizationResponse],
    summary="List user's organizations",
)
def list_user_organizations(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> list[OrganizationResponse]:
    """Get all organizations where current user is a member."""
    org_list = get_user_organizations(db, current_user.id)

    response = []
    for org, role_display_name in org_list:
        org_dict = OrganizationResponse.model_validate(org).model_dump()
        org_dict["member_role"] = role_display_name
        response.append(OrganizationResponse(**org_dict))

    return response


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create organization",
)
def create_new_organization(
    org_data: OrganizationCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    """Create a new organization. Current user becomes admin."""
    try:
        organization = create_organization(db, org_data, current_user.id)

        org_dict = OrganizationResponse.model_validate(organization).model_dump()
        org_dict["member_role"] = "admin"

        return OrganizationResponse(**org_dict)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{organization_id}",
    response_model=OrganizationResponse,
    summary="Get organization",
)
def get_organization_by_id(
    organization_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    """Get organization details. User must be a member."""
    organization = get_organization(db, organization_id, current_user.id)

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacion no encontrada o no eres miembro",
        )

    role_info = get_user_role_in_org(db, organization_id, current_user.id)

    org_dict = OrganizationResponse.model_validate(organization).model_dump()
    org_dict["member_role"] = role_info["role_name"] if role_info else None

    return OrganizationResponse(**org_dict)


@router.patch(
    "/{organization_id}",
    response_model=OrganizationResponse,
    summary="Update organization",
)
def update_organization_details(
    organization_id: UUID,
    org_data: OrganizationUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    """Update organization details. Only admins can update."""
    role_info = get_user_role_in_org(db, organization_id, current_user.id)

    if not role_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacion no encontrada o no eres miembro",
        )

    if not role_info["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden actualizar la organizacion",
        )

    try:
        organization = update_organization(db, organization_id, org_data)

        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organizacion no encontrada",
            )

        org_dict = OrganizationResponse.model_validate(organization).model_dump()
        org_dict["member_role"] = role_info["role_name"]

        return OrganizationResponse(**org_dict)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{organization_id}/members",
    response_model=list[OrganizationMemberResponse],
    summary="List organization members",
)
def list_organization_members(
    organization_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> list[OrganizationMemberResponse]:
    """Get all members of an organization with their details."""
    role_info = get_user_role_in_org(db, organization_id, current_user.id)

    if not role_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacion no encontrada o no eres miembro",
        )

    members_list = get_organization_members(db, organization_id)

    response = []
    for member, user in members_list:
        acc_ids = get_user_account_assignments(db, member.user_id, organization_id)
        member_dict = {
            "id": member.id,
            "user_id": member.user_id,
            "organization_id": member.organization_id,
            "role_id": member.role_id,
            "role_name": member.role.name if member.role else None,
            "role_display_name": member.role.display_name if member.role else None,
            "joined_at": member.joined_at,
            "user_email": user.email,
            "user_full_name": user.full_name,
            "account_ids": acc_ids,
        }
        response.append(OrganizationMemberResponse(**member_dict))

    return response


@router.post(
    "/{organization_id}/members",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add member",
)
def add_organization_member(
    organization_id: UUID,
    member_data: OrganizationMemberCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> OrganizationMemberResponse:
    """Add a user to the organization. Only admins can add members."""
    role_info = get_user_role_in_org(db, organization_id, current_user.id)

    if not role_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacion no encontrada o no eres miembro",
        )

    if not role_info["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden agregar miembros",
        )

    try:
        membership = add_member(db, organization_id, member_data.user_id, member_data.role_id)

        from app.services.user import get_user_by_id
        user = get_user_by_id(db, member_data.user_id)

        member_dict = {
            "id": membership.id,
            "user_id": membership.user_id,
            "organization_id": membership.organization_id,
            "role_id": membership.role_id,
            "role_name": membership.role.name if membership.role else None,
            "role_display_name": membership.role.display_name if membership.role else None,
            "joined_at": membership.joined_at,
            "user_email": user.email if user else None,
            "user_full_name": user.full_name if user else None,
        }

        return OrganizationMemberResponse(**member_dict)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch(
    "/{organization_id}/members/{user_id}",
    response_model=OrganizationMemberResponse,
    summary="Update member role",
)
def update_organization_member_role(
    organization_id: UUID,
    user_id: UUID,
    role_data: OrganizationMemberUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> OrganizationMemberResponse:
    """Update a member's role. Only admins can update roles."""
    current_role_info = get_user_role_in_org(db, organization_id, current_user.id)

    if not current_role_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacion no encontrada o no eres miembro",
        )

    if not current_role_info["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden cambiar roles",
        )

    try:
        membership = update_member_role(db, organization_id, user_id, role_data.role_id)

        from app.services.user import get_user_by_id
        user = get_user_by_id(db, user_id)

        member_dict = {
            "id": membership.id,
            "user_id": membership.user_id,
            "organization_id": membership.organization_id,
            "role_id": membership.role_id,
            "role_name": membership.role.name if membership.role else None,
            "role_display_name": membership.role.display_name if membership.role else None,
            "joined_at": membership.joined_at,
            "user_email": user.email if user else None,
            "user_full_name": user.full_name if user else None,
        }

        return OrganizationMemberResponse(**member_dict)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{organization_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove member",
)
def remove_organization_member(
    organization_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> None:
    """Remove a user from the organization. Only admins can remove members."""
    current_role_info = get_user_role_in_org(db, organization_id, current_user.id)

    if not current_role_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacion no encontrada o no eres miembro",
        )

    if not current_role_info["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden remover miembros",
        )

    try:
        remove_member(db, organization_id, user_id)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{organization_id}/leave",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Leave organization",
)
def leave_organization(
    organization_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> None:
    """Current user leaves the organization. Cannot leave if last admin."""
    role_info = get_user_role_in_org(db, organization_id, current_user.id)

    if not role_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacion no encontrada o no eres miembro",
        )

    try:
        remove_member(db, organization_id, current_user.id)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put(
    "/{organization_id}/members/{user_id}/account-assignments",
    response_model=list[str],
    summary="Update account assignments",
)
def update_account_assignments(
    organization_id: UUID,
    user_id: UUID,
    data: AccountAssignmentsUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> list[str]:
    """Actualizar cuentas asignadas a un usuario. Solo admins."""
    current_role_info = get_user_role_in_org(db, organization_id, current_user.id)

    if not current_role_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacion no encontrada o no eres miembro",
        )

    if not current_role_info["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden asignar cuentas",
        )

    # Verificar que el usuario es miembro
    target_role = get_user_role_in_org(db, organization_id, user_id)
    if not target_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no es miembro de esta organizacion",
        )

    result = update_user_account_assignments(db, user_id, organization_id, data.account_ids)
    return [str(aid) for aid in result]
