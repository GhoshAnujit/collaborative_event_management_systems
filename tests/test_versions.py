import pytest
from httpx import AsyncClient
from fastapi import status
from datetime import datetime, timedelta

pytestmark = pytest.mark.asyncio

async def test_event_version_creation(client: AsyncClient, test_user_token):
    """Test version creation when an event is updated."""
    # Create an event
    event_data = {
        "title": "Version Test Event",
        "description": "Original description",
        "start_time": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "end_time": (datetime.utcnow() + timedelta(days=1, hours=2)).isoformat(),
        "is_recurring": False
    }
    
    response = await client.post(
        "/api/v1/events/",
        json=event_data,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    event_id = response.json()["id"]
    
    # Update the event to create a new version
    update_data = {
        "title": "Updated Title",
        "description": "Updated description",
        "start_time": event_data["start_time"],
        "end_time": event_data["end_time"],
        "is_recurring": False
    }
    
    response = await client.put(
        f"/api/v1/events/{event_id}",
        json=update_data,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Get event history
    response = await client.get(
        f"/api/v1/events/{event_id}/history",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    versions = response.json()
    
    # Should have at least 2 versions (original + update)
    assert len(versions) >= 2
    
    # Check specific version
    response = await client.get(
        f"/api/v1/events/{event_id}/history/1",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    version = response.json()
    assert version["version_number"] == 1

async def test_version_rollback(client: AsyncClient, test_user_token):
    """Test rolling back to a previous version."""
    # Create an event
    event_data = {
        "title": "Rollback Test Event",
        "description": "Original description",
        "start_time": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "end_time": (datetime.utcnow() + timedelta(days=1, hours=2)).isoformat(),
        "is_recurring": False
    }
    
    response = await client.post(
        "/api/v1/events/",
        json=event_data,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    event_id = response.json()["id"]
    
    # Make multiple updates to create versions
    update_data = {
        "title": "Update 1",
        "description": "First update",
        "start_time": event_data["start_time"],
        "end_time": event_data["end_time"],
        "is_recurring": False
    }
    
    response = await client.put(
        f"/api/v1/events/{event_id}",
        json=update_data,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    update_data = {
        "title": "Update 2",
        "description": "Second update",
        "start_time": event_data["start_time"],
        "end_time": event_data["end_time"],
        "is_recurring": False
    }
    
    response = await client.put(
        f"/api/v1/events/{event_id}",
        json=update_data,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Rollback to version 1 (original)
    response = await client.post(
        f"/api/v1/events/{event_id}/rollback/1",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Verify the event has been rolled back
    response = await client.get(
        f"/api/v1/events/{event_id}",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["title"] == event_data["title"]
    assert data["description"] == event_data["description"]

async def test_version_diff(client: AsyncClient, test_user_token):
    """Test getting diff between two versions."""
    # Create an event
    event_data = {
        "title": "Diff Test Event",
        "description": "Original description",
        "start_time": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "end_time": (datetime.utcnow() + timedelta(days=1, hours=2)).isoformat(),
        "is_recurring": False
    }
    
    response = await client.post(
        "/api/v1/events/",
        json=event_data,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    event_id = response.json()["id"]
    
    # Make an update to create a new version
    update_data = {
        "title": "Updated Title",
        "description": "Updated description",
        "start_time": event_data["start_time"],
        "end_time": event_data["end_time"],
        "is_recurring": False
    }
    
    response = await client.put(
        f"/api/v1/events/{event_id}",
        json=update_data,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Get diff between versions 1 and 2
    response = await client.get(
        f"/api/v1/events/{event_id}/diff/1/2",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    
    # Print the response for debugging
    print(f"Diff response status: {response.status_code}")
    print(f"Diff response content: {response.text}")
    
    assert response.status_code == status.HTTP_200_OK
    diff = response.json()
    
    # Check that diff contains changes to title and description
    assert "changes" in diff
    assert "title" in diff["changes"]
    assert diff["changes"]["title"]["old"] == event_data["title"]
    assert diff["changes"]["title"]["new"] == update_data["title"]
    assert "description" in diff["changes"] 