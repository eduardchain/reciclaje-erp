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
)
from app.models.user import User

router = APIRouter()


@router.get(
    "",
    response_model=list[OrganizationResponse],
    summary="List user's organizations",
    description="Get all organizations where the current user is a member, with their role in each",
)
def list_user_organizations(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> list[OrganizationResponse]:
    """
    Get all organizations where current user is a member.
    Returns organization details with user's role in each.
    """
    org_list = get_user_organizations(db, current_user.id)
    
    # Convert to response format
    response = []
    for org, role in org_list:
        org_dict = OrganizationResponse.model_validate(org).model_dump()
        org_dict["member_role"] = role
        response.append(OrganizationResponse(**org_dict))
    
    return response


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create organization",
    description="Create a new organization. User becomes admin automatically.",
)
def create_new_organization(
    org_data: OrganizationCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    """
    Create a new organization.
    The current user is automatically added as an admin.
    """
    try:
        organization = create_organization(db, org_data, current_user.id)
        
        # Add member_role to response
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
    description="Get organization details. Requires membership.",
)
def get_organization_by_id(
    organization_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    """
    Get organization details.
    User must be a member of the organization.
    """
    organization = get_organization(db, organization_id, current_user.id)
    
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacion no encontrada o no eres miembro",
        )
    
    # Get user's role
    role = get_user_role_in_org(db, organization_id, current_user.id)
    
    # Add member_role to response
    org_dict = OrganizationResponse.model_validate(organization).model_dump()
    org_dict["member_role"] = role
    
    return OrganizationResponse(**org_dict)


@router.patch(
    "/{organization_id}",
    response_model=OrganizationResponse,
    summary="Update organization",
    description="Update organization details. Requires admin role.",
)
def update_organization_details(
    organization_id: UUID,
    org_data: OrganizationUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    """
    Update organization details.
    Only admins can update organizations.
    """
    # Check user is member and get role
    role = get_user_role_in_org(db, organization_id, current_user.id)
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacion no encontrada o no eres miembro",
        )
    
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update organization details",
        )
    
    try:
        organization = update_organization(db, organization_id, org_data)
        
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organizacion no encontrada",
            )
        
        # Add member_role to response
        org_dict = OrganizationResponse.model_validate(organization).model_dump()
        org_dict["member_role"] = role
        
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
    description="Get all members of an organization. Requires membership.",
)
def list_organization_members(
    organization_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> list[OrganizationMemberResponse]:
    """
    Get all members of an organization with their details.
    User must be a member of the organization.
    """
    # Check user is member
    role = get_user_role_in_org(db, organization_id, current_user.id)
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacion no encontrada o no eres miembro",
        )
    
    members_list = get_organization_members(db, organization_id)
    
    # Convert to response format
    response = []
    for member, user in members_list:
        member_dict = {
            "id": member.id,
            "user_id": member.user_id,
            "organization_id": member.organization_id,
            "role": member.role,
            "joined_at": member.joined_at,
            "user_email": user.email,
            "user_full_name": user.full_name,
        }
        response.append(OrganizationMemberResponse(**member_dict))
    
    return response


@router.post(
    "/{organization_id}/members",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add member",
    description="Add a user to the organization. Requires admin role.",
)
def add_organization_member(
    organization_id: UUID,
    member_data: OrganizationMemberCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> OrganizationMemberResponse:
    """
    Add a user to the organization with specified role.
    Only admins can add members.
    Validates max_users limit.
    """
    # Check user is admin
    role = get_user_role_in_org(db, organization_id, current_user.id)
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacion no encontrada o no eres miembro",
        )
    
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can add members",
        )
    
    try:
        membership = add_member(db, organization_id, member_data.user_id, member_data.role)
        
        # Get user details for response
        from app.services.user import get_user_by_id
        user = get_user_by_id(db, member_data.user_id)
        
        member_dict = {
            "id": membership.id,
            "user_id": membership.user_id,
            "organization_id": membership.organization_id,
            "role": membership.role,
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
    description="Update a member's role. Requires admin role.",
)
def update_organization_member_role(
    organization_id: UUID,
    user_id: UUID,
    role_data: OrganizationMemberUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> OrganizationMemberResponse:
    """
    Update a member's role in the organization.
    Only admins can update roles.
    Prevents changing the last admin to a different role.
    """
    # Check user is admin
    current_role = get_user_role_in_org(db, organization_id, current_user.id)
    
    if not current_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacion no encontrada o no eres miembro",
        )
    
    if current_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update member roles",
        )
    
    try:
        membership = update_member_role(db, organization_id, user_id, role_data.role)
        
        # Get user details for response
        from app.services.user import get_user_by_id
        user = get_user_by_id(db, user_id)
        
        member_dict = {
            "id": membership.id,
            "user_id": membership.user_id,
            "organization_id": membership.organization_id,
            "role": membership.role,
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
    description="Remove a user from the organization. Requires admin role.",
)
def remove_organization_member(
    organization_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Remove a user from the organization.
    Only admins can remove members.
    Prevents removing the last admin.
    """
    # Check user is admin
    current_role = get_user_role_in_org(db, organization_id, current_user.id)
    
    if not current_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacion no encontrada o no eres miembro",
        )
    
    if current_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can remove members",
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
    description="Current user leaves the organization voluntarily.",
)
def leave_organization(
    organization_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Current user leaves the organization.
    Users can leave organizations they are members of.
    Cannot leave if you are the last admin.
    """
    # Check user is member
    role = get_user_role_in_org(db, organization_id, current_user.id)
    
    if not role:
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
