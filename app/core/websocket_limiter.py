from datetime import datetime, timedelta
from typing import Dict, Set
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from app.core.config import settings

class WebSocketRateLimiter:
    def __init__(self):
        self.connections: Dict[int, Set[WebSocket]] = {}  # user_id -> connections
        self.message_counts: Dict[int, Dict[datetime, int]] = {}  # user_id -> {timestamp -> count}
        self.max_connections_per_user = 5
        self.max_messages_per_minute = 60
        self._cleanup_task = None

    async def start_cleanup(self):
        """Start the cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup(self):
        """Stop the cleanup task."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    async def _cleanup_loop(self):
        """Periodically clean up old message counts."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self._cleanup_old_counts()
            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but continue running
                continue

    async def _cleanup_old_counts(self):
        """Remove message counts older than 1 minute."""
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)
        
        for user_id in list(self.message_counts.keys()):
            counts = self.message_counts[user_id]
            # Remove old timestamps
            self.message_counts[user_id] = {
                ts: count for ts, count in counts.items()
                if ts > cutoff
            }
            # Remove user if no recent messages
            if not self.message_counts[user_id]:
                del self.message_counts[user_id]

    async def connect(self, websocket: WebSocket, user_id: int):
        """Handle new WebSocket connection."""
        # Check if user has too many connections
        if user_id not in self.connections:
            self.connections[user_id] = set()
        
        if len(self.connections[user_id]) >= self.max_connections_per_user:
            await websocket.close(code=1008, reason="Too many connections")
            return False
        
        # Add connection
        self.connections[user_id].add(websocket)
        return True

    async def disconnect(self, websocket: WebSocket, user_id: int):
        """Handle WebSocket disconnection."""
        if user_id in self.connections:
            self.connections[user_id].discard(websocket)
            if not self.connections[user_id]:
                del self.connections[user_id]

    async def check_rate_limit(self, user_id: int) -> bool:
        """Check if user has exceeded message rate limit."""
        now = datetime.utcnow()
        if user_id not in self.message_counts:
            self.message_counts[user_id] = {}
        
        # Count messages in the last minute
        cutoff = now - timedelta(minutes=1)
        recent_count = sum(
            count for ts, count in self.message_counts[user_id].items()
            if ts > cutoff
        )
        
        if recent_count >= self.max_messages_per_minute:
            return False
        
        # Update message count
        self.message_counts[user_id][now] = self.message_counts[user_id].get(now, 0) + 1
        return True

    async def broadcast_to_user(self, user_id: int, message: str):
        """Send message to all connections of a user."""
        if user_id not in self.connections:
            return
        
        dead_connections = set()
        for websocket in self.connections[user_id]:
            try:
                await websocket.send_text(message)
            except WebSocketDisconnect:
                dead_connections.add(websocket)
            except Exception:
                dead_connections.add(websocket)
        
        # Clean up dead connections
        for websocket in dead_connections:
            await self.disconnect(websocket, user_id)

# Global instance
ws_limiter = WebSocketRateLimiter() 