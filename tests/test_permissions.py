import pytest
import pytest_asyncio
from httpx import AsyncClient
from fastapi import status
from datetime import datetime, timedelta, UTC
import asyncio

from app.models.enums import PermissionRole

pytestmark = pytest.mark.asyncio

@pytest_asyncio.fixture
async def second_test_user(db_session):
    """Create a second test user for permission tests."""
    from app.models.user import User
    from app.core.security import get_password_hash
    
    user = User(
        email="second@example.com",
        username="second_user",
        hashed_password=get_password_hash("testpass123"),
        is_active=True,
        updated_at=datetime.now()
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest_asyncio.fixture
async def second_user_token(second_test_user):
    """Get a token for the second test user."""
    from app.core.security import create_access_token
    data = {"sub": second_test_user.email}
    return create_access_token(data)

async def test_share_event(client: AsyncClient, test_user_token, second_test_user):
    """Test sharing an event with another user."""
    # First create an event
    event_data = {
        "title": "Shared Event",
        "description": "Event to be shared",
        "start_time": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "end_time": (datetime.now(UTC) + timedelta(days=1, hours=2)).isoformat(),
        "is_recurring": False
    }
    
    response = await client.post(
        "/api/v1/events/",
        json=event_data,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    event_id = response.json()["id"]
    
    # Share the event with the second user
    share_data = {
        "user_id": second_test_user.id,
        "role": "EDITOR"
    }
    
    response = await client.post(
        f"/api/v1/events/{event_id}/share",
        json=share_data,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Check if the permission was created correctly
    response = await client.get(
        f"/api/v1/events/{event_id}/permissions",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Verify that second user is in the permissions list
    permissions = response.json()
    second_user_permission = next((p for p in permissions if p["user_id"] == second_test_user.id), None)
    assert second_user_permission is not None
    assert second_user_permission["role"] == "EDITOR"

async def test_permission_revocation(
    client: AsyncClient,
    test_user_token,
    second_test_user,
    second_user_token
):
    """Test revoking permissions from a user."""
    # First create and share an event
    event_data = {
        "title": "Revocation Test Event",
        "description": "Test Description",
        "start_time": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "end_time": (datetime.now(UTC) + timedelta(days=1, hours=2)).isoformat(),
        "is_recurring": False
    }
    
    response = await client.post(
        "/api/v1/events/",
        json=event_data,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    event_id = response.json()["id"]
    
    # Share with second user
    share_data = {
        "user_id": second_test_user.id,
        "role": "VIEWER"
    }
    
    response = await client.post(
        f"/api/v1/events/{event_id}/share",
        json=share_data,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Second user should be able to view the event
    response = await client.get(
        f"/api/v1/events/{event_id}",
        headers={"Authorization": f"Bearer {second_user_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Revoke access
    response = await client.delete(
        f"/api/v1/events/{event_id}/permissions/{second_test_user.id}",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
    
    # Verify the permission was removed
    response = await client.get(
        f"/api/v1/events/{event_id}/permissions",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    permissions = response.json()
    second_user_permission = next((p for p in permissions if p["user_id"] == second_test_user.id), None)
    assert second_user_permission is None
    
    # Second user should no longer be able to access the event
    response = await client.get(
        f"/api/v1/events/{event_id}",
        headers={"Authorization": f"Bearer {second_user_token}"}
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN 