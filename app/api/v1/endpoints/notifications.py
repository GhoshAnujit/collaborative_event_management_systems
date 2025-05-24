from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.core.websocket import ws_manager
from app.db.database import get_db
from app.models.user import User
from app.schemas.notification import NotificationResponse, NotificationUpdate, NotificationCreate, WebSocketMessage
from app.crud import notification as crud_notification
from app.api.v1.endpoints.auth import get_current_user_from_token
from app.core.websocket_limiter import ws_limiter
from app.core.security import get_current_user_ws

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized"},
        404: {"description": "Resource not found"},
        500: {"description": "Internal server error"}
    }
)

@router.get(
    "/",
    response_model=List[NotificationResponse],
    status_code=status.HTTP_200_OK,
    summary="List notifications",
    description="""
    Get a list of notifications for the current user.
    
    Features:
    * Pagination support
    * Filter for unread notifications
    * Sorted by creation time (newest first)
    * Includes notification metadata
    """,
    responses={
        200: {
            "description": "List of notifications",
            "content": {
                "application/json": {
                    "example": [{
                        "id": 1,
                        "type": "EVENT_SHARE",
                        "title": "Event Shared",
                        "message": "John Doe shared 'Team Meeting' with you",
                        "event_id": 123,
                        "is_read": False,
                        "created_at": "2024-03-19T15:00:00Z"
                    }, {
                        "id": 2,
                        "type": "EVENT_UPDATE",
                        "title": "Event Updated",
                        "message": "Time changed for 'Team Meeting'",
                        "event_id": 123,
                        "is_read": True,
                        "created_at": "2024-03-19T14:00:00Z"
                    }]
                }
            }
        },
        400: {
            "description": "Invalid parameters",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid pagination parameters"}
                }
            }
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not enough permissions"},
        500: {"description": "Internal server error"}
    }
)
async def list_notifications(
    *,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of notifications to skip (pagination)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of notifications to return"),
    unread_only: bool = Query(False, description="Only show unread notifications"),
    current_user: User = Depends(get_current_user_from_token)
) -> List[NotificationResponse]:
    """
    List notifications for the current user.
    
    Parameters:
    - **skip**: Number of notifications to skip (default: 0)
    - **limit**: Maximum number of notifications to return (default: 100, max: 1000)
    - **unread_only**: Whether to show only unread notifications (default: false)
    
    Returns a paginated list of notifications sorted by creation time (newest first).
    """
    try:
        notifications = await crud_notification.get_user_notifications(
            db,
            current_user.id,
            unread_only=unread_only
        )
        
        # Apply pagination manually
        start = skip
        end = skip + limit
        paginated_notifications = notifications[start:end]
        
        return paginated_notifications
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark as read",
    description="""
    Mark a specific notification as read.
    
    Features:
    * Permission validation
    * Automatic WebSocket update
    * Updates read timestamp
    """,
    responses={
        200: {
            "description": "Notification marked as read",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "type": "EVENT_SHARE",
                        "title": "Event Shared",
                        "message": "John Doe shared 'Team Meeting' with you",
                        "event_id": 123,
                        "is_read": True,
                        "created_at": "2024-03-19T15:00:00Z",
                        "read_at": "2024-03-19T16:00:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid input",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid notification ID"}
                }
            }
        },
        401: {"description": "Not authenticated"},
        403: {
            "description": "Not your notification",
            "content": {
                "application/json": {
                    "example": {"detail": "Not your notification"}
                }
            }
        },
        404: {
            "description": "Notification not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Notification not found"}
                }
            }
        },
        500: {"description": "Internal server error"}
    }
)
async def mark_notification_read(
    *,
    db: AsyncSession = Depends(get_db),
    notification_id: int,
    current_user: User = Depends(get_current_user_from_token)
) -> NotificationResponse:
    """
    Mark a notification as read.
    
    Parameters:
    - **notification_id**: ID of the notification to mark as read
    
    The notification must belong to the current user.
    """
    try:
        notification = await crud_notification.get_notification(db, notification_id, current_user.id)
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        updated_notification = await crud_notification.mark_notification_read(db, notification_id, current_user.id)
        return updated_notification
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put(
    "/read-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark all as read",
    description="""
    Mark all notifications as read for the current user.
    
    Features:
    * Bulk update operation
    * Automatic WebSocket update
    * Updates read timestamp for all notifications
    """,
    responses={
        204: {
            "description": "All notifications marked as read"
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not enough permissions"},
        500: {"description": "Internal server error"}
    }
)
async def mark_all_notifications_read(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
) -> None:
    """
    Mark all notifications as read for the current user.
    
    This is a bulk operation that updates all unread notifications.
    """
    try:
        await crud_notification.mark_all_notifications_read(db, current_user.id)
        return None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.websocket(
    "/ws",
    name="notifications_websocket"
)
async def notifications_websocket(
    websocket: WebSocket,
    token: str = Query(..., description="JWT token for authentication"),
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint for real-time notifications.
    
    Features:
    * Real-time updates
    * JWT authentication
    * Automatic reconnection support
    * Efficient message delivery
    
    Connection URL format:
    ws://server/notifications/ws?token=<jwt_token>
    
    Message format:
    {
        "type": "notification",
        "data": {
            "id": 1,
            "type": "EVENT_UPDATE",
            "title": "Event Updated",
            "message": "Details changed for 'Team Meeting'",
            "event_id": 123,
            "created_at": "2024-03-19T15:00:00Z"
        }
    }
    """
    try:
        # Authenticate user
        user = await get_current_user_ws(websocket, token, db)
        
        # Connect WebSocket
        await ws_manager.connect(websocket, user.id)
        
        try:
            while True:
                # Wait for messages (client pings/status updates)
                data = await websocket.receive_json()
                
                # Handle client messages if needed
                # For now, we just acknowledge receipt
                await websocket.send_json({
                    "type": "ack",
                    "data": {"received": True}
                })
                
        except WebSocketDisconnect:
            await ws_manager.disconnect(websocket, user.id)
            
    except WebSocketDisconnect:
        # Already handled
        pass
    except Exception:
        await websocket.close(code=4000)  # Other error

@router.post(
    "",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create notification",
    description="""
    Create a new notification.
    
    Features:
    * Automatic user assignment
    * WebSocket broadcast
    * Event linking
    * Notification metadata
    """,
    responses={
        201: {
            "description": "Notification created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "type": "EVENT_SHARE",
                        "title": "Event Shared",
                        "message": "John Doe shared 'Team Meeting' with you",
                        "event_id": 123,
                        "is_read": False,
                        "created_at": "2024-03-19T15:00:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid input",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid notification data"}
                }
            }
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not enough permissions"},
        500: {"description": "Internal server error"}
    }
)
async def create_new_notification(
    *,
    db: AsyncSession = Depends(get_db),
    notification: NotificationCreate,
    current_user: User = Depends(get_current_user)
) -> NotificationResponse:
    """
    Create a new notification.
    
    Parameters:
    - **notification**: Notification data to create
    
    Creates a new notification and broadcasts it via WebSocket if applicable.
    """
    try:
        return await crud_notification.create_notification(db, notification, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete notification",
    description="""
    Delete a notification.
    
    Features:
    * Permission validation
    * WebSocket update
    * Automatic cleanup
    """,
    responses={
        204: {
            "description": "Notification deleted successfully"
        },
        401: {"description": "Not authenticated"},
        403: {
            "description": "Not your notification",
            "content": {
                "application/json": {
                    "example": {"detail": "Not your notification"}
                }
            }
        },
        404: {
            "description": "Notification not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Notification not found"}
                }
            }
        },
        500: {"description": "Internal server error"}
    }
)
async def remove_notification(
    *,
    db: AsyncSession = Depends(get_db),
    notification_id: int,
    current_user: User = Depends(get_current_user)
) -> None:
    """
    Delete a notification.
    
    Parameters:
    - **notification_id**: ID of the notification to delete
    
    The notification must belong to the current user.
    """
    notification = await crud_notification.get_notification(db, notification_id, current_user.id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    result = await crud_notification.delete_notification(db, notification_id, current_user.id)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to delete notification")
    return None 