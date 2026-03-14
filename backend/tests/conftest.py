import os
from typing import Generator
from uuid import uuid4

import pytest
import sqlalchemy
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.api.deps import get_db  # Override the deps.get_db that endpoints actually use
from app.models import Base  # Import Base from models to get all registered tables
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.role import Role, RolePermission
from app.models.permission import Permission
from app.core.security import get_password_hash, create_access_token
from app.services.role import role_service

# Import all models to ensure they are registered with Base.metadata
from app.models import (
    User,
    Organization,
    OrganizationMember,
    ThirdParty,
    Material,
    MaterialCategory,
    Warehouse,
    BusinessUnit,
    MoneyAccount,
    PriceList,
    ExpenseCategory,
    MoneyMovement,
    InventoryAdjustment,
    MaterialTransformation,
    MaterialTransformationLine,
    MaterialCostHistory,
    ScheduledExpense,
    ScheduledExpenseApplication,
    Permission,
    Role,
    RolePermission,
)

# Test database URL (PostgreSQL on port 5433)
# Make sure docker-compose.test.yml is running:
# docker-compose -f docker-compose.test.yml up -d
TEST_DATABASE_URL = "postgresql://admin:test_password@localhost:5433/reciclaje_test"

# Create test engine with specific configuration for testing
test_engine = create_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True,
    echo=False,  # Set to True for SQL debugging
    isolation_level="READ COMMITTED",  # Ensure proper isolation
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def _seed_permissions_and_roles(db: Session, organization_id) -> dict:
    """
    Seed permissions and system roles for a test organization.
    Returns dict {role_name: role_id} for easy access.
    """
    role_service.seed_permissions(db)
    role_service.create_system_roles_for_org(db, organization_id)
    db.flush()

    roles = db.query(Role).filter(Role.organization_id == organization_id).all()
    return {r.name: r.id for r in roles}


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Create a fresh database session for each test.

    Drops tables first to ensure clean state, then creates them before test.
    This works correctly with TestClient which creates its own sessions.

    Note: Uses raw SQL with CASCADE to handle circular dependencies between
    double_entries, purchases, sales. Also drops ENUM types for PostgreSQL.
    """
    # Cerrar conexiones previas para evitar conflictos con ENUM types cacheados
    test_engine.dispose()

    # Drop all tables and types using raw SQL
    with test_engine.begin() as connection:
        if test_engine.dialect.name == "postgresql":
            # Clean slate: drop and recreate public schema
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
        else:
            # For SQLite, disable foreign keys first
            connection.execute(text("PRAGMA foreign_keys = OFF"))
            inspector = sqlalchemy.inspect(test_engine)
            tables = inspector.get_table_names()
            for table in tables:
                connection.execute(text(f'DROP TABLE IF EXISTS "{table}"'))
            connection.execute(text("PRAGMA foreign_keys = ON"))

    # Create all tables using SQLAlchemy
    Base.metadata.create_all(bind=test_engine)

    # Create a regular session
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()

        # Cerrar todas las conexiones del pool antes de DDL cleanup
        test_engine.dispose()

        # Drop all tables and types after test using the same strategy
        with test_engine.begin() as connection:
            if test_engine.dialect.name == "postgresql":
                # Clean slate: drop and recreate public schema
                connection.execute(text("DROP SCHEMA public CASCADE"))
                connection.execute(text("CREATE SCHEMA public"))
            else:
                connection.execute(text("PRAGMA foreign_keys = OFF"))
                inspector = sqlalchemy.inspect(test_engine)
                tables = inspector.get_table_names()
                for table in tables:
                    connection.execute(text(f'DROP TABLE IF EXISTS "{table}"'))
                connection.execute(text("PRAGMA foreign_keys = ON"))


@pytest.fixture(scope="function", autouse=True)
def override_db_dependency(db_session: Session):
    """
    Automatically override the database dependency for all tests.
    Makes the app use the test database engine instead of production.

    Note: This depends on db_session to ensure tables exist before override.
    """
    def override_get_db():
        """Create a new session from the test engine for each request."""
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client() -> Generator[TestClient, None, None]:
    """
    Create a FastAPI test client.
    Database override is handled by override_db_dependency fixture.
    """
    test_client = TestClient(app)
    yield test_client


@pytest.fixture
def test_user(db_session: Session) -> User:
    """
    Create a test user.
    """
    user = User(
        email="testuser@example.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="Test User",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user2(db_session: Session) -> User:
    """
    Create a second test user for multi-user tests.
    """
    user = User(
        email="testuser2@example.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="Test User 2",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user3(db_session: Session) -> User:
    """
    Create a third test user.
    """
    user = User(
        email="testuser3@example.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="Test User 3",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_organization(db_session: Session, test_user: User) -> Organization:
    """
    Create a test organization with test_user as admin.
    Seeds permissions and system roles.
    """
    org = Organization(
        name="Test Organization",
        slug="test-organization",
        max_users=10,
    )
    db_session.add(org)
    db_session.flush()

    # Seed permissions and system roles
    role_map = _seed_permissions_and_roles(db_session, org.id)

    # Add test_user as admin
    membership = OrganizationMember(
        user_id=test_user.id,
        organization_id=org.id,
        role_id=role_map["admin"],
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(org)

    return org


@pytest.fixture
def test_organization2(db_session: Session, test_user: User) -> Organization:
    """
    Create a second test organization with test_user as viewer.
    """
    org = Organization(
        name="Second Organization",
        slug="second-organization",
        max_users=5,
    )
    db_session.add(org)
    db_session.flush()

    # Seed permissions and system roles
    role_map = _seed_permissions_and_roles(db_session, org.id)

    # Add test_user as viewer (not admin)
    membership = OrganizationMember(
        user_id=test_user.id,
        organization_id=org.id,
        role_id=role_map["viewer"],
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(org)

    return org


@pytest.fixture
def auth_token(test_user: User) -> str:
    """
    Create a JWT token for test_user.
    """
    token = create_access_token(data={"sub": str(test_user.id)})
    return token


@pytest.fixture
def auth_token_user2(test_user2: User) -> str:
    """
    Create a JWT token for test_user2.
    """
    token = create_access_token(data={"sub": str(test_user2.id)})
    return token


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    """
    Create authorization headers with token.
    """
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def auth_headers_user2(auth_token_user2: str) -> dict:
    """
    Create authorization headers for user2.
    """
    return {"Authorization": f"Bearer {auth_token_user2}"}


@pytest.fixture
def org_headers(auth_token: str, test_organization: Organization) -> dict:
    """
    Create headers with both auth and organization context.
    test_user is admin in test_organization.
    """
    return {
        "Authorization": f"Bearer {auth_token}",
        "X-Organization-ID": str(test_organization.id),
    }


@pytest.fixture
def org_headers2(auth_token: str, test_organization2: Organization) -> dict:
    """
    Create headers with auth and organization2 context.
    test_user is viewer in test_organization2 (no write permissions).
    """
    return {
        "Authorization": f"Bearer {auth_token}",
        "X-Organization-ID": str(test_organization2.id),
    }
