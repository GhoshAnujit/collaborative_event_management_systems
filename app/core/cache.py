from typing import Any, Optional, Dict, Callable
from datetime import datetime, timedelta
import time
import asyncio
from functools import wraps

class Cache:
    """Simple in-memory cache implementation"""
    def __init__(self, default_ttl: int = 300):  # 5 minutes default TTL
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._default_ttl = default_ttl
        self._cleanup_task: Optional[asyncio.Task] = None

    async def _cleanup_expired(self):
        """Periodically cleanup expired cache entries"""
        while True:
            try:
                current_time = time.time()
                for key in list(self._cache.keys()):
                    if self._cache[key]["expires_at"] <= current_time:
                        del self._cache[key]
                await asyncio.sleep(60)  # Run cleanup every minute
            except Exception:
                await asyncio.sleep(60)

    def start_cleanup(self):
        """Start the cleanup task"""
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_expired())

    def stop_cleanup(self):
        """Stop the cleanup task"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache"""
        if key in self._cache:
            cache_data = self._cache[key]
            if cache_data["expires_at"] > time.time():
                return cache_data["value"]
            del self._cache[key]
        return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in cache with TTL"""
        expires_at = time.time() + (ttl or self._default_ttl)
        self._cache[key] = {
            "value": value,
            "expires_at": expires_at
        }

    async def delete(self, key: str) -> None:
        """Delete a value from cache"""
        if key in self._cache:
            del self._cache[key]

    async def clear(self) -> None:
        """Clear all cache entries"""
        self._cache.clear()

# Global cache instance
cache = Cache()

def cached(ttl: Optional[int] = None):
    """Decorator for caching function results"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cached_value = await cache.get(key)
            if cached_value is not None:
                return cached_value
            
            # If not in cache, execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(key, result, ttl)
            return result
        return wrapper
    return decorator 