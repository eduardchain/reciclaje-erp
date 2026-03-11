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
from app.core.security import get_password_hash, create_access_token

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


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Create a fresh database session for each test.
    
    Drops tables first to ensure clean state, then creates them before test.
    This works correctly with TestClient which creates its own sessions.
    
    Note: Uses raw SQL with CASCADE to handle circular dependencies between 
    double_entries, purchases, sales. Also drops ENUM types for PostgreSQL.
    """
    # Drop all tables and types using raw SQL
    with test_engine.begin() as connection:
        if test_engine.dialect.name == "postgresql":
            # Drop all ENUM types first (PostgreSQL-specific)
            result = connection.execute(text(
                "SELECT t.typname FROM pg_type t "
                "JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace "
                "WHERE t.typtype = 'e' AND n.nspname = 'public'"
            ))
            enum_types = [row[0] for row in result]
            for enum_type in enum_types:
                connection.execute(text(f'DROP TYPE IF EXISTS "{enum_type}" CASCADE'))
            
            # Get all table names and drop them
            inspector = sqlalchemy.inspect(test_engine)
            tables = inspector.get_table_names()
            for table in tables:
                connection.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
        else:
            # For SQLite, disable foreign keys first
            connection.execute(text("PRAGMA foreign_keys = OFF"))
            inspector = sqlalchemy.inspect(test_engine)
            tables = inspector.get_table_names()
            for table in tables:
                connection.execute(text(f'DROP TABLE IF EXISTS "{table}"'))
            connection.execute(text("PRAGMA foreign_keys = ON"))
    
    # Create all tables using SQLAlchemy
    Base.metadata.create_all(bind=test_engine, checkfirst=False)
    
    # Create a regular session
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        
        # Drop all tables and types after test using the same strategy
        with test_engine.begin() as connection:
            if test_engine.dialect.name == "postgresql":
                # Drop ENUM types first
                result = connection.execute(text(
                    "SELECT t.typname FROM pg_type t "
                    "JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace "
                    "WHERE t.typtype = 'e' AND n.nspname = 'public'"
                ))
                enum_types = [row[0] for row in result]
                for enum_type in enum_types:
                    connection.execute(text(f'DROP TYPE IF EXISTS "{enum_type}" CASCADE'))
                
                # Drop tables
                inspector = sqlalchemy.inspect(test_engine)
                tables = inspector.get_table_names()
                for table in tables:
                    connection.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
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
    """
    org = Organization(
        name="Test Organization",
        slug="test-organization",
        max_users=10,
    )
    db_session.add(org)
    db_session.flush()
    
    # Add test_user as admin
    membership = OrganizationMember(
        user_id=test_user.id,
        organization_id=org.id,
        role="admin",
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(org)
    
    return org


@pytest.fixture
def test_organization2(db_session: Session, test_user: User) -> Organization:
    """
    Create a second test organization.
    """
    org = Organization(
        name="Second Organization",
        slug="second-organization",
        max_users=5,
    )
    db_session.add(org)
    db_session.flush()
    
    # Add test_user as manager (not admin)
    membership = OrganizationMember(
        user_id=test_user.id,
        organization_id=org.id,
        role="manager",
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
    """
    return {
        "Authorization": f"Bearer {auth_token}",
        "X-Organization-ID": str(test_organization.id),
    }
