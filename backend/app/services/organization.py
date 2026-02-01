from uuid import UUID
import re

from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from app.models.organization import Organization
from app.models.user import User, OrganizationMember
from app.schemas.organization import OrganizationCreate, OrganizationUpdate


def _generate_slug_from_name(name: str) -> str:
    """
    Generate a URL-friendly slug from organization name.
    
    Args:
        name: Organization name
        
    Returns:
        Slug string (lowercase, hyphens, alphanumeric)
    """
    # Convert to lowercase
    slug = name.lower()
    # Replace spaces and special chars with hyphens
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    return slug


def _ensure_unique_slug(db: Session, base_slug: str) -> str:
    """
    Ensure slug is unique by appending numbers if necessary.
    
    Args:
        db: Database session
        base_slug: Base slug to check
        
    Returns:
        Unique slug
    """
    slug = base_slug
    counter = 1
    
    while True:
        existing = db.execute(
            select(Organization).where(Organization.slug == slug)
        ).scalar_one_or_none()
        
        if not existing:
            return slug
        
        slug = f"{base_slug}-{counter}"
        counter += 1


def create_organization(
    db: Session,
    org_data: OrganizationCreate,
    owner_user_id: UUID
) -> Organization:
    """
    Create a new organization and add owner as admin.
    
    Args:
        db: Database session
        org_data: Organization creation data
        owner_user_id: User ID to set as admin
        
    Returns:
        Created Organization object
    """
    # Generate or validate slug
    if org_data.slug:
        slug = _ensure_unique_slug(db, org_data.slug)
    else:
        base_slug = _generate_slug_from_name(org_data.name)
        slug = _ensure_unique_slug(db, base_slug)
    
    # Create organization
    organization = Organization(
        name=org_data.name,
        slug=slug,
    )
    
    db.add(organization)
    db.flush()  # Get organization.id without committing
    
    # Add owner as admin
    membership = OrganizationMember(
        user_id=owner_user_id,
        organization_id=organization.id,
        role="admin",
    )
    
    db.add(membership)
    db.commit()
    db.refresh(organization)
    
    return organization


def get_organization(db: Session, organization_id: UUID, user_id: UUID) -> Organization | None:
    """
    Get organization if user is a member.
    
    Args:
        db: Database session
        organization_id: Organization UUID
        user_id: User UUID
        
    Returns:
        Organization object if user is member, None otherwise
    """
    # Check if user is member
    membership = db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id
        )
    ).scalar_one_or_none()
    
    if not membership:
        return None
    
    # Get organization
    organization = db.execute(
        select(Organization).where(Organization.id == organization_id)
    ).scalar_one_or_none()
    
    return organization


def get_user_organizations(db: Session, user_id: UUID) -> list[tuple[Organization, str]]:
    """
    Get all organizations where user is a member, with their role in each.
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        List of tuples (Organization, role)
    """
    # Query organizations with user's role
    statement = (
        select(Organization, OrganizationMember.role)
        .join(OrganizationMember)
        .where(OrganizationMember.user_id == user_id)
        .order_by(Organization.created_at.desc())
    )
    
    results = db.execute(statement).all()
    
    return [(org, role) for org, role in results]


def add_member(
    db: Session,
    organization_id: UUID,
    user_id: UUID,
    role: str
) -> OrganizationMember:
    """
    Add a user to an organization with specified role.
    Validates max_users limit.
    
    Args:
        db: Database session
        organization_id: Organization UUID
        user_id: User UUID to add
        role: Role to assign
        
    Returns:
        Created OrganizationMember object
        
    Raises:
        ValueError: If organization is at max capacity or user already member
    """
    # Get organization
    organization = db.execute(
        select(Organization).where(Organization.id == organization_id)
    ).scalar_one_or_none()
    
    if not organization:
        raise ValueError("Organization not found")
    
    # Check if user is already a member
    existing = db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id
        )
    ).scalar_one_or_none()
    
    if existing:
        raise ValueError("User is already a member of this organization")
    
    # Check max_users limit
    current_member_count = db.execute(
        select(func.count(OrganizationMember.id)).where(
            OrganizationMember.organization_id == organization_id
        )
    ).scalar()
    
    if current_member_count >= organization.max_users:
        raise ValueError(f"Organization has reached maximum capacity ({organization.max_users} users)")
    
    # Verify user exists
    user = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()
    
    if not user:
        raise ValueError("User not found")
    
    # Create membership
    membership = OrganizationMember(
        user_id=user_id,
        organization_id=organization_id,
        role=role,
    )
    
    db.add(membership)
    db.commit()
    db.refresh(membership)
    
    return membership


def remove_member(
    db: Session,
    organization_id: UUID,
    user_id: UUID
) -> bool:
    """
    Remove a user from an organization.
    Prevents removing the last admin.
    
    Args:
        db: Database session
        organization_id: Organization UUID
        user_id: User UUID to remove
        
    Returns:
        True if removed successfully
        
    Raises:
        ValueError: If trying to remove last admin or member not found
    """
    # Get membership
    membership = db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id
        )
    ).scalar_one_or_none()
    
    if not membership:
        raise ValueError("User is not a member of this organization")
    
    # If removing an admin, check if it's the last one
    if membership.role == "admin":
        admin_count = db.execute(
            select(func.count(OrganizationMember.id)).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.role == "admin"
            )
        ).scalar()
        
        if admin_count <= 1:
            raise ValueError("Cannot remove the last admin from the organization")
    
    db.delete(membership)
    db.commit()
    
    return True


def update_member_role(
    db: Session,
    organization_id: UUID,
    user_id: UUID,
    new_role: str
) -> OrganizationMember:
    """
    Update a member's role in an organization.
    Prevents changing the last admin to a different role.
    
    Args:
        db: Database session
        organization_id: Organization UUID
        user_id: User UUID
        new_role: New role to assign
        
    Returns:
        Updated OrganizationMember object
        
    Raises:
        ValueError: If trying to change last admin or member not found
    """
    # Get membership
    membership = db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id
        )
    ).scalar_one_or_none()
    
    if not membership:
        raise ValueError("User is not a member of this organization")
    
    # If changing from admin to another role, check if it's the last admin
    if membership.role == "admin" and new_role != "admin":
        admin_count = db.execute(
            select(func.count(OrganizationMember.id)).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.role == "admin"
            )
        ).scalar()
        
        if admin_count <= 1:
            raise ValueError("Cannot change role of the last admin")
    
    membership.role = new_role
    db.commit()
    db.refresh(membership)
    
    return membership


def get_organization_members(
    db: Session,
    organization_id: UUID
) -> list[tuple[OrganizationMember, User]]:
    """
    Get all members of an organization with their user details.
    
    Args:
        db: Database session
        organization_id: Organization UUID
        
    Returns:
        List of tuples (OrganizationMember, User)
    """
    statement = (
        select(OrganizationMember, User)
        .join(User, OrganizationMember.user_id == User.id)
        .where(OrganizationMember.organization_id == organization_id)
        .order_by(OrganizationMember.joined_at.desc())
    )
    
    results = db.execute(statement).all()
    
    return [(member, user) for member, user in results]


def get_user_role_in_org(
    db: Session,
    organization_id: UUID,
    user_id: UUID
) -> str | None:
    """
    Get user's role in a specific organization.
    
    NOTE: This function will be called on EVERY authenticated request
    that requires organization context. In Phase 2, we will implement
    Redis caching to avoid repeated database queries.
    
    Args:
        db: Database session
        organization_id: Organization UUID
        user_id: User UUID
        
    Returns:
        Role string if user is member, None otherwise
    """
    membership = db.execute(
        select(OrganizationMember.role).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id
        )
    ).scalar_one_or_none()
    
    return membership


def update_organization(
    db: Session,
    organization_id: UUID,
    org_data: OrganizationUpdate
) -> Organization | None:
    """
    Update organization details.
    
    Args:
        db: Database session
        organization_id: Organization UUID
        org_data: Organization update data
        
    Returns:
        Updated Organization object or None if not found
    """
    organization = db.execute(
        select(Organization).where(Organization.id == organization_id)
    ).scalar_one_or_none()
    
    if not organization:
        return None
    
    # Update fields if provided
    if org_data.name is not None:
        organization.name = org_data.name
    
    if org_data.logo_url is not None:
        organization.logo_url = org_data.logo_url
    
    if org_data.max_users is not None:
        # Validate new max_users is not less than current member count
        current_member_count = db.execute(
            select(func.count(OrganizationMember.id)).where(
                OrganizationMember.organization_id == organization_id
            )
        ).scalar()
        
        if org_data.max_users < current_member_count:
            raise ValueError(
                f"Cannot set max_users to {org_data.max_users}. "
                f"Organization currently has {current_member_count} members"
            )
        
        organization.max_users = org_data.max_users
    
    db.commit()
    db.refresh(organization)
    
    return organization
