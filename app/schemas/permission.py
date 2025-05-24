from typing import List
from pydantic import Field, model_validator
from app.models.user import UserRole
from .base import BaseSchema

class EventPermissionBase(BaseSchema):
    """Base schema for event permissions"""
    role: UserRole = Field(..., description="Role assigned to the user for this event")

    @model_validator(mode='after')
    def validate_role(self):
        # Owner role can only be set during event creation
        if self.role == UserRole.OWNER:
            raise ValueError("Cannot set OWNER role through permissions")
        return self

class EventPermissionCreate(EventPermissionBase):
    """Schema for creating event permissions"""
    user_id: int = Field(..., gt=0)

class EventPermissionBatchCreate(BaseSchema):
    """Schema for batch creating permissions"""
    permissions: List[EventPermissionCreate] = Field(..., min_items=1, max_items=20)
    
    @model_validator(mode='after')
    def validate_unique_users(self):
        user_ids = [p.user_id for p in self.permissions]
        if len(user_ids) != len(set(user_ids)):
            raise ValueError("Duplicate user_ids found in batch permissions")
        return self

class EventPermissionUpdate(BaseSchema):
    """Schema for updating event permissions"""
    role: UserRole = Field(..., description="New role to assign to the user")

    @model_validator(mode='after')
    def validate_role_update(self):
        if self.role == UserRole.OWNER:
            raise ValueError("Cannot change role to OWNER")
        return self

class EventPermissionResponse(EventPermissionBase):
    """Schema for event permission response"""
    id: int
    event_id: int
    user_id: int
    user: 'UserResponse'

class EventPermissionList(BaseSchema):
    """Schema for listing event permissions"""
    permissions: List[EventPermissionResponse]
    total: int 