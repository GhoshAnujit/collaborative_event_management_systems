import pytest
from httpx import AsyncClient
from fastapi import status
from datetime import datetime, timedelta, UTC
import urllib.parse

pytestmark = pytest.mark.asyncio

async def test_create_event_success(client: AsyncClient, test_user_token, offset_days=0):
    """Test successful event creation."""
    event_data = {
        "title": f"Test Event {offset_days}",
        "description": "Test Description",
        "start_time": (datetime.now(UTC) + timedelta(days=1 + offset_days)).isoformat(),
        "end_time": (datetime.now(UTC) + timedelta(days=1 + offset_days, hours=2)).isoformat(),
        "location": "Test Location",
        "is_recurring": False
    }
    
    response = await client.post(
        "/api/v1/events/",
        json=event_data,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    
    if response.status_code != status.HTTP_201_CREATED:
        print(f"Error creating event: {response.text}")
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    return data["id"]

async def test_create_recurring_event(client: AsyncClient, test_user_token):
    """Test creating a recurring event."""
    event_data = {
        "title": "Recurring Meeting",
        "description": "Weekly team sync",
        "start_time": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "end_time": (datetime.now(UTC) + timedelta(days=1, hours=2)).isoformat(),
        "location": "Conference Room",
        "is_recurring": True,
        "recurrence_pattern": "FREQ=WEEKLY;COUNT=4"
    }
    
    response = await client.post(
        "/api/v1/events/",
        json=event_data,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["is_recurring"] == True
    # The API adds "RRULE:" prefix if not provided
    assert "RRULE:" in data["recurrence_pattern"]
    assert "FREQ=WEEKLY;COUNT=4" in data["recurrence_pattern"]

async def test_get_event(client: AsyncClient, test_user_token):
    """Test retrieving an event."""
    event_id = await test_create_event_success(client, test_user_token)
    
    response = await client.get(
        f"/api/v1/events/{event_id}",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == event_id

async def test_update_event(client: AsyncClient, test_user_token):
    """Test updating an event."""
    event_id = await test_create_event_success(client, test_user_token)
    
    # Make sure to provide all fields that might be required
    update_data = {
        "title": "Updated Event",
        "description": "Updated Description",
        "start_time": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "end_time": (datetime.now(UTC) + timedelta(days=1, hours=2)).isoformat(),
        "location": "Updated Location",
        "is_recurring": False
    }
    
    response = await client.put(
        f"/api/v1/events/{event_id}",
        json=update_data,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["title"] == "Updated Event"
    assert data["description"] == "Updated Description"

async def test_delete_event(client: AsyncClient, test_user_token):
    """Test deleting an event."""
    # Create event directly
    event_data = {
        "title": "Event to Delete",
        "description": "This event will be deleted",
        "start_time": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "end_time": (datetime.now(UTC) + timedelta(days=1, hours=2)).isoformat(),
        "location": "Test Location",
        "is_recurring": False
    }
    
    # Create the event
    response = await client.post(
        "/api/v1/events/",
        json=event_data,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    event_id = response.json()["id"]
    
    # Try to get the event first to confirm it exists
    response = await client.get(
        f"/api/v1/events/{event_id}",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Delete the event
    response = await client.delete(
        f"/api/v1/events/{event_id}",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
    
    # Try to get the event again to confirm it's deleted
    response = await client.get(
        f"/api/v1/events/{event_id}",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND

async def test_batch_create_events(client: AsyncClient, test_user_token):
    """Test batch event creation."""
    events = []
    for i in range(3):
        events.append({
            "title": f"Event {i+1}",
            "description": f"Description {i+1}",
            "start_time": (datetime.now(UTC) + timedelta(days=i+1)).isoformat(),
            "end_time": (datetime.now(UTC) + timedelta(days=i+1, hours=2)).isoformat(),
            "location": f"Location {i+1}",
            "is_recurring": False
        })
    
    response = await client.post(
        "/api/v1/events/batch",
        json={"events": events},
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert len(data) == len(events)
    for i, event in enumerate(data):
        assert event["title"] == events[i]["title"]

async def test_event_conflict_detection(client: AsyncClient, test_user_token):
    """Test event conflict detection."""
    # Create first event
    start_time = datetime.now(UTC) + timedelta(days=1)
    end_time = start_time + timedelta(hours=2)
    
    event1_data = {
        "title": "Event 1",
        "description": "First event",
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "location": "Location 1",
        "is_recurring": False
    }
    
    response = await client.post(
        "/api/v1/events",
        json=event1_data,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    
    # Try to create overlapping event
    event2_data = {
        "title": "Event 2",
        "description": "Second event",
        "start_time": (start_time + timedelta(minutes=30)).isoformat(),
        "end_time": (end_time + timedelta(minutes=30)).isoformat(),
        "location": "Location 2",
        "is_recurring": False
    }
    
    response = await client.post(
        "/api/v1/events",
        json=event2_data,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "conflicts" in response.json()["detail"].lower() 