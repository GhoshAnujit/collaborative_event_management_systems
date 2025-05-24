from typing import Any
from fastapi import Response
from fastapi.responses import JSONResponse
import msgpack
from app.core.cache import cached

class MessagePackResponse(Response):
    """Response class for MessagePack serialization"""
    media_type = "application/x-msgpack"

    def render(self, content: Any) -> bytes:
        return msgpack.packb(content)

class DynamicResponse(Response):
    """Dynamic response class that can return either JSON or MessagePack based on Accept header"""
    def __init__(self, content: Any, *args, **kwargs):
        super().__init__(content, *args, **kwargs)
        self.content = content

    async def __call__(self, scope, receive, send):
        accept = scope.get("headers", {}).get(b"accept", b"application/json").decode()
        
        if "application/x-msgpack" in accept:
            response = MessagePackResponse(self.content)
        else:
            response = JSONResponse(self.content)
        
        await response(scope, receive, send) 