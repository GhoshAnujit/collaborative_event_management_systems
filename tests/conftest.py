import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
import asyncio
from typing import AsyncGenerator, Generator, Dict
import os
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from datetime import datetime, UTC, timedelta
import sys

# Add the app directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.models.base import Base
from app.db.database import get_db
from app.core.config import settings
from app.core.rate_limit import rate_limit_dependency
from app.models import User, Event, EventPermission, EventVersion, Notification  # Import all models
from app.core.security import create_access_token, create_refresh_token, get_password_hash

# Use a separate test database
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

# Create async engine for tests
engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=True,
    future=True,
    connect_args={"check_same_thread": False}
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Override the get_db dependency for testing
async def override_get_db():
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

@pytest_asyncio.fixture(scope="session")
def event_loop_policy():
    """Create and configure event loop policy for tests."""
    return asyncio.DefaultEventLoopPolicy()

@pytest_asyncio.fixture(scope="session")
async def create_test_db():
    """Create test database and tables."""
    # Drop all tables to ensure clean state
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    # Clean up after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Setup database for each test."""
    # Start with a clean slate for each test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Clean up after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session for tests."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

@pytest_asyncio.fixture
async def test_app() -> FastAPI:
    """Create and configure a new FastAPI application for testing."""
    # Set testing mode
    settings.TESTING = True
    
    # Override database dependency
    app.dependency_overrides[get_db] = override_get_db
    
    # Remove rate limiting for tests by overriding the dependency
    app.dependency_overrides[rate_limit_dependency] = lambda: True
    
    # Set very high rate limits in settings
    settings.API_RATE_LIMIT = 10000
    settings.AUTH_RATE_LIMIT = 10000
    
    # Add validation exempt path for events listing
    if "/api/v1/events/" not in settings.VALIDATION_EXEMPT_PATHS:
        settings.VALIDATION_EXEMPT_PATHS.append("/api/v1/events/")
    
    return app

@pytest_asyncio.fixture
async def client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
        follow_redirects=True
    ) as ac:
        yield ac

@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("testpass123"),
        is_active=True,
        updated_at=datetime.now(UTC)
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest_asyncio.fixture
async def test_user_tokens(test_user: User) -> Dict[str, str]:
    """Create test tokens for the test user."""
    data = {"sub": test_user.email}
    return {
        "access_token": create_access_token(data),
        "refresh_token": create_refresh_token(data)
    }

@pytest_asyncio.fixture
async def test_user_token(test_user_tokens: Dict[str, str]) -> str:
    """Create a test access token for the test user."""
    return test_user_tokens["access_token"]

@pytest_asyncio.fixture
async def test_user_refresh_token(test_user_tokens: Dict[str, str]) -> str:
    """Create a test refresh token for the test user."""
    return test_user_tokens["refresh_token"]

@pytest_asyncio.fixture
async def test_event(client, test_user, test_user_token) -> Dict:
    """Create a test event and return it."""
    event_data = {
        "title": "Test Event",
        "description": "Test Description",
        "start_time": datetime.now(UTC).isoformat(),
        "end_time": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
        "is_recurring": False
    }
    
    response = await client.post(
        "/api/v1/events/",
        json=event_data,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    
    assert response.status_code == 201
    return response.json()

@pytest_asyncio.fixture
async def second_test_user(db_session: AsyncSession) -> User:
    """Create a second test user."""
    user = User(
        email="second@example.com",
        username="seconduser",
        hashed_password=get_password_hash("testpass123"),
        is_active=True,
        updated_at=datetime.now(UTC)
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest_asyncio.fixture
async def second_user_tokens(second_test_user: User) -> Dict[str, str]:
    """Create tokens for the second test user."""
    data = {"sub": second_test_user.email}
    return {
        "access_token": create_access_token(data),
        "refresh_token": create_refresh_token(data)
    }

@pytest_asyncio.fixture
async def second_user_token(second_user_tokens: Dict[str, str]) -> str:
    """Get access token for the second test user."""
    return second_user_tokens["access_token"] 