import pytest
import pytest_asyncio
from fastapi import FastAPI, Response
import httpx
import json
import logging
from prometheus_client.parser import text_string_to_metric_families
from app.core.logging import setup_test_logging, RequestLoggingMiddleware, CustomJsonFormatter
from app.core.metrics import (
    MetricsMiddleware, 
    record_db_operation,
    record_cache_operation,
    record_auth_attempt,
    record_ws_event,
    record_rate_limit_hit,
    setup_metrics,
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS_IN_PROGRESS,
    DB_QUERIES_TOTAL,
    CACHE_HITS_TOTAL,
    AUTH_SUCCESSES_TOTAL,
    RATE_LIMIT_HITS_TOTAL,
    ws_connections_total
)
from app.core.error_handler import setup_error_handlers
from prometheus_client import generate_latest, REGISTRY

@pytest_asyncio.fixture
async def test_app():
    """Create test application with logging and metrics."""
    app = FastAPI()
    
    # Add test endpoints first
    @app.get("/test")
    async def test_endpoint():
        return {"message": "success"}
    
    @app.get("/error")
    async def error_endpoint():
        raise ValueError("Test error")
    
    # Set up metrics first (before any error handlers or logging)
    setup_metrics(app)
    
    # Set up logging with test configuration
    setup_test_logging()
    app.add_middleware(RequestLoggingMiddleware)
    
    # Set up error handlers last
    setup_error_handlers(app)
    
    # Add metrics endpoint
    @app.get("/metrics")
    async def metrics():
        return Response(
            generate_latest(REGISTRY),
            media_type="text/plain"
        )
    
    return app

@pytest_asyncio.fixture
async def client(test_app):
    """Create test client."""
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

@pytest.mark.asyncio
async def test_request_logging(client, caplog):
    """Test request logging middleware."""
    with caplog.at_level(logging.INFO):
        response = await client.get("/test")
        assert response.status_code == 200
        
        # Check log records
        records = [r for r in caplog.records if r.name == "api.request"]
        assert len(records) >= 1  # At least one record should exist
        
        # Check record fields
        record = records[0]
        assert hasattr(record, "request_id")
        assert "timestamp" in record.__dict__
        
        # Get the formatted output to check method
        formatter = CustomJsonFormatter("%(timestamp)s %(level)s %(name)s %(message)s")
        formatted_output = formatter.format(record)
        parsed_output = json.loads(formatted_output)
        
        # Check method in the extra fields
        assert "method" in parsed_output, "Method field missing in log output"
        assert parsed_output["method"] == "GET"
        
        # Check request ID propagation
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] == record.request_id

@pytest.mark.asyncio
async def test_error_logging(client, caplog):
    """Test error logging."""
    with caplog.at_level(logging.ERROR):
        response = await client.get("/error")
        assert response.status_code == 500
        
        # Check error log
        error_records = [r for r in caplog.records if r.levelname == "ERROR"]
        assert len(error_records) >= 1
        
        error_record = error_records[0]
        assert "error" in error_record.__dict__
        assert "ValueError" in str(error_record.__dict__.get("error_type", ""))

@pytest.mark.asyncio
async def test_metrics_collection(client):
    """Test metrics collection and exposure."""
    # Make some requests to generate metrics
    await client.get("/test")
    await client.get("/test")
    await client.get("/error")
    
    # Record some additional metrics
    record_db_operation("SELECT", 0.1)
    record_cache_operation("get", hit=True)
    record_auth_attempt(True, "login")
    record_ws_event("/ws", "connect")
    record_rate_limit_hit("/api/auth/login")
    
    # Get metrics
    response = await client.get("/metrics")
    assert response.status_code == 200
    
    # Parse metrics
    metrics = {
        metric.name: metric
        for metric in text_string_to_metric_families(response.text)
    }
    
    # Check required metrics exist
    required_metrics = {
        "http_requests_total",
        "http_request_duration_seconds",
        "http_requests_in_progress",
        "db_queries_total",
        "cache_hits_total",
        "auth_successes_total",
        "ws_connections_total",
        "rate_limit_hits_total"
    }
    
    for metric_name in required_metrics:
        assert metric_name in metrics, f"Missing metric: {metric_name}"
    
    # Check specific metric values
    assert metrics["http_requests_total"].samples[0].value > 0
    assert metrics["db_queries_total"].samples[0].value == 1
    assert metrics["cache_hits_total"].samples[0].value == 1
    assert metrics["auth_successes_total"].samples[0].value == 1
    assert metrics["ws_connections_total"].samples[0].value == 1
    assert metrics["rate_limit_hits_total"].samples[0].value == 1

@pytest.mark.asyncio
async def test_structured_log_format(client, caplog):
    """Test structured JSON log format."""
    with caplog.at_level(logging.INFO):
        await client.get("/test")
        
        # Get the log records from our custom logger
        records = [r for r in caplog.records if r.name == "api.request"]
        assert records, "No api.request log records found"
        record = records[-1]
        
        # Get the formatted output
        formatter = CustomJsonFormatter("%(timestamp)s %(level)s %(name)s %(message)s")
        formatted_output = formatter.format(record)
        parsed_output = json.loads(formatted_output)
        
        # Check required fields
        required_fields = {
            "timestamp",
            "level",
            "name",
            "message",
            "request_id",
            "environment"
        }
        
        for field in required_fields:
            assert field in parsed_output, f"Missing field: {field}"
        
        # Verify field values
        assert parsed_output["level"] == "INFO"
        assert parsed_output["name"] == "api.request"
        assert isinstance(parsed_output.get("duration"), (int, float)) 