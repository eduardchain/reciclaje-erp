import pytest
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_required_org_context, get_optional_org_context
from app.models.user import User
from app.models.organization import Organization


class TestRequiredOrgContext:
    """Tests for get_required_org_context dependency."""
    
    @pytest.mark.asyncio
    async def test_validates_uuid_format(
        self,
        db_session: Session,
        test_user: User,
    ):
        """Test rejects invalid UUID format."""
        with pytest.raises(HTTPException) as exc_info:
            await get_required_org_context(
                x_organization_id="not-a-valid-uuid",
                current_user=test_user,
                db=db_session,
            )
        
        assert exc_info.value.status_code == 400
        assert "invalid" in exc_info.value.detail.lower()
        assert "uuid" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_validates_membership(
        self,
        db_session: Session,
        test_user: User,
    ):
        """Test rejects when user is not member of organization."""
        # Use random UUID (organization doesn't exist or user not member)
        random_org_id = str(uuid4())
        
        with pytest.raises(HTTPException) as exc_info:
            await get_required_org_context(
                x_organization_id=random_org_id,
                current_user=test_user,
                db=db_session,
            )
        
        assert exc_info.value.status_code == 403
        assert "not a member" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_returns_correct_role(
        self,
        db_session: Session,
        test_user: User,
        test_organization: Organization,
    ):
        """Test returns user's correct role in organization."""
        context = await get_required_org_context(
            x_organization_id=str(test_organization.id),
            current_user=test_user,
            db=db_session,
        )
        
        assert context["organization_id"] == test_organization.id
        assert context["user_id"] == test_user.id
        assert context["user_role"] == "admin"  # test_user is admin in test_organization
        assert context["user"] == test_user
    
    @pytest.mark.asyncio
    async def test_returns_correct_role_for_different_org(
        self,
        db_session: Session,
        test_user: User,
        test_organization2: Organization,
    ):
        """Test returns correct role when user has different role in different org."""
        context = await get_required_org_context(
            x_organization_id=str(test_organization2.id),
            current_user=test_user,
            db=db_session,
        )
        
        assert context["user_role"] == "manager"  # test_user is manager in test_organization2


class TestOptionalOrgContext:
    """Tests for get_optional_org_context dependency."""
    
    @pytest.mark.asyncio
    async def test_returns_none_when_no_header(
        self,
        db_session: Session,
        test_user: User,
    ):
        """Test returns None when header not provided."""
        context = await get_optional_org_context(
            x_organization_id=None,
            current_user=test_user,
            db=db_session,
        )
        
        assert context is None
    
    @pytest.mark.asyncio
    async def test_validates_uuid_when_header_present(
        self,
        db_session: Session,
        test_user: User,
    ):
        """Test validates UUID format when header is provided."""
        with pytest.raises(HTTPException) as exc_info:
            await get_optional_org_context(
                x_organization_id="invalid-uuid",
                current_user=test_user,
                db=db_session,
            )
        
        assert exc_info.value.status_code == 400
        assert "invalid" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_validates_membership_when_header_present(
        self,
        db_session: Session,
        test_user: User,
    ):
        """Test validates membership when header is provided."""
        random_org_id = str(uuid4())
        
        with pytest.raises(HTTPException) as exc_info:
            await get_optional_org_context(
                x_organization_id=random_org_id,
                current_user=test_user,
                db=db_session,
            )
        
        assert exc_info.value.status_code == 403
        assert "not a member" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_returns_context_when_valid_header(
        self,
        db_session: Session,
        test_user: User,
        test_organization: Organization,
    ):
        """Test returns context dict when valid header provided."""
        context = await get_optional_org_context(
            x_organization_id=str(test_organization.id),
            current_user=test_user,
            db=db_session,
        )
        
        assert context is not None
        assert context["organization_id"] == test_organization.id
        assert context["user_id"] == test_user.id
        assert context["user_role"] == "admin"
        assert context["user"] == test_user
