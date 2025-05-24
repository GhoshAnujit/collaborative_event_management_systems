from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import secrets
from typing import Optional
from app.core.config import settings

class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        csp_policy: Optional[str] = None,
        hsts_max_age: int = 31536000
    ):
        super().__init__(app)
        self.csp_policy = csp_policy or self._default_csp_policy()
        self.hsts_max_age = hsts_max_age

    def _default_csp_policy(self) -> str:
        """Generate default Content Security Policy."""
        return (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https:; "
            "connect-src 'self' ws: wss:; "
            f"frame-ancestors {settings.ALLOWED_HOSTS}; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        """Add security headers to response."""
        # Generate nonce for CSP
        nonce = secrets.token_urlsafe(16)
        
        # Call next middleware/route handler
        response = await call_next(request)
        
        # Security Headers
        headers = {
            # Content Security Policy
            "Content-Security-Policy": self.csp_policy,
            
            # Prevent clickjacking
            "X-Frame-Options": "DENY",
            
            # XSS protection
            "X-XSS-Protection": "1; mode=block",
            
            # Prevent MIME type sniffing
            "X-Content-Type-Options": "nosniff",
            
            # Referrer Policy
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # Permissions Policy (formerly Feature-Policy)
            "Permissions-Policy": (
                "accelerometer=(), "
                "camera=(), "
                "geolocation=(), "
                "gyroscope=(), "
                "magnetometer=(), "
                "microphone=(), "
                "payment=(), "
                "usb=()"
            ),
            
            # HSTS (only in production)
            "Strict-Transport-Security": f"max-age={self.hsts_max_age}; includeSubDomains; preload",
            
            # Clear-Site-Data on logout (handled separately in auth endpoints)
            # "Clear-Site-Data": "\"cache\", \"cookies\", \"storage\"",
        }
        
        # Add headers to response
        for header_name, header_value in headers.items():
            response.headers[header_name] = header_value
        
        return response

def setup_security_middleware(app: FastAPI) -> None:
    """Configure security middleware for the application."""
    # Add security middleware
    app.add_middleware(
        SecurityMiddleware,
        csp_policy=None,  # Use default policy
        hsts_max_age=31536000  # 1 year
    )
    
    # Configure CORS
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_HOSTS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset"
        ],
        max_age=3600  # Cache preflight requests for 1 hour
    )
    
    # Configure trusted hosts
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    if settings.ALLOWED_HOSTS:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.ALLOWED_HOSTS
        ) 