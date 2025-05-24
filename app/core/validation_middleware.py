from fastapi import FastAPI, Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import re
from typing import List, Dict, Any, Optional, Callable
from app.core.config import settings
from urllib.parse import unquote

class RequestValidationMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        max_content_length: int = 10 * 1024 * 1024,  # 10MB
        blocked_paths: Optional[List[str]] = None,
        blocked_ips: Optional[List[str]] = None
    ):
        super().__init__(app)
        self.max_content_length = max_content_length
        self.blocked_paths = blocked_paths or []
        self.blocked_ips = blocked_ips or []
        
        # Common attack patterns
        self.sql_injection_pattern = re.compile(
            r"(?i)((\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bDROP\b|\bUNION\b|\bALTER\b|\bEXEC\b|\bOR\s+1\s*=\s*1\b|\bOR\s+'[^']+'='[^']+'\b|--\s+))"
        )
        self.xss_pattern = re.compile(
            r"(?i)(<script|javascript:|data:text/html|vbscript:|onload=|onerror=|<img[^>]*src=.*onerror=|<iframe)"
        )
        self.path_traversal_pattern = re.compile(r"\.{2}[/\\]")
        self.command_injection_pattern = re.compile(
            r"(?i)([;&|`]|\$\(|\|\||&&)"
        )

    def _check_content_length(self, request: Request) -> None:
        """Check if request content length is within limits."""
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_content_length:
            raise HTTPException(
                status_code=413,
                detail={
                    "code": "REQUEST_ENTITY_TOO_LARGE",
                    "message": "Request body too large"
                }
            )

    def _check_blocked_path(self, request: Request) -> None:
        """Check if request path is blocked."""
        path = request.url.path
        if any(blocked in path for blocked in self.blocked_paths):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "PATH_BLOCKED",
                    "message": "Access to this path is blocked"
                }
            )

    def _check_blocked_ip(self, request: Request) -> None:
        """Check if request IP is blocked."""
        client_ip = request.client.host if request.client else None
        
        # Check X-Forwarded-For header for proxy situations
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # The first IP in the list is the original client
            proxied_ip = forwarded_for.split(",")[0].strip()
            if proxied_ip in self.blocked_ips:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "IP_BLOCKED",
                        "message": "Access from this IP is blocked"
                    }
                )
        
        if client_ip and client_ip in self.blocked_ips:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "IP_BLOCKED",
                    "message": "Access from this IP is blocked"
                }
            )

    def _check_attack_patterns(self, request: Request) -> None:
        """Check request for common attack patterns."""
        # Get request data
        path = request.url.path
        
        # Get raw query string and URL-decode it
        raw_query = str(request.url.query)
        decoded_query = unquote(raw_query)
        
        # Get query parameters as a string
        query_string = str(request.query_params)
        
        # Get headers without standard ones to reduce false positives
        sensitive_headers = ["cookie", "authorization"]
        filtered_headers = {
            k.lower(): v for k, v in request.headers.items() 
            if k.lower() in sensitive_headers
        }
        
        # Combine data for checking
        data_to_check = [
            path,
            query_string,
            decoded_query,  # Check the raw decoded query string
            str(filtered_headers)
        ]
        
        # Check patterns
        for data in data_to_check:
            if self.sql_injection_pattern.search(data):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "INVALID_REQUEST",
                        "message": "Potential SQL injection detected"
                    }
                )
            
            if self.xss_pattern.search(data):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "INVALID_REQUEST",
                        "message": "Potential XSS attack detected"
                    }
                )
            
            if self.path_traversal_pattern.search(data):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "INVALID_REQUEST",
                        "message": "Path traversal attempt detected"
                    }
                )
            
            if self.command_injection_pattern.search(data):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "INVALID_REQUEST",
                        "message": "Command injection attempt detected"
                    }
                )

    def _add_security_headers(self, response: Response) -> Response:
        """Add security headers to response."""
        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'"
        )
        
        # Other security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Validate request and dispatch to endpoint."""
        # Skip validation for certain paths (e.g., health checks)
        if request.url.path in settings.VALIDATION_EXEMPT_PATHS:
            return await call_next(request)
            
        try:
            # Check path
            self._check_blocked_path(request)
            
            # Check for path traversal in the URL path
            raw_path = request.url.path
            if ".." in raw_path:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "INVALID_REQUEST",
                        "message": "Path traversal attempt detected"
                    }
                )
            
            # Check client IP
            self._check_blocked_ip(request)
            
            # Check content length
            self._check_content_length(request)
            
            # Check for common attack patterns
            self._check_attack_patterns(request)
            
            # Continue with request
            response = await call_next(request)
            
            # Add security headers
            return self._add_security_headers(response)
        except Exception as e:
            # Re-raise the exception
            raise e

def setup_validation_middleware(
    app: FastAPI,
    max_content_length: int = 10 * 1024 * 1024,  # 10MB
    blocked_paths: Optional[List[str]] = None,
    blocked_ips: Optional[List[str]] = None
) -> None:
    """Configure request validation middleware."""
    app.add_middleware(
        RequestValidationMiddleware,
        max_content_length=max_content_length,
        blocked_paths=blocked_paths,
        blocked_ips=blocked_ips
    ) 