from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
import logging
import sys
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.api.v1.api import api_router
from app.core.rate_limit import rate_limit_dependency, limiter
from app.core.cache import cache
from app.core.exceptions import CustomException
from app.core.middleware import (
    SecurityHeadersMiddleware,
    RequestValidationMiddleware,
    RateLimitMiddleware
)

# ─── Logging Configuration ───────────────────────────────────────────

def setup_logging():
    log_format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    formatter = logging.Formatter(log_format)

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL.upper())

    # Remove default handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    if settings.ENVIRONMENT.lower() == "development":
        handler = logging.StreamHandler(sys.stdout)
    else:
        handler = RotatingFileHandler(
            filename=settings.LOG_FILE_PATH if hasattr(settings, "LOG_FILE_PATH") else "app.log",
            maxBytes=10_000_000,
            backupCount=3
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

setup_logging()
logger = logging.getLogger(__name__)

class WelcomeResponse(BaseModel):
    message: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handle startup and shutdown events.
    """
    # Startup
    print("Starting up...")
    logger.info("Starting up application...")
    limiter.start_cleanup()
    cache.start_cleanup()
    
    yield
    
    # Shutdown
    print("Shutting down...")
    logger.info("Shutting down application...")
    limiter.stop_cleanup()
    cache.stop_cleanup()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
    NeoFi Event Manager API - A comprehensive event management system.
    
    ## Features
    
    * 👤 **Authentication**
        * JWT-based authentication
        * Token refresh mechanism
        * Secure password handling
    
    * 📅 **Event Management**
        * Create, read, update, delete events
        * Recurring event support (RFC 5545)
        * Conflict detection
        * Version history and rollback
    
    * 🔔 **Real-time Notifications**
        * WebSocket-based updates
        * Read/unread status
        * Bulk operations
    
    * 👥 **Permission Management**
        * Role-based access control
        * Granular permissions
        * Event sharing
    
    ## Authentication
    
    Most endpoints require authentication using JWT tokens. To authenticate:
    1. Get a token pair using the `/auth/login` endpoint
    2. Include the access token in the `Authorization` header:
       `Authorization: Bearer <token>`
    3. Use the refresh token to get new access tokens
    
    ## Rate Limiting
    
    The API implements rate limiting to ensure fair usage:
    * Authentication endpoints: 5 requests per minute
    * Regular endpoints: 100 requests per minute
    * WebSocket connections: 1 connection per user
    
    ## Response Formats
    
    The API supports both JSON and MessagePack response formats:
    * Default: JSON (application/json)
    * MessagePack: Set Accept header to 'application/x-msgpack'
    
    ## Caching
    
    The API implements caching for frequently accessed data:
    * Event listings: 5 minutes TTL
    * User profiles: 15 minutes TTL
    * Public data: 30 minutes TTL
    
    ## Error Handling
    
    The API uses standard HTTP status codes and returns detailed error messages:
    * 400: Bad Request - Invalid input
    * 401: Unauthorized - Missing or invalid token
    * 403: Forbidden - Insufficient permissions
    * 404: Not Found - Resource doesn't exist
    * 429: Too Many Requests - Rate limit exceeded
    * 500: Internal Server Error - Server-side error
    
    ## Support
    
    For issues or questions, please contact the NeoFi team or visit our documentation.
    """,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs" if settings.SHOW_DOCS else None,
    redoc_url=f"{settings.API_V1_STR}/redoc" if settings.SHOW_DOCS else None,
    contact={
        "name": "NeoFi Team",
        "url": "https://github.com/neofi/neofi_backend",
        "email": "support@neofi.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    terms_of_service="https://neofi.com/terms/",
    dependencies=[Depends(rate_limit_dependency)],  # Apply rate limiting to all routes
    lifespan=lifespan
)

# Add CORS middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Add security headers middleware
if settings.SECURITY_HEADERS:
    app.add_middleware(SecurityHeadersMiddleware)

# Add request validation middleware
app.add_middleware(RequestValidationMiddleware)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Custom exception handler
@app.exception_handler(CustomException)
async def custom_exception_handler(request: Request, exc: CustomException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

# Validation exception handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=app.description,  # Use the app's description
        routes=app.routes,
    )
    
    # Add custom components, security schemes, etc.
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    
    # Add security requirement to all routes
    openapi_schema["security"] = [{"bearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.get(
    "/",
    response_model=WelcomeResponse,
    status_code=status.HTTP_200_OK,
    summary="Root endpoint",
    description="Welcome endpoint for the API",
    responses={
        200: {
            "description": "Welcome message",
            "content": {
                "application/json": {
                    "example": {"message": "Welcome to NeoFi Event Manager API"}
                }
            }
        }
    }
)
async def root() -> WelcomeResponse:
    """Root endpoint returning a welcome message."""
    return WelcomeResponse(message="Welcome to NeoFi Event Manager API")
