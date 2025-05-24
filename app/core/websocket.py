from typing import Dict, Set, Optional, List, Any
from fastapi import WebSocket, WebSocketDisconnect
from app.core.logging import websocket_logger
from app.core.metrics import record_ws_event
import json
from app.schemas.notification import WebSocketMessage

class WebSocketManager:
    def __init__(self):
        # Store active connections: user_id -> Set[WebSocket]
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, user_id: int):
        """Connect a new WebSocket for a user."""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        
        # Log and record metrics
        websocket_logger.info(
            "WebSocket connected",
            extra={
                "user_id": user_id,
                "endpoint": str(websocket.url)
            }
        )
        record_ws_event(str(websocket.url), "connect")
        
    async def disconnect(self, websocket: WebSocket, user_id: int):
        """Disconnect a WebSocket for a user."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        # Log and record metrics
        websocket_logger.info(
            "WebSocket disconnected",
            extra={
                "user_id": user_id,
                "endpoint": str(websocket.url)
            }
        )
        record_ws_event(str(websocket.url), "disconnect")
    
    async def broadcast_to_user(self, user_id: int, message: WebSocketMessage):
        """Send a message to all connections of a specific user."""
        if user_id not in self.active_connections:
            return
            
        # Convert message to dict for JSON serialization
        message_data = message.model_dump()
        
        # Send to all user's connections
        dead_connections = set()
        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_json(message_data)
                record_ws_event(str(websocket.url), "message", "sent")
            except WebSocketDisconnect:
                dead_connections.add(websocket)
                continue
            except Exception as e:
                websocket_logger.error(
                    "Failed to send WebSocket message",
                    extra={
                        "user_id": user_id,
                        "error": str(e)
                    },
                    exc_info=True
                )
                dead_connections.add(websocket)
        
        # Clean up dead connections
        for dead_ws in dead_connections:
            await self.disconnect(dead_ws, user_id)
    
    async def broadcast_to_users(self, user_ids: Set[int], message: WebSocketMessage):
        """Send a message to multiple users."""
        for user_id in user_ids:
            await self.broadcast_to_user(user_id, message)
            
    async def broadcast(self, user_ids: List[int] | Set[int], message_type: str, data: Dict[str, Any]):
        """
        Create a WebSocketMessage and broadcast it to a list of users.
        This is a convenience method used by the event CRUD operations.
        """
        # Create a WebSocketMessage from the provided type and data
        message = WebSocketMessage(
            type=message_type,
            data=data
        )
        
        # Convert list to set if needed
        if isinstance(user_ids, list):
            user_ids = set(user_ids)
            
        # Broadcast to all specified users
        await self.broadcast_to_users(user_ids, message)

# Global WebSocket manager instance
ws_manager = WebSocketManager() 