from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, UTC
from sqlalchemy import select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationCreate, NotificationUpdate

async def create_notification(
    db: AsyncSession,
    notification: NotificationCreate
) -> Notification:
    """Create a new notification."""
    current_time = datetime.now(UTC)
    db_notification = Notification(
        user_id=notification.user_id,
        event_id=notification.event_id,
        type=notification.type,
        message=notification.message,
        data=notification.data,
        is_read=False,
        updated_at=current_time
    )
    db.add(db_notification)
    await db.commit()
    await db.refresh(db_notification)
    return db_notification

async def get_notification(
    db: AsyncSession,
    notification_id: int,
    user_id: int
) -> Optional[Notification]:
    """Get a specific notification."""
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.user_id == user_id
            )
        )
    )
    return result.scalar_one_or_none()

async def get_user_notifications(
    db: AsyncSession,
    user_id: int,
    unread_only: bool = False
) -> List[Notification]:
    """Get all notifications for a user."""
    query = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        query = query.where(Notification.is_read == False)
    query = query.order_by(Notification.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())

async def mark_notification_read(
    db: AsyncSession,
    notification_id: int,
    user_id: int
) -> Optional[Notification]:
    """Mark a notification as read."""
    notification = await get_notification(db, notification_id, user_id)
    if notification:
        notification.is_read = True
        notification.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(notification)
    return notification

async def delete_notification(
    db: AsyncSession,
    notification_id: int,
    user_id: int
) -> bool:
    """Delete a notification."""
    notification = await get_notification(db, notification_id, user_id)
    if notification:
        await db.delete(notification)
        await db.commit()
        return True
    return False

async def mark_all_read(
    db: AsyncSession,
    user_id: int
) -> int:
    """Mark all notifications as read for a user."""
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.user_id == user_id,
                Notification.is_read == False
            )
        )
    )
    notifications = result.scalars().all()
    current_time = datetime.now(UTC)
    count = 0
    for notification in notifications:
        notification.is_read = True
        notification.updated_at = current_time
        count += 1
    await db.commit()
    return count

async def delete_old_notifications(
    db: AsyncSession,
    days: int = 30
) -> None:
    """Delete notifications older than specified days"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    await db.execute(
        delete(Notification).where(Notification.created_at < cutoff_date)
    )
    await db.commit()

async def create_event_notification(
    db: AsyncSession,
    event_id: int,
    user_ids: List[int],
    notification_type: str,
    message: str,
    data: Dict[str, Any] = None
) -> List[Notification]:
    """Create notifications for multiple users about an event"""
    notifications = []
    for user_id in user_ids:
        notification = await create_notification(
            db,
            NotificationCreate(
                user_id=user_id,
                event_id=event_id,
                type=notification_type,
                message=message,
                data=data or {}
            )
        )
        notifications.append(notification)
    return notifications 