from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, field_validator
import secrets
import os
from pathlib import Path

# Ensure the SQLite database directory exists
sqlite_db_path = Path("./sqlite_db")
sqlite_db_path.mkdir(exist_ok=True)

class Settings(BaseSettings):
    # Project Info
    PROJECT_NAME: str = "Collaborative Event Management System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    
    # Server settings
    PORT: int = int(os.environ.get("PORT", 8000))
    
    # Security
    SECRET_KEY: str = os.environ.get("SECRET_KEY", secrets.token_urlsafe(32))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", secrets.token_urlsafe(32))
    JWT_ALGORITHM: str = "HS256"
    
    # Testing
    TESTING: bool = False
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    ALLOWED_HOSTS: List[str] = ["*"]
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # Rate Limiting
    AUTH_RATE_LIMIT: int = 5  # requests per minute
    API_RATE_LIMIT: int = 100  # requests per minute
    WS_MAX_CONNECTIONS_PER_USER: int = 5
    WS_MAX_MESSAGES_PER_MINUTE: int = 60
    
    # Redis
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    REDIS_MAX_CONNECTIONS: int = 10
    REDIS_TIMEOUT: int = 5  # seconds
    
    # Security Headers
    SECURITY_HEADERS: bool = True
    HSTS_MAX_AGE: int = 31536000  # 1 year
    CSP_REPORT_URI: str = ""
    
    # Request Validation
    MAX_CONTENT_LENGTH: int = 10 * 1024 * 1024  # 10MB
    BLOCKED_PATHS: List[str] = [
        "/admin",
        "/.env",
        "/.git",
        "/wp-admin",
        "/wp-login",
        "/phpmyadmin"
    ]
    BLOCKED_IPS: List[str] = []
    VALIDATION_EXEMPT_PATHS: List[str] = [
        "/health",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json"
    ]
    
    # Database
    DATABASE_URL: str = os.environ.get("DATABASE_URL", f"sqlite+aiosqlite:///./sqlite_db/app.db")
    SQL_ECHO: bool = False
    
    # Documentation
    SHOW_DOCS: bool = True
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Cache
    CACHE_TTL_MINUTES: int = 5
    CACHE_MAX_SIZE: int = 10000
    
    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", env_file_encoding="utf-8")

# Global instance
settings = Settings() 

# Security constants
SECURE_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": f"max-age={settings.HSTS_MAX_AGE}; includeSubDomains; preload",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
}

# Content Security Policy
CSP_POLICY = {
    "default-src": ["'self'"],
    "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:", "https:"],
    "font-src": ["'self'", "data:", "https:"],
    "connect-src": ["'self'", "ws:", "wss:"],
    "frame-ancestors": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"]
}

# Permissions Policy
PERMISSIONS_POLICY = {
    "accelerometer": [],
    "camera": [],
    "geolocation": [],
    "gyroscope": [],
    "magnetometer": [],
    "microphone": [],
    "payment": [],
    "usb": []
} 