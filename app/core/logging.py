import logging
import json
from datetime import datetime, UTC
from typing import Any, Dict
from uuid import uuid4
from pythonjsonlogger.jsonlogger import JsonFormatter
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from app.core.config import settings
import time
import traceback

class CustomJsonFormatter(JsonFormatter):
    """Custom JSON formatter for logs."""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Add custom fields to the log record."""
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp in ISO format
        log_record["timestamp"] = datetime.now(UTC).isoformat()
        log_record["level"] = record.levelname
        log_record["name"] = record.name
        
        # Add code location
        log_record["function"] = record.funcName
        log_record["module"] = record.module
        log_record["line"] = record.lineno
        
        # Add process and thread info
        log_record["process_id"] = record.process
        log_record["thread_id"] = record.thread
        
        # Add environment
        log_record["environment"] = settings.ENVIRONMENT
        
        # Add request context if available
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_record["user_id"] = record.user_id
        if hasattr(record, "duration"):
            log_record["duration"] = record.duration

def setup_logging() -> None:
    """Configure logging for the application."""
    # Create handlers
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(CustomJsonFormatter())
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)
    root_logger.addHandler(console_handler)
    
    # Configure specific loggers
    loggers = [
        "api.request",
        "api.websocket",
        "api.auth",
        "api.events",
        "api.notifications",
        "db",
        "cache",
        "httpx",
        "uvicorn"
    ]
    
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(settings.LOG_LEVEL)
        logger.propagate = False
        logger.addHandler(console_handler)

def setup_test_logging() -> None:
    """Configure logging for tests with propagation enabled."""
    # Create handlers
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(CustomJsonFormatter())
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    
    # Configure specific loggers with propagation enabled for tests
    loggers = [
        "api.request",
        "api.websocket",
        "api.auth",
        "api.events",
        "api.notifications",
        "db",
        "cache",
        "httpx",
        "uvicorn"
    ]
    
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        logger.propagate = True  # Enable propagation for test capture
        logger.addHandler(console_handler)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests."""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request and log details."""
        request_id = str(uuid4())
        start_time = time.time()
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        # Log request details
        extra = {
            "request_id": request_id,
            "user_id": None,  # Will be set by auth middleware if user is authenticated
            "method": request.method,
            "path": request.url.path,
            "timestamp": datetime.now(UTC).isoformat(),
            "duration": None
        }
        
        request_logger.info("Incoming request", extra=extra)
        
        try:
            response = await call_next(request)
            
            # Update duration in extra fields
            duration = time.time() - start_time
            extra["duration"] = duration
            extra["status_code"] = response.status_code
            
            request_logger.info("Request completed", extra=extra)
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Log error with traceback
            duration = time.time() - start_time
            extra["duration"] = duration
            extra["error"] = str(e)
            extra["error_type"] = e.__class__.__name__
            extra["exc_info"] = traceback.format_exc()
            
            request_logger.error(f"{e.__class__.__name__} occurred", extra=extra)
            raise

# Create specific loggers
request_logger = logging.getLogger("api.request")
websocket_logger = logging.getLogger("api.websocket")
auth_logger = logging.getLogger("api.auth")
events_logger = logging.getLogger("api.events")
notifications_logger = logging.getLogger("api.notifications")
db_logger = logging.getLogger("db")
cache_logger = logging.getLogger("cache") 