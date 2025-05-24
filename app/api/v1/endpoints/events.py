from typing import List, Dict, Any
from datetime import datetime, UTC
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.database import get_db
from app.models.user import User, UserRole
from app.schemas.event import (
    EventCreate,
    EventResponse,
    EventUpdate,
    EventBatchCreate,
    EventPermissionCreate,
    EventPermissionResponse,
    EventVersionResponse,
    EventVersionDiff,
    EventListResponse,
    UserInfo
)
from app.crud import event as crud_event
from app.core.cache import cached
from app.core.responses import DynamicResponse
from app.core.queries import DateRangeQuery, EventFilter
from app.utils.event_utils import create_event_response
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/events",
    tags=["Events"],
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not enough permissions"},
        404: {"description": "Event not found"},
        500: {"description": "Internal server error"}
    }
)

@router.post(
    "/",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new event",
    description="""
    Create a new event.
    
    Features:
    * Automatic conflict detection
    * Timezone handling (UTC)
    * Recurring event support
    * Version tracking
    """,
    responses={
        201: {
            "description": "Event created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "title": "Team Meeting",
                        "description": "Weekly team sync",
                        "start_time": "2024-03-20T10:00:00Z",
                        "end_time": "2024-03-20T11:00:00Z",
                        "location": "Conference Room A",
                        "is_recurring": False,
                        "recurrence_pattern": None,
                        "created_by": {"id": 1, "email": "user@example.com"},
                        "created_at": "2024-03-19T15:00:00Z",
                        "updated_at": "2024-03-19T15:00:00Z"
                    }
                }
            }
        }
    }
)
async def create_event(
    *,
    db: AsyncSession = Depends(get_db),
    event_in: EventCreate,
    current_user: User = Depends(get_current_user),
    check_conflicts: bool = Query(True, description="Whether to check for conflicts with existing events")
) -> EventResponse:
    """
    Create a new event.
    
    Parameters:
    - **event**: Event data
    - **check_conflicts**: Whether to check for conflicts (optional, default: true)
    
    Returns the created event.
    """
    try:
        # Ensure start_time and end_time are timezone-aware
        if not event_in.start_time.tzinfo:
            event_in.start_time = event_in.start_time.replace(tzinfo=UTC)
        if not event_in.end_time.tzinfo:
            event_in.end_time = event_in.end_time.replace(tzinfo=UTC)
        
        # Validate that end_time is after start_time
        if event_in.start_time >= event_in.end_time:
            raise ValueError("End time must be after start time")
        
        db_event = await crud_event.create_event(
            db,
            event_in,
            current_user,
            check_conflicts=check_conflicts
        )
        
        return await create_event_response(db, db_event)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/batch",
    response_model=List[EventResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create multiple events",
    description="""
    Create multiple events in a single batch operation.
    
    Features:
    * Atomic operation (all succeed or all fail)
    * Conflict detection across all events
    * Maximum 50 events per batch
    * Consistent permission assignment
    """,
    responses={
        201: {
            "description": "Events created successfully",
            "content": {
                "application/json": {
                    "example": [{
                        "id": 1,
                        "title": "Meeting 1",
                        "start_time": "2024-03-20T10:00:00Z",
                        "end_time": "2024-03-20T11:00:00Z",
                        "created_by": {"id": 1, "email": "user@example.com"},
                        "created_at": "2024-03-19T15:00:00Z",
                        "updated_at": "2024-03-19T15:00:00Z"
                    }]
                }
            }
        }
    }
)
async def create_events_batch(
    *,
    db: AsyncSession = Depends(get_db),
    batch_in: EventBatchCreate,
    current_user: User = Depends(get_current_user),
    check_conflicts: bool = Query(True, description="Whether to check for conflicts with existing events")
) -> List[EventResponse]:
    """
    Create multiple events in a batch operation.
    
    Parameters:
    - **events**: List of events to create (maximum 50)
    - **check_conflicts**: Whether to check for conflicts (optional, default: true)
    
    Each event in the batch requires the same fields as single event creation.
    """
    if len(batch_in.events) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create more than 50 events at once"
        )
    
    try:
        db_events = await crud_event.create_events_batch(
            db,
            batch_in,
            current_user,
            check_conflicts=check_conflicts
        )
        
        return [await create_event_response(db, event) for event in db_events]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/",
    response_model=EventListResponse,
    summary="List events in date range",
    description="""
    Retrieve all events within a specified date range.
    
    Features:
    * Pagination support
    * Optional inclusion of recurring event occurrences
    * Automatic permission filtering
    * Efficient date range querying
    """,
    responses={
        200: {
            "description": "List of events in the specified range",
            "content": {
                "application/json": {
                    "example": {
                        "items": [{
                        "id": 1,
                        "title": "Team Meeting",
                        "start_time": "2024-03-20T10:00:00Z",
                        "end_time": "2024-03-20T11:00:00Z",
                        "is_recurring": False
                        }],
                        "total": 1,
                        "page": 1,
                        "size": 10,
                        "filters_applied": {
                            "date_range": {
                                "start_date": "2024-03-20T00:00:00Z",
                                "end_date": "2024-03-21T00:00:00Z",
                                "include_recurring": True
                            }
                        }
                    }
                }
            }
        },
        400: {
            "description": "Invalid date range",
            "content": {
                "application/json": {
                    "example": {"detail": "End time must be after start time"}
                }
            }
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not enough permissions"},
        500: {"description": "Internal server error"}
    }
)
@cached(ttl=300)  # Cache for 5 minutes
async def list_events(
    *,
    db: AsyncSession = Depends(get_db),
    start_time: datetime = Query(..., description="Start of date range (ISO format)"),
    end_time: datetime = Query(..., description="End of date range (ISO format)"),
    include_recurring: bool = Query(True, description="Include recurring event occurrences"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user)
) -> EventListResponse:
    """
    List events in a date range.
    
    Parameters:
    - **start_time**: Start of date range (ISO format)
    - **end_time**: End of date range (ISO format)
    - **include_recurring**: Include recurring event occurrences (default: true)
    - **page**: Page number (default: 1)
    - **size**: Items per page (default: 10, max: 100)
    
    Returns a paginated list of events in the specified date range.
    """
    if end_time <= start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End time must be after start time"
        )
    
    try:
        # Calculate skip from page and size
        skip = (page - 1) * size
        
        # Get all events in the range
        all_events = await crud_event.get_events_in_range(
            db,
            current_user,
            start_time,
            end_time,
            include_recurring=include_recurring,
            skip=0,
            limit=None
        )
        
        # Calculate total for pagination
        total = len(all_events)
        
        # Get paginated events
        events = await crud_event.get_events_in_range(
            db,
            current_user,
            start_time,
            end_time,
            include_recurring=include_recurring,
            skip=skip,
            limit=size
        )
        
        event_responses = []
        for event_data in events:
            event = event_data["event"]
            event_response = await create_event_response(
                db,
                event,
                start_time=event_data["start_time"],
                end_time=event_data["end_time"]
            )
            event_responses.append(event_response)
        
        return EventListResponse(
            items=event_responses,
            total=total,
            page=page,
            size=size,
            filters_applied=EventFilter(
                date_range=DateRangeQuery(
                    start_date=start_time,
                    end_date=end_time,
                    include_recurring=include_recurring
                )
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/{event_id}",
    response_model=EventResponse,
    summary="Get event by ID",
    description="""
    Retrieve detailed information about a specific event.
    
    This endpoint provides:
    * Full event details
    * Permission information
    * Recurring event details if applicable
    * Latest version of the event
    """,
    responses={
        200: {
            "description": "Event details retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "title": "Team Meeting",
                        "description": "Weekly team sync",
                        "start_time": "2024-03-20T10:00:00Z",
                        "end_time": "2024-03-20T11:00:00Z",
                        "location": "Conference Room A",
                        "is_recurring": False,
                        "recurrence_pattern": None,
                        "created_by": {"id": 1, "email": "user@example.com"},
                        "created_at": "2024-03-19T15:00:00Z",
                        "updated_at": "2024-03-19T15:00:00Z"
                    }
                }
            }
        },
        404: {
            "description": "Event not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Event not found"}
                }
            }
        }
    }
)
@cached(ttl=60)  # Cache for 1 minute since event details might change frequently
async def get_event(
    *,
    db: AsyncSession = Depends(get_db),
    event_id: int,
    current_user: User = Depends(get_current_user)
) -> EventResponse:
    """
    Get detailed information about a specific event.
    
    Parameters:
    - **event_id**: ID of the event to retrieve
    
    Returns the event details if the user has permission to view it.
    """
    event = await crud_event.get_event(db, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Check permissions
    if not await crud_event.has_permission(db, event, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    owner = await crud_event.get_owner(db, event)
    return EventResponse(
        **event.__dict__,
        created_by={"id": owner.id, "email": owner.email}
    )

@router.put(
    "/{event_id}",
    response_model=EventResponse,
    summary="Update event",
    description="""
    Update an existing event's details.
    
    Features:
    * Partial updates supported
    * Automatic conflict detection
    * Version history tracking
    * Permission validation (requires EDITOR role)
    * Recurring event pattern updates
    """,
    responses={
        200: {
            "description": "Event updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "title": "Updated Team Meeting",
                        "description": "Weekly team sync - Updated agenda",
                        "start_time": "2024-03-20T10:30:00Z",
                        "end_time": "2024-03-20T11:30:00Z",
                        "location": "Conference Room B",
                        "is_recurring": False,
                        "recurrence_rule": None,
                        "updated_at": "2024-03-19T16:00:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid update data or conflict detected",
            "content": {
                "application/json": {
                    "example": {"detail": "Event conflicts with existing events"}
                }
            }
        },
        403: {
            "description": "Insufficient permissions",
            "content": {
                "application/json": {
                    "example": {"detail": "Not enough permissions"}
                }
            }
        }
    }
)
async def update_event(
    *,
    db: AsyncSession = Depends(get_db),
    event_id: int,
    event_in: EventUpdate,
    current_user: User = Depends(get_current_user),
    check_conflicts: bool = Query(True, description="Whether to check for conflicts with existing events")
):
    """
    Update an existing event.
    
    Parameters:
    - **event_id**: ID of the event to update
    - **event_in**: Updated event data (partial updates supported)
    - **check_conflicts**: Whether to check for conflicts (optional, default: true)
    
    Requires EDITOR role or higher.
    Creates a new version in the event history.
    """
    db_event = await crud_event.get_event(db, event_id)
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    if not db_event.has_permission(current_user, required_role=UserRole.EDITOR):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    try:
        updated_event = await crud_event.update_event(
            db,
            db_event,
            event_in,
            current_user,
            check_conflicts=check_conflicts
        )
        
        # Get owner info for response
        owner = await crud_event.get_owner(db, updated_event)
        
        # Create response model
        response_data = {
            "id": updated_event.id,
            "title": updated_event.title,
            "description": updated_event.description,
            "location": updated_event.location,
            "start_time": updated_event.start_time,
            "end_time": updated_event.end_time,
            "is_recurring": updated_event.is_recurring,
            "recurrence_pattern": updated_event.recurrence_pattern,
            "created_by": UserInfo(id=owner.id, email=owner.email),
            "created_at": updated_event.created_at,
            "updated_at": updated_event.updated_at
        }
        
        return EventResponse(**response_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete event",
    description="""
    Delete an event.
    
    Features:
    * Permission validation (requires OWNER role)
    * Option for hard delete or soft delete
    * Cascading deletion of related data
    * Version history tracking (for soft delete)
    """,
    responses={
        204: {
            "description": "Event successfully deleted"
        },
        403: {
            "description": "Insufficient permissions",
            "content": {
                "application/json": {
                    "example": {"detail": "Not enough permissions"}
                }
            }
        },
        404: {
            "description": "Event not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Event not found"}
                }
            }
        }
    }
)
async def delete_event(
    *,
    db: AsyncSession = Depends(get_db),
    event_id: int,
    current_user: User = Depends(get_current_user),
    hard_delete: bool = Query(False, description="Whether to permanently delete the event (true) or just mark as deleted (false)")
):
    """
    Delete an event.
    
    Parameters:
    - **event_id**: ID of the event to delete
    - **hard_delete**: Whether to permanently delete the event (default: false)
    
    Requires OWNER role.
    """
    event = await crud_event.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Check if user has permission to delete
    has_permission = await crud_event.has_permission(db, event, current_user, "OWNER")
    if not has_permission:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    await crud_event.delete_event(db, event, current_user, hard_delete=hard_delete)
    return None

@router.post(
    "/{event_id}/share",
    response_model=EventPermissionResponse,
    summary="Share event",
    description="""
    Share an event with another user by granting them specific permissions.
    
    Features:
    * Role-based access control (VIEWER, EDITOR, OWNER)
    * Permission validation
    * Automatic notification
    * Prevents duplicate permissions
    """,
    responses={
        200: {
            "description": "Permission granted successfully",
            "content": {
                "application/json": {
                    "example": {
                        "event_id": 1,
                        "user_id": 2,
                        "role": "EDITOR",
                        "granted_by": {"id": 1, "email": "owner@example.com"},
                        "granted_at": "2024-03-19T16:00:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid permission data",
            "content": {
                "application/json": {
                    "example": {"detail": "User already has access to this event"}
                }
            }
        },
        403: {
            "description": "Insufficient permissions",
            "content": {
                "application/json": {
                    "example": {"detail": "Not enough permissions"}
                }
            }
        }
    }
)
async def share_event(
    *,
    db: AsyncSession = Depends(get_db),
    event_id: int,
    permission_in: EventPermissionCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Share an event with another user.
    
    Parameters:
    - **event_id**: ID of the event to share
    - **permission_in**: Permission details including:
        - user_id: ID of the user to share with
        - role: Permission role (VIEWER, EDITOR, OWNER)
    
    Requires OWNER role to share the event.
    """
    db_event = await crud_event.get_event(db, event_id)
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    if not db_event.has_permission(current_user, required_role=UserRole.OWNER):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    try:
        permission = await crud_event.create_event_permission(
            db, db_event, permission_in, current_user
        )
        return permission
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/{event_id}/permissions",
    response_model=List[EventPermissionResponse],
    summary="List event permissions",
    description="""
    Get a list of all permissions for an event.
    
    Features:
    * Lists all users with access
    * Shows permission roles
    * Includes permission metadata
    * Filtered by user's access level
    """,
    responses={
        200: {
            "description": "List of permissions",
            "content": {
                "application/json": {
                    "example": [{
                        "event_id": 1,
                        "user_id": 1,
                        "role": "OWNER",
                        "granted_by": {"id": 1, "email": "owner@example.com"},
                        "granted_at": "2024-03-19T15:00:00Z"
                    }, {
                        "event_id": 1,
                        "user_id": 2,
                        "role": "EDITOR",
                        "granted_by": {"id": 1, "email": "owner@example.com"},
                        "granted_at": "2024-03-19T16:00:00Z"
                    }]
                }
            }
        }
    }
)
async def get_event_permissions(
    *,
    db: AsyncSession = Depends(get_db),
    event_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Get all permissions for an event.
    
    Parameters:
    - **event_id**: ID of the event
    
    Returns a list of all permissions if the user has access to the event.
    """
    db_event = await crud_event.get_event(db, event_id)
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    if not db_event.has_permission(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    permissions = await crud_event.get_event_permissions(db, db_event)
    return permissions

@router.put(
    "/{event_id}/permissions/{user_id}",
    response_model=EventPermissionResponse,
    summary="Update permission",
    description="""
    Update a user's permission level for an event.
    
    Features:
    * Role updates (VIEWER ↔ EDITOR ↔ OWNER)
    * Permission validation
    * Automatic notification
    * Change tracking
    """,
    responses={
        200: {
            "description": "Permission updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "event_id": 1,
                        "user_id": 2,
                        "role": "OWNER",
                        "granted_by": {"id": 1, "email": "previous_owner@example.com"},
                        "granted_at": "2024-03-19T17:00:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid role or user does not have access",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid role specified"}
                }
            }
        }
    }
)
async def update_event_permission(
    *,
    db: AsyncSession = Depends(get_db),
    event_id: int,
    user_id: int,
    new_role: str,
    current_user: User = Depends(get_current_user)
):
    """
    Update a user's permission level.
    
    Parameters:
    - **event_id**: ID of the event
    - **user_id**: ID of the user whose permission to update
    - **new_role**: New permission role (VIEWER, EDITOR, OWNER)
    
    Requires OWNER role to modify permissions.
    """
    db_event = await crud_event.get_event(db, event_id)
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    if not db_event.has_permission(current_user, required_role=UserRole.OWNER):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    try:
        permission = await crud_event.update_event_permission(
            db, db_event, user_id, new_role, current_user
        )
        return permission
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/{event_id}/permissions/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove permission",
    description="""
    Remove a user's access to an event.
    
    Features:
    * Permission validation
    * Automatic notification
    * Cannot remove owner's access
    * Cascading updates
    """,
    responses={
        204: {
            "description": "Permission successfully removed"
        },
        400: {
            "description": "Cannot remove permission",
            "content": {
                "application/json": {
                    "example": {"detail": "Cannot remove owner's access"}
                }
            }
        }
    }
)
async def delete_event_permission(
    *,
    db: AsyncSession = Depends(get_db),
    event_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Remove a user's access to an event.
    
    Parameters:
    - **event_id**: ID of the event
    - **user_id**: ID of the user whose access to remove
    
    Requires OWNER role.
    Cannot remove the owner's access.
    """
    db_event = await crud_event.get_event(db, event_id)
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    if not db_event.has_permission(current_user, required_role=UserRole.OWNER):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    try:
        await crud_event.delete_event_permission(db, db_event, user_id, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return None

@router.get(
    "/{event_id}/history/{version_id}",
    response_model=EventVersionResponse,
    summary="Get event version",
    description="""
    Get a specific version of an event.
    
    Features:
    * Version details
    * Change tracking
    * Permission validation
    """,
    responses={
        200: {
            "description": "Event version retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "version_id": 1,
                        "event_id": 1,
                        "data": {
                            "title": "Team Meeting",
                            "description": "Weekly team sync",
                            "start_time": "2024-03-20T10:00:00Z",
                            "end_time": "2024-03-20T11:00:00Z"
                        },
                        "created_by": {"id": 1, "email": "user@example.com"},
                        "created_at": "2024-03-19T15:00:00Z"
                    }
                }
            }
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not enough permissions"},
        404: {"description": "Event or version not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_event_version(
    *,
    db: AsyncSession = Depends(get_db),
    event_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get a specific version of an event"""
    db_event = await crud_event.get_event(db, event_id)
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    if not db_event.has_permission(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    version = await crud_event.get_event_version(db, db_event, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    return version

@router.get(
    "/{event_id}/history",
    response_model=List[EventVersionResponse],
    summary="Get event history",
    description="""
    Get the version history of an event.
    
    Features:
    * Complete version history
    * Pagination support
    * Permission validation
    * Change tracking
    """,
    responses={
        200: {
            "description": "Event history retrieved successfully",
            "content": {
                "application/json": {
                    "example": [{
                        "version_id": 2,
                        "event_id": 1,
                        "data": {
                            "title": "Updated Team Meeting",
                            "description": "Weekly team sync - Updated",
                            "start_time": "2024-03-20T10:30:00Z",
                            "end_time": "2024-03-20T11:30:00Z"
                        },
                        "created_by": {"id": 1, "email": "user@example.com"},
                        "created_at": "2024-03-19T16:00:00Z"
                    }, {
                        "version_id": 1,
                        "event_id": 1,
                        "data": {
                            "title": "Team Meeting",
                            "description": "Weekly team sync",
                            "start_time": "2024-03-20T10:00:00Z",
                            "end_time": "2024-03-20T11:00:00Z"
                        },
                        "created_by": {"id": 1, "email": "user@example.com"},
                        "created_at": "2024-03-19T15:00:00Z"
                    }]
                }
            }
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not enough permissions"},
        404: {"description": "Event not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_event_history(
    *,
    db: AsyncSession = Depends(get_db),
    event_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user)
):
    """Get the version history of an event"""
    # Get the event
    db_event = await crud_event.get_event(db, event_id)
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Check permissions
    if not db_event.has_permission(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Get all versions
    versions = await crud_event.get_event_versions(db, db_event, skip=skip, limit=limit)
    
    # Debug log
    print(f"Endpoint returning {len(versions)} versions for event {event_id}")
    
    # Convert to response model
    return versions

@router.post(
    "/{event_id}/rollback/{version_id}",
    response_model=EventResponse,
    summary="Rollback event",
    description="""
    Rollback an event to a specific version.
    
    Features:
    * Version restoration
    * Permission validation
    * Change tracking
    * New version creation
    """,
    responses={
        200: {
            "description": "Event rolled back successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "title": "Team Meeting",
                        "description": "Weekly team sync",
                        "start_time": "2024-03-20T10:00:00Z",
                        "end_time": "2024-03-20T11:00:00Z",
                        "location": "Conference Room A",
                        "is_recurring": False,
                        "recurrence_rule": None,
                        "created_by": {"id": 1, "email": "user@example.com"},
                        "created_at": "2024-03-19T15:00:00Z",
                        "updated_at": "2024-03-19T17:00:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid version",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid version ID"}
                }
            }
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not enough permissions"},
        404: {"description": "Event or version not found"},
        500: {"description": "Internal server error"}
    }
)
async def rollback_event(
    *,
    db: AsyncSession = Depends(get_db),
    event_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user)
):
    """Rollback an event to a specific version"""
    db_event = await crud_event.get_event(db, event_id)
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    if not db_event.has_permission(current_user, required_role=UserRole.EDITOR):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    try:
        updated_event = await crud_event.rollback_event(db, db_event, version_id, current_user)
        
        # Get the owner information for the response
        owner = await crud_event.get_owner(db, updated_event)
        
        # Convert to the expected response format
        return EventResponse(
            id=updated_event.id,
            title=updated_event.title,
            description=updated_event.description,
            location=updated_event.location,
            start_time=updated_event.start_time,
            end_time=updated_event.end_time,
            is_recurring=updated_event.is_recurring,
            recurrence_pattern=updated_event.recurrence_pattern,
            created_by=UserInfo(id=owner.id, email=owner.email),
            created_at=updated_event.created_at,
            updated_at=updated_event.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/{event_id}/diff/{version_id1}/{version_id2}",
    response_model=EventVersionDiff,
    summary="Get event version diff",
    description="""
    Get the difference between two versions of an event.
    
    Features:
    * Field-by-field comparison
    * Change tracking
    * Permission validation
    * Metadata about changes
    """,
    responses={
        200: {
            "description": "Version difference retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "version1": 1,
                        "version2": 2,
                        "changes": {
                            "title": {
                                "old": "Team Meeting",
                                "new": "Updated Team Meeting"
                            },
                            "location": {
                                "old": "Conference Room A",
                                "new": "Conference Room B"
                            }
                        },
                        "changed_by": {"id": 1, "email": "user@example.com"},
                        "changed_at": "2024-03-19T16:00:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid version IDs",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid version IDs specified"}
                }
            }
        }
    }
)
async def get_event_diff(
    *,
    db: AsyncSession = Depends(get_db),
    event_id: int,
    version_id1: int,
    version_id2: int,
    current_user: User = Depends(get_current_user)
) -> EventVersionDiff:
    """Get the difference between two versions of an event"""
    db_event = await crud_event.get_event(db, event_id)
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    if not db_event.has_permission(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    try:
        diff = await crud_event.get_event_diff(db, db_event, version_id1, version_id2)
        return EventVersionDiff(**diff)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) 