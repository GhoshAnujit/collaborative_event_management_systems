from datetime import datetime, timedelta, UTC
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.event import Event
from app.models.permission import EventPermission
from app.models.version import EventVersion
from app.models.user import User
from app.models.enums import PermissionRole, UserRole
from app.schemas.event import (
    EventCreate, EventUpdate, EventBatchCreate,
    EventPermissionCreate, EventFilter, DateRangeQuery,
    BaseSchema
)
from app.core.websocket import ws_manager
from app.crud import notification as crud_notification
from app.schemas.notification import WebSocketMessage
from app.core.exceptions import PermissionDenied, ResourceNotFound

async def _notify_event_users(
    db: AsyncSession,
    event: Event,
    notification_type: str,
    message: str,
    data: Dict[str, Any],
    exclude_user_id: int | None = None
) -> None:
    """Helper function to notify users about event changes"""
    # Get all users with access to the event
    users = {event.owner_id}
    
    # Get permissions with eager loading
    result = await db.execute(
        select(EventPermission)
        .where(EventPermission.event_id == event.id)
    )
    permissions = result.scalars().all()
    
    for permission in permissions:
        users.add(permission.user_id)
    
    # Remove excluded user if any
    if exclude_user_id is not None:
        users.discard(exclude_user_id)
    
    # Create notifications and send WebSocket messages
    if users:
        notifications = await crud_notification.create_event_notification(
            db,
            event.id,
            list(users),
            notification_type,
            message,
            data
        )
        await ws_manager.broadcast(users, "notification", {
            "type": notification_type,
            "event_id": event.id,
            "message": message,
            "data": data
        })

def _serialize_event_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to serialize event data for version storage"""
    serialized = {}
    for key, value in data.items():
        # Skip internal SQLAlchemy attributes
        if key.startswith('_sa_'):
            continue
            
        # Handle datetime objects
        if isinstance(value, datetime):
            serialized[key] = value.isoformat()
        # Handle nested dictionaries
        elif isinstance(value, dict):
            serialized[key] = _serialize_event_data(value)
        # Handle lists/iterables that might contain datetime objects
        elif isinstance(value, (list, tuple)):
            serialized[key] = [
                item.isoformat() if isinstance(item, datetime) else item
                for item in value
            ]
        # Handle SQLAlchemy objects by excluding them
        elif hasattr(value, '_sa_instance_state'):
            # Skip SQLAlchemy objects or relationships
            continue
        # Handle other types
        else:
            serialized[key] = value
    return serialized

async def create_event(
    db: AsyncSession, 
    event_in: EventCreate, 
    owner: User,
    check_conflicts: bool = True
) -> Event:
    """Create a new event"""
    event_data = event_in.model_dump(exclude_unset=True)
    now = datetime.now(UTC)
    
    # Create the event instance
    db_event = Event(
        **event_data,
        owner_id=owner.id,
        current_version=1,
        is_deleted=False,
        updated_at=now
    )
    
    # Check for conflicts if requested
    if check_conflicts:
        conflicts = await db_event.check_conflicts(
            db,
            db_event.start_time,
            db_event.end_time,
            exclude_self=False
        )
        if conflicts:
            raise ValueError("Event conflicts with existing events")
    
    db.add(db_event)
    await db.flush()
    
    # Create owner permission
    permission = EventPermission(
        event_id=db_event.id,
        user_id=owner.id,
        role=PermissionRole.OWNER,
        created_at=now,
        updated_at=now
    )
    db.add(permission)
    
    # Create initial version
    version = EventVersion(
        event_id=db_event.id,
        version_number=1,
        changed_by_id=owner.id,
        event_data=_serialize_event_data(db_event.to_dict()),
        changes={},
        created_at=now,
        updated_at=now
    )
    db.add(version)
    
    await db.commit()
    await db.refresh(db_event)
    
    return db_event

async def create_events_batch(
    db: AsyncSession,
    events_in: EventBatchCreate,
    owner: User,
    check_conflicts: bool = True
) -> List[Event]:
    """Create multiple events in a batch"""
    now = datetime.now(UTC)
    db_events = []
    
    # First check for conflicts across all events if requested
    if check_conflicts:
        for event_in in events_in.events:
            event_data = event_in.model_dump(exclude_unset=True)
            db_event = Event(
                **event_data,
                owner_id=owner.id,
                current_version=1,
                is_deleted=False,
                updated_at=now
            )
            conflicts = await db_event.check_conflicts(
                db,
                db_event.start_time,
                db_event.end_time,
                exclude_self=False
            )
    if conflicts:
                raise ValueError(f"Event '{event_in.title}' conflicts with existing events")
    
    # Create all events
    for event_in in events_in.events:
        event_data = event_in.model_dump(exclude_unset=True)
        db_event = Event(
            **event_data,
            owner_id=owner.id,
            current_version=1,
            is_deleted=False,
            updated_at=now
        )
        db.add(db_event)
        db_events.append(db_event)
    
    await db.flush()
    
    # Create permissions and versions for all events
    for db_event in db_events:
        # Create owner permission
        permission = EventPermission(
            event_id=db_event.id,
            user_id=owner.id,
            role=PermissionRole.OWNER,
            created_at=now,
            updated_at=now
        )
        db.add(permission)
        
        # Create initial version
        version = EventVersion(
            event_id=db_event.id,
            version_number=1,
            changed_by_id=owner.id,
            event_data=_serialize_event_data(db_event.to_dict()),
            changes={},
            created_at=now,
            updated_at=now
        )
        db.add(version)
    
    await db.commit()
    for db_event in db_events:
        await db.refresh(db_event)
    
    return db_events

async def get_event(
    db: AsyncSession, 
    event_id: int,
    include_permissions: bool = False,
    include_versions: bool = False
) -> Optional[Event]:
    """Get an event by ID"""
    query = select(Event).where(
        and_(
            Event.id == event_id,
            Event.is_deleted == False
        )
    )
    
    if include_permissions:
        query = query.options(selectinload(Event.permissions))
    if include_versions:
        query = query.options(selectinload(Event.versions))
    
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_events_by_owner(
    db: AsyncSession, 
    owner_id: int,
    skip: int = 0,
    limit: int = 100
) -> List[Event]:
    """Get events by owner ID"""
    result = await db.execute(
        select(Event)
        .where(
            Event.owner_id == owner_id,
            Event.is_deleted == False
        )
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def update_event(
    db: AsyncSession, 
    db_event: Event, 
    event_in: EventUpdate,
    user: User,
    check_conflicts: bool = True
) -> Event:
    """Update an event"""
    # Make sure the user has edit permissions
    if not await has_permission(db, db_event, user, "EDITOR"):
        raise ValueError("Not enough permissions")
    
    # Check for conflicts if requested
    if check_conflicts:
        # Get the event data
        update_data = event_in.model_dump(exclude_unset=True)
        start_time = update_data.get("start_time", db_event.start_time)
        end_time = update_data.get("end_time", db_event.end_time)
        
        # Ensure start_time and end_time are timezone-aware
        if start_time and not start_time.tzinfo:
            start_time = start_time.replace(tzinfo=UTC)
        if end_time and not end_time.tzinfo:
            end_time = end_time.replace(tzinfo=UTC)
        
        # Validate that end_time is after start_time
        if start_time and end_time and start_time >= end_time:
            raise ValueError("End time must be after start time")
        
        # Check for conflicts with other events
        conflicts = await db_event.check_conflicts(
            db, 
            start_time, 
            end_time, 
            exclude_self=True
        )
        if conflicts:
            raise ValueError("Event conflicts with existing events")
    
    # Store the original event data for versioning
    old_event_data = _serialize_event_data(db_event.to_dict())
    
    # Update event attributes
    update_data = event_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_event, field, value)
    
    # Update version and timestamp
    now = datetime.now(UTC)
    db_event.current_version += 1
    db_event.updated_at = now
    
    # Create a new version record with serialized changes
    changes = {}
    for k in update_data.keys():
        old_value = old_event_data.get(k)
        # For datetime objects, convert to string for JSON serialization
        if isinstance(update_data[k], datetime):
            new_value = update_data[k].isoformat()
        else:
            new_value = update_data[k]
        changes[k] = {"old": old_value, "new": new_value}
    
    version = EventVersion(
        event_id=db_event.id,
        version_number=db_event.current_version,
        changed_by_id=user.id,
        event_data=old_event_data,
        changes=changes,
        created_at=now,
        updated_at=now
    )
    
    # Add the version to the database
    db.add(version)
    
    # Save changes
    await db.commit()
    await db.refresh(db_event)
    
    # Notify users about the update
    await _notify_event_users(
        db, 
        db_event, 
        "EVENT_UPDATED", 
        f"Event {db_event.title} was updated",
        {"event_id": db_event.id, "updater_id": user.id},
        exclude_user_id=user.id
    )
    
    return db_event

async def delete_event(
    db: AsyncSession, 
    db_event: Event,
    user: User,
    hard_delete: bool = False
) -> None:
    """Delete an event"""
    if hard_delete:
        # Permanently delete the event
        await db.delete(db_event)
        await db.commit()
        return
        
    now = datetime.now(UTC)
    db_event.is_deleted = True
    db_event.updated_at = now
    
    # Create final version with properly serialized event data
    event_data = _serialize_event_data(db_event.to_dict())
    
    version = EventVersion(
        event_id=db_event.id,
        version_number=db_event.current_version + 1,
        changed_by_id=user.id,
        event_data=event_data,
        changes={"is_deleted": True},
        change_description="Event deleted",
        created_at=now,
        updated_at=now
    )
    
    db.add(version)
    await db.commit()
    
    # Notify about event deletion
    await _notify_event_users(
        db,
        db_event,
        "event.delete",
        f"Event deleted: {db_event.title}",
        {"event": {"id": db_event.id, "title": db_event.title}},
        exclude_user_id=user.id
    )

async def get_user_accessible_events(
    db: AsyncSession,
    user: User,
    skip: int = 0,
    limit: int = 100
) -> List[Event]:
    """Get all events a user can access"""
    # Get owned events
    owned_result = await db.execute(
        select(Event)
        .where(
            Event.owner_id == user.id,
            Event.is_deleted == False
        )
    )
    owned_events = owned_result.scalars().all()
    
    # Get events with permissions
    # This could be optimized with a join
    from app.models.permission import EventPermission
    
    perm_result = await db.execute(
        select(Event)
        .join(EventPermission, EventPermission.event_id == Event.id)
        .where(
            EventPermission.user_id == user.id,
            Event.is_deleted == False
        )
    )
    perm_events = perm_result.scalars().all()
    
    # Combine and deduplicate
    all_events = {event.id: event for event in owned_events + perm_events}
    return list(all_events.values())[skip:skip+limit] 

async def create_event_permission(
    db: AsyncSession,
    event: Event,
    permission_in: EventPermissionCreate,
    granting_user: User
) -> EventPermission:
    """Create a new event permission"""
    # Validate the role
    try:
        role = PermissionRole(permission_in.role)
    except ValueError:
        raise ValueError(f"Invalid permission role: {permission_in.role}")
    
    # Prevent granting OWNER role - there should only be one owner
    if role == PermissionRole.OWNER and event.owner_id != permission_in.user_id:
        raise ValueError("Cannot grant OWNER role to a different user")
    
    # Check that the user exists
    user = await db.get(User, permission_in.user_id)
    if not user:
        raise ValueError("User not found")
    
    # Check if permission already exists
    result = await db.execute(
        select(EventPermission)
        .where(
            EventPermission.event_id == event.id,
            EventPermission.user_id == permission_in.user_id
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise ValueError("Permission already exists for this user")
    
    # Create permission
    now = datetime.now(UTC)
    permission = EventPermission(
        event_id=event.id,
        user_id=permission_in.user_id,
        role=role,
        created_at=now,
        updated_at=now
    )
    db.add(permission)
    
    # Create a version entry for this permission change
    event.current_version += 1
    event.updated_at = now
    
    # Prepare changes data
    changes = {
        "permissions": {
            "added": {
                "user_id": permission_in.user_id,
                "role": role.value
            }
        }
    }
    
    # Create version with proper serialization
    version = EventVersion(
        event_id=event.id,
        version_number=event.current_version,
        changed_by_id=granting_user.id,
        event_data=_serialize_event_data(event.to_dict()),
        changes=_serialize_event_data(changes),
        change_description=f"Added {role.value} permission for user {permission_in.user_id}",
        created_at=now,
        updated_at=now
    )
    
    db.add(version)
    db.add(event)
    await db.commit()
    await db.refresh(permission)
    
    # Notify the user about the permission grant
    await _notify_event_users(
        db,
        event,
        "permission.grant",
        f"You've been given {role.value} access to: {event.title}",
        {
            "event": {"id": event.id, "title": event.title},
            "permission": {"role": role.value}
        },
        exclude_user_id=granting_user.id
    )
    
    return permission

async def update_event_permission(
    db: AsyncSession,
    event: Event,
    user_id: int,
    new_role: str,
    updating_user: User
) -> EventPermission:
    """Update an event permission"""
    # Validate the role
    try:
        role = PermissionRole(new_role)
    except ValueError:
        raise ValueError(f"Invalid permission role: {new_role}")
    
    # Prevent changing OWNER role - there should only be one owner
    if role == PermissionRole.OWNER and event.owner_id != user_id:
        raise ValueError("Cannot change to OWNER role")
    
    # Get the existing permission
    result = await db.execute(
        select(EventPermission)
        .where(
            EventPermission.event_id == event.id,
            EventPermission.user_id == user_id
        )
    )
    permission = result.scalar_one_or_none()
    
    if not permission:
        raise ValueError("Permission not found")
    
    # Cannot change the owner's role
    if event.owner_id == user_id:
        raise ValueError("Cannot change the event owner's role")
    
    # Store the old role for version history
    old_role = permission.role
    
    # Update the permission
    now = datetime.now(UTC)
    permission.role = role
    permission.updated_at = now
    
    # Create a version entry for this permission change
    event.current_version += 1
    event.updated_at = now
    
    # Prepare changes data
    changes = {
        "permissions": {
            "updated": {
                "user_id": user_id,
                "old_role": old_role.value,
                "new_role": role.value
            }
        }
    }
    
    # Create version with proper serialization
    version = EventVersion(
        event_id=event.id,
        version_number=event.current_version,
        changed_by_id=updating_user.id,
        event_data=_serialize_event_data(event.to_dict()),
        changes=_serialize_event_data(changes),
        change_description=f"Updated permission for user {user_id} from {old_role.value} to {role.value}",
        created_at=now,
        updated_at=now
    )
    
    db.add(version)
    db.add(permission)
    db.add(event)
    await db.commit()
    await db.refresh(permission)
    
    # Notify the user about the permission update
    await _notify_event_users(
        db,
        event,
        "permission.update",
        f"Your access to {event.title} has been updated to {role.value}",
        {
            "event": {"id": event.id, "title": event.title},
            "permission": {"role": role.value, "previous_role": old_role.value}
        },
        exclude_user_id=updating_user.id
    )
    
    return permission

async def delete_event_permission(
    db: AsyncSession,
    event: Event,
    user_id: int,
    deleting_user: User
) -> None:
    """Delete an event permission"""
    # Cannot remove the owner's permission
    if event.owner_id == user_id:
        raise ValueError("Cannot remove the event owner's permission")
    
    # Get the existing permission
    result = await db.execute(
        select(EventPermission)
        .where(
            EventPermission.event_id == event.id,
            EventPermission.user_id == user_id
        )
    )
    permission = result.scalar_one_or_none()
    
    if not permission:
        raise ValueError("Permission not found")
    
    # Store the role for version history
    old_role = permission.role
    
    # Delete the permission
    await db.delete(permission)
    
    # Create a version entry for this permission change
    now = datetime.now(UTC)
    event.current_version += 1
    event.updated_at = now
    
    # Prepare changes data
    changes = {
        "permissions": {
            "removed": {
                "user_id": user_id,
                "role": old_role.value
            }
        }
    }
    
    # Create version with proper serialization
    version = EventVersion(
        event_id=event.id,
        version_number=event.current_version,
        changed_by_id=deleting_user.id,
        event_data=_serialize_event_data(event.to_dict()),
        changes=_serialize_event_data(changes),
        change_description=f"Removed {old_role.value} permission for user {user_id}",
        created_at=now,
        updated_at=now
    )
    
    db.add(version)
    db.add(event)
    await db.commit()
    
    # Notify the user about the permission removal
    await _notify_event_users(
        db,
        event,
        "permission.revoke",
        f"Your access to {event.title} has been removed",
        {
            "event": {"id": event.id, "title": event.title},
            "permission": {"previous_role": old_role.value}
        },
        exclude_user_id=deleting_user.id
    )

async def get_event_permissions(
    db: AsyncSession,
    event: Event
) -> List[EventPermission]:
    """Get all permissions for an event"""
    result = await db.execute(
        select(EventPermission).where(
            EventPermission.event_id == event.id
        )
    )
    return result.scalars().all()

async def get_event_version(
    db: AsyncSession,
    event: Event,
    version_number: int
) -> Optional[EventVersion]:
    """Get a specific version of an event"""
    result = await db.execute(
        select(EventVersion).where(
            EventVersion.event_id == event.id,
            EventVersion.version_number == version_number
        )
    )
    return result.scalar_one_or_none()

async def get_event_versions(
    db: AsyncSession,
    event: Event,
    skip: int = 0,
    limit: int = 100
) -> List[EventVersion]:
    """Get all versions of an event"""
    # Ensure we have valid values for skip and limit
    skip = 0 if skip is None else int(skip)
    limit = 100 if limit is None else int(limit)
    
    result = await db.execute(
        select(EventVersion)
        .where(EventVersion.event_id == event.id)
        .order_by(EventVersion.version_number.desc())
        .offset(skip)
        .limit(limit)
    )
    versions = result.scalars().all()
    
    # Debug logging to help identify the issue
    print(f"Found {len(versions)} versions for event {event.id}")
    if versions:
        version_numbers = [v.version_number for v in versions]
        print(f"Version numbers: {version_numbers}")
    
    return versions

async def rollback_event(
    db: AsyncSession,
    event: Event,
    version_number: int,
    user: User
) -> Event:
    """Rollback an event to a specific version"""
    # Get the target version
    target_version = await get_event_version(db, event, version_number)
    if not target_version:
        raise ValueError(f"Version {version_number} not found")
    
    if version_number >= event.current_version:
        raise ValueError("Cannot rollback to a future or current version")
    
    # Get the event data from the target version
    event_data = target_version.event_data
    
    # Create a new version for the rollback
    changes = {
        "rollback": {
            "from_version": event.current_version,
            "to_version": version_number,
            "changes": {k: {"old": getattr(event, k), "new": v} 
                       for k, v in event_data.items() 
                       if k not in ["id", "current_version", "versions", "permissions"]}
        }
    }
    
    now = datetime.now(UTC)
    version = EventVersion(
        event_id=event.id,
        version_number=event.current_version + 1,
        changed_by_id=user.id,
        event_data=_serialize_event_data(event.to_dict()),
        changes=_serialize_event_data(changes),
        change_description=f"Rolled back to version {version_number}",
        created_at=now,
        updated_at=now
    )
    db.add(version)
    
    # Update event with data from target version
    for field, value in event_data.items():
        if field not in ["id", "current_version", "versions", "permissions"]:
            # Handle datetime fields - convert ISO format strings to datetime objects
            if field in ["start_time", "end_time", "created_at", "updated_at"] and value:
                if isinstance(value, str):
                    try:
                        # Parse ISO format datetime strings
                        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        # If parsing fails, skip this field to avoid errors
                        continue
            
            setattr(event, field, value)
    
    # Update metadata fields
    event.current_version += 1
    event.updated_at = now
    
    await db.commit()
    await db.refresh(event)
    return event

async def get_event_diff(
    db: AsyncSession,
    event: Event,
    version1: int,
    version2: int
) -> Dict[str, Any]:
    """Get the difference between two versions of an event"""
    v1 = await get_event_version(db, event, version1)
    v2 = await get_event_version(db, event, version2)
    
    if not v1 or not v2:
        raise ValueError("One or both versions not found")
    
    # Get the changes directly from the version record
    # In our version model, we already store the changes made for each version
    changes = {}
    if version2 > version1:
        # If going forward in versions, use the stored changes from v2
        changes = v2.changes
    else:
        # If going backward (rollback scenario), we need to compute reverse changes
        # This is simplified for now
        for field, values in v1.changes.items():
            if isinstance(values, dict) and "old" in values and "new" in values:
                changes[field] = {
                    "old": values["new"],
                    "new": values["old"]
                }
    
    # If changes is still empty but we know the data is different, 
    # compute changes by comparing the event data directly
    if not changes:
        all_fields = set(v1.event_data.keys()) | set(v2.event_data.keys())
        for field in all_fields:
            # Skip system fields
            if field in ["id", "current_version", "versions", "permissions", 
                        "created_at", "updated_at", "_sa_instance_state"]:
                continue
            
            old_value = v1.event_data.get(field)
            new_value = v2.event_data.get(field)
            
            if old_value != new_value:
                changes[field] = {
                    "old": old_value,
                    "new": new_value
                }
    
    # Format the response according to the EventVersionDiff schema
    return {
        "version1": version1,
        "version2": version2,
        "changes": changes,
        "changed_by": {"id": v2.changed_by_id},
        "changed_at": v2.created_at
    }

async def get_events_in_range(
    db: AsyncSession,
    user: User,
    start_time: datetime,
    end_time: datetime,
    include_recurring: bool = True,
    skip: int = 0,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Get all events (including recurring occurrences) in a date range"""
    # Ensure skip and limit are valid integers with defaults
    skip = 0 if skip is None else int(skip)
    limit = 100 if limit is None else int(limit)
    
    # Get base events that the user can access
    events = await get_user_accessible_events(db, user, skip=0, limit=None)
    
    # Filter events in the date range and handle recurring events
    result = []
    for event in events:
        if event.is_recurring and include_recurring:
            # Get all occurrences in the range
            occurrences = event.get_occurrences(start_time, end_time)
            for occurrence in occurrences:
                result.append({
                    "event": event,
                    "start_time": occurrence["start_time"],
                    "end_time": occurrence["end_time"],
                    "is_recurring": True,
                    "is_original": occurrence["is_original"]
                })
        else:
            # Check if non-recurring event falls in the range
            if start_time <= event.start_time <= end_time:
                result.append({
                    "event": event,
                    "start_time": event.start_time,
                    "end_time": event.end_time,
                    "is_recurring": False,
                    "is_original": True
                })
    
    # Sort by start time
    result.sort(key=lambda x: x["start_time"])
    
    # Apply pagination - safely handle the case where skip or limit might be None
    if not result:
        return []
        
    end_idx = min(skip + limit, len(result))
    if skip >= len(result):
        return []
        
    return result[skip:end_idx]

async def has_permission(
    db: AsyncSession,
    event: Event,
    user: User,
    required_role: str = "VIEWER"
) -> bool:
    """Check if a user has the required permission level for this event"""
    if user.is_superuser or user.id == event.owner_id:
        return True
        
    result = await db.execute(
        select(EventPermission)
        .where(
            EventPermission.event_id == event.id,
            EventPermission.user_id == user.id
        )
    )
    permission = result.scalar_one_or_none()
    
    if permission:
        role_values = {
            "OWNER": 3,
            "EDITOR": 2,
            "VIEWER": 1
        }
        return role_values[permission.role] >= role_values[required_role]
    return False 

async def get_owner(db: AsyncSession, event: Event) -> User:
    """Get the owner of an event."""
    owner = await db.get(User, event.owner_id)
    if not owner:
        raise ValueError("Event owner not found")
    return owner 