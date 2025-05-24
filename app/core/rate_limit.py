from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
import time
from typing import Optional, Dict, Tuple
import asyncio
from datetime import datetime

class RateLimiter:
    """In-memory rate limiter implementation"""
    def __init__(self):
        self.requests: Dict[Tuple[str, str], list] = {}  # (ip, path) -> [timestamps]
        self._cleanup_task: Optional[asyncio.Task] = None

    async def _cleanup_old_requests(self):
        """Periodically cleanup old request records"""
        while True:
            try:
                current_time = time.time()
                for key in list(self.requests.keys()):
                    # Remove timestamps older than 1 minute
                    self.requests[key] = [
                        ts for ts in self.requests[key]
                        if current_time - ts < 60
                    ]
                    # Remove empty lists
                    if not self.requests[key]:
                        del self.requests[key]
                await asyncio.sleep(60)  # Run cleanup every minute
            except Exception:
                await asyncio.sleep(60)  # Continue even if there's an error

    def start_cleanup(self):
        """Start the cleanup task"""
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_old_requests())

    def stop_cleanup(self):
        """Stop the cleanup task"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None

    async def is_rate_limited(
        self,
        request: Request,
        limit: int = 100,  # requests per minute
        auth_limit: int = 5  # auth requests per minute
    ) -> bool:
        """Check if a request should be rate limited"""
        client_ip = request.client.host
        path = request.url.path
        current_time = time.time()
        key = (client_ip, path)

        # Use stricter limit for auth endpoints
        current_limit = auth_limit if path.startswith("/api/auth/") else limit

        # Initialize or update request timestamps
        if key not in self.requests:
            self.requests[key] = []
        self.requests[key].append(current_time)

        # Count requests in the last minute
        minute_ago = current_time - 60
        recent_requests = [ts for ts in self.requests[key] if ts > minute_ago]
        self.requests[key] = recent_requests

        return len(recent_requests) > current_limit

# Global rate limiter instance
limiter = RateLimiter()

async def rate_limit_dependency(request: Request):
    """FastAPI dependency for rate limiting"""
    is_limited = await limiter.is_rate_limited(request)
    if is_limited:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Too many requests",
                "message": "Rate limit exceeded. Please try again later.",
                "retry_after": "60 seconds"
            }
        )
    return True 