from prometheus_client import Counter, Histogram, Gauge, Info, REGISTRY
from prometheus_client.openmetrics.exposition import generate_latest
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Optional
import time
from app.core.config import settings

# System Info
system_info = Info("app_info", "Application information")
system_info.info({
    "version": settings.VERSION,
    "environment": settings.ENVIRONMENT
})

# Define metrics with proper labels
HTTP_REQUESTS_TOTAL = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'path', 'status']
)

HTTP_REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'path']
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests in progress',
    ['method', 'path']
)

# WebSocket Metrics
ws_connections_total = Counter(
    "ws_connections_total",
    "Total number of WebSocket connections",
    ["endpoint"]
)

ws_connections_active = Gauge(
    "ws_connections_active",
    "Number of active WebSocket connections",
    ["endpoint"]
)

ws_messages_total = Counter(
    "ws_messages_total",
    "Total number of WebSocket messages",
    ["endpoint", "direction"]  # direction: sent/received
)

# Database Metrics
DB_QUERIES_TOTAL = Counter(
    'db_queries_total',
    'Total database queries',
    ['operation']
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5]
)

db_connections_active = Gauge(
    "db_connections_active",
    "Number of active database connections"
)

# Cache Metrics
cache_operations_total = Counter(
    "cache_operations_total",
    "Total number of cache operations",
    ["operation"]  # get, set, delete
)

CACHE_HITS_TOTAL = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['operation', 'hit']
)

cache_misses_total = Counter(
    "cache_misses_total",
    "Total number of cache misses"
)

# Authentication Metrics
AUTH_SUCCESSES_TOTAL = Counter(
    'auth_successes_total',
    'Total successful authentications',
    ['method', 'success']
)

auth_failures_total = Counter(
    "auth_failures_total",
    "Total number of failed authentications",
    ["method", "reason"]
)

# Rate Limiting Metrics
RATE_LIMIT_HITS_TOTAL = Counter(
    'rate_limit_hits_total',
    'Total rate limit hits',
    ['path']
)

class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting request metrics."""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request and collect metrics."""
        start_time = time.time()
        
        # Track in-progress requests
        HTTP_REQUESTS_IN_PROGRESS.labels(
            method=request.method,
            path=request.url.path
        ).inc()
        
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            
            # Record request duration
            duration = time.time() - start_time
            HTTP_REQUEST_DURATION.labels(
                method=request.method,
                path=request.url.path
            ).observe(duration)
            
            # Record request count
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                path=request.url.path,
                status=status_code
            ).inc()
            
            return response
        except Exception as e:
            # Record error metrics
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                path=request.url.path,
                status="500"
            ).inc()
            raise e
        finally:
            # Always decrement in-progress requests
            HTTP_REQUESTS_IN_PROGRESS.labels(
                method=request.method,
                path=request.url.path
            ).dec()

async def metrics_endpoint():
    """Endpoint for exposing Prometheus metrics."""
    return Response(
        generate_latest(),
        media_type="text/plain"
    )

# Helper functions for recording metrics
def record_db_operation(operation: str, duration: float) -> None:
    """Record database operation metrics."""
    DB_QUERIES_TOTAL.labels(operation=operation).inc()
    db_query_duration_seconds.labels(operation=operation).observe(duration)

def record_cache_operation(operation: str, hit: bool) -> None:
    """Record cache operation metrics."""
    cache_operations_total.labels(operation=operation).inc()
    CACHE_HITS_TOTAL.labels(operation=operation, hit=str(hit)).inc()

def record_auth_attempt(success: bool, method: str) -> None:
    """Record authentication attempt metrics."""
    AUTH_SUCCESSES_TOTAL.labels(method=method, success=str(success)).inc()

def record_ws_event(path: str, event: str) -> None:
    """Record WebSocket event metrics."""
    if event == "connect":
        ws_connections_total.labels(endpoint=path).inc()
        ws_connections_active.labels(endpoint=path).inc()
    elif event == "disconnect":
        ws_connections_active.labels(endpoint=path).dec()
    elif event == "message":
        ws_messages_total.labels(endpoint=path, direction="sent").inc()

def record_rate_limit_hit(path: str) -> None:
    """Record rate limit hit metrics."""
    RATE_LIMIT_HITS_TOTAL.labels(path=path).inc()

def setup_metrics(app) -> None:
    """Configure metrics collection for the application."""
    from fastapi import Response
    from prometheus_client.openmetrics.exposition import generate_latest
    
    # Add metrics middleware
    app.add_middleware(MetricsMiddleware)
    
    # Add metrics endpoint
    @app.get("/metrics")
    async def metrics():
        return Response(
            generate_latest(REGISTRY),
            media_type="text/plain"
        ) 