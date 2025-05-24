from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Optional, Tuple
import time
import asyncio
from redis.asyncio import Redis
from app.core.config import settings
from app.core.metrics import record_rate_limit_hit

class RateLimiter:
    """Rate limiter using Redis."""
    
    def __init__(self, redis: Redis):
        self.redis = redis
        self.default_rate = settings.API_RATE_LIMIT
        self.auth_rate = settings.AUTH_RATE_LIMIT
        self.window = 60  # 1 minute window
    
    async def _get_key(self, identifier: str, endpoint: str) -> str:
        """Generate Redis key for rate limiting."""
        return f"rate_limit:{endpoint}:{identifier}"
    
    async def is_rate_limited(
        self,
        identifier: str,
        endpoint: str,
        limit: Optional[int] = None
    ) -> Tuple[bool, Dict[str, int]]:
        """Check if request should be rate limited."""
        key = await self._get_key(identifier, endpoint)
        now = int(time.time())
        window_start = now - self.window
        
        async with self.redis.pipeline(transaction=True) as pipe:
            try:
                # Clean old records
                await pipe.zremrangebyscore(key, 0, window_start)
                # Count requests in current window
                await pipe.zcard(key)
                # Add current request
                await pipe.zadd(key, {str(now): now})
                # Set expiry
                await pipe.expire(key, self.window)
                # Execute pipeline
                _, current_requests, _, _ = await pipe.execute()
                
                rate_limit = limit or self.default_rate
                is_limited = current_requests >= rate_limit
                
                remaining = max(0, rate_limit - current_requests)
                reset_time = now + self.window
                
                return is_limited, {
                    "limit": rate_limit,
                    "remaining": remaining,
                    "reset": reset_time
                }
                
            except Exception as e:
                # If Redis fails, allow request but log error
                return False, {
                    "limit": rate_limit,
                    "remaining": -1,
                    "reset": now + self.window
                }

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests."""
    
    def __init__(self, app, limiter: RateLimiter):
        super().__init__(app)
        self.limiter = limiter
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for testing or exempt paths
        if settings.TESTING or request.url.path in settings.VALIDATION_EXEMPT_PATHS:
            return await call_next(request)
        
        # Get client identifier (IP address or user ID if authenticated)
        identifier = request.client.host
        if hasattr(request.state, "user"):
            identifier = f"user:{request.state.user.id}"
        
        # Determine rate limit based on endpoint
        endpoint = request.url.path
        limit = self.limiter.auth_rate if "/auth/" in endpoint else None
        
        # Check rate limit
        is_limited, rate_info = await self.limiter.is_rate_limited(
            identifier,
            endpoint,
            limit
        )
        
        if is_limited:
            # Record metric
            record_rate_limit_hit(endpoint)
            
            # Return rate limit error
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests",
                    "reset": rate_info["reset"]
                }
            )
        
        # Add rate limit headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rate_info["reset"])
        
        return response

def setup_rate_limiter(app, redis: Redis):
    """Configure rate limiting middleware."""
    limiter = RateLimiter(redis)
    app.add_middleware(RateLimitMiddleware, limiter=limiter) 