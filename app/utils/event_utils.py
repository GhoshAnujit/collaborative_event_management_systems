from typing import Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.schemas.event import EventResponse, UserInfo
from app.crud.event import get_owner

async def create_event_response(db: AsyncSession, event: Event, start_time: datetime | None = None, end_time: datetime | None = None) -> EventResponse:
    """Create a standardized event response."""
    owner = await get_owner(db, event)
    
    response_data = {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "location": event.location,
        "start_time": start_time or event.start_time,
        "end_time": end_time or event.end_time,
        "is_recurring": event.is_recurring,
        "recurrence_pattern": event.recurrence_pattern,
        "created_by": UserInfo(id=owner.id, email=owner.email),
        "created_at": event.created_at,
        "updated_at": event.updated_at
    }
    
    return EventResponse(**response_data) 