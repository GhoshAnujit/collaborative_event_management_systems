from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp
from app.core.config import settings

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to responses."""
    
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.security_headers = {
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": f"max-age={settings.HSTS_MAX_AGE}; includeSubDomains",
            "Content-Security-Policy": f"report-uri {settings.CSP_REPORT_URI}" if settings.CSP_REPORT_URI else None,
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        for header_name, header_value in self.security_headers.items():
            if header_value:
                response.headers[header_name] = header_value
        return response

class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Validate incoming requests."""
    
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.blocked_paths = settings.BLOCKED_PATHS
        self.blocked_ips = settings.BLOCKED_IPS
        self.validation_exempt_paths = settings.VALIDATION_EXEMPT_PATHS
        self.max_content_length = settings.MAX_CONTENT_LENGTH
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Check blocked paths
        if any(request.url.path.startswith(path) for path in self.blocked_paths):
            return Response(status_code=403, content="Access denied")
        
        # Check blocked IPs
        client_ip = request.client.host if request.client else None
        if client_ip and client_ip in self.blocked_ips:
            return Response(status_code=403, content="IP blocked")
        
        # Check content length
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_content_length:
            return Response(status_code=413, content="Request too large")
        
        return await call_next(request)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit requests."""
    
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.auth_rate_limit = settings.AUTH_RATE_LIMIT
        self.api_rate_limit = settings.API_RATE_LIMIT
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Implement rate limiting logic here
        # For now, just pass through
        return await call_next(request) 