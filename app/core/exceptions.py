from fastapi import HTTPException, status
from typing import Any

class PermissionDenied(HTTPException):
    """Exception raised when a user does not have permission to perform an action."""
    def __init__(self, detail: str = "Permission denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )

class ResourceNotFound(HTTPException):
    """Exception raised when a requested resource is not found."""
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )

class ValidationError(HTTPException):
    """Exception raised when input validation fails."""
    def __init__(self, detail: str = "Validation error"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )

class AuthenticationError(HTTPException):
    """Exception raised when authentication fails."""
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail
        )

class CustomException(Exception):
    """Base class for custom exceptions."""
    def __init__(
        self,
        detail: str | dict[str, Any] = "An error occurred",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    ) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail) 