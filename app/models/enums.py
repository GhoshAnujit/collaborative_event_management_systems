from enum import Enum

class UserRole(str, Enum):
    """Enum for user roles in the system"""
    OWNER = "OWNER"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"

class PermissionRole(str, Enum):
    """Enum for event permission roles."""
    OWNER = "OWNER"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER" 