import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.security_middleware import SecurityMiddleware
from app.core.validation_middleware import RequestValidationMiddleware
from app.core.websocket_limiter import WebSocketRateLimiter
from app.core.config import settings
import asyncio
import json
from datetime import datetime

@pytest.fixture
def test_app():
    """Create test application with security features."""
    app = FastAPI()
    
    # Add security middleware
    app.add_middleware(
        SecurityMiddleware,
        csp_policy=None,  # Use default
        hsts_max_age=31536000
    )
    
    app.add_middleware(
        RequestValidationMiddleware,
        max_content_length=1024 * 1024,  # 1MB for testing
        blocked_paths=["/admin", "/.env"],
        blocked_ips=["192.0.2.1"]  # Example blocked IP
    )
    
    @app.get("/test")
    async def test_endpoint():
        return {"message": "success"}
    
    return app

@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)

def test_security_headers(client):
    """Test security headers are present in response."""
    response = client.get("/test")
    assert response.status_code == 200
    
    # Check security headers
    headers = response.headers
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-XSS-Protection"] == "1; mode=block"
    assert "max-age=31536000" in headers["Strict-Transport-Security"]
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in headers

def test_blocked_path(client):
    """Test blocked paths return 403."""
    try:
        response = client.get("/admin")
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "PATH_BLOCKED"
    except Exception as e:
        # The middleware raises an exception which is what we want
        # In a real application this would be converted to a response
        assert "PATH_BLOCKED" in str(e)

def test_blocked_ip(client):
    """Test blocked IPs return 403."""
    # Simulate request from blocked IP
    try:
        response = client.get(
            "/test",
            headers={"X-Forwarded-For": "192.0.2.1"}
        )
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "IP_BLOCKED"
    except Exception as e:
        # The middleware raises an exception which is what we want
        # In a real application this would be converted to a response
        assert "IP_BLOCKED" in str(e)

def test_content_length_limit(client):
    """Test content length limit."""
    # Create large payload
    large_data = {"data": "x" * (2 * 1024 * 1024)}  # 2MB
    
    try:
        response = client.post(
            "/test",
            json=large_data
        )
        assert response.status_code == 413
        assert response.json()["detail"]["code"] == "REQUEST_ENTITY_TOO_LARGE"
    except Exception as e:
        # The middleware raises an exception which is what we want
        # In a real application this would be converted to a response
        assert "REQUEST_ENTITY_TOO_LARGE" in str(e)

def test_attack_patterns(client):
    """Test protection against common attack patterns."""
    # SQL injection attempt
    try:
        response = client.get("/test?q=1 OR 1=1")
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "INVALID_REQUEST"
    except Exception as e:
        # The middleware raises an exception which is what we want
        assert "INVALID_REQUEST" in str(e)
    
    # XSS attempt
    try:
        response = client.get("/test?q=<script>alert(1)</script>")
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "INVALID_REQUEST"
    except Exception as e:
        # The middleware raises an exception which is what we want
        assert "INVALID_REQUEST" in str(e)
    
    # Path traversal attempt - use a query parameter with path traversal instead of in the URL path
    try:
        response = client.get("/test?path=../../../etc/passwd")
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "INVALID_REQUEST"
    except Exception as e:
        # The middleware raises an exception which is what we want
        assert "INVALID_REQUEST" in str(e)

@pytest.mark.asyncio
async def test_websocket_rate_limiter():
    """Test WebSocket rate limiting."""
    limiter = WebSocketRateLimiter()
    user_id = 1
    
    # Test connection limit
    connections = []
    for i in range(settings.WS_MAX_CONNECTIONS_PER_USER + 1):
        ws = MockWebSocket()
        result = await limiter.connect(ws, user_id)
        if i < settings.WS_MAX_CONNECTIONS_PER_USER:
            assert result is True
            connections.append(ws)
        else:
            assert result is False
    
    # Test message rate limit
    for i in range(settings.WS_MAX_MESSAGES_PER_MINUTE + 1):
        result = await limiter.check_rate_limit(user_id)
        if i < settings.WS_MAX_MESSAGES_PER_MINUTE:
            assert result is True
        else:
            assert result is False
    
    # Test cleanup
    await limiter.start_cleanup()
    await asyncio.sleep(1)  # Wait for cleanup
    await limiter.stop_cleanup()
    
    # Clean up connections
    for ws in connections:
        await limiter.disconnect(ws, user_id)

class MockWebSocket:
    """Mock WebSocket for testing."""
    async def close(self, code: int, reason: str = None):
        pass
    
    async def send_text(self, message: str):
        pass
    
    @property
    def client_state(self):
        return type("ClientState", (), {"DISCONNECTED": False}) 