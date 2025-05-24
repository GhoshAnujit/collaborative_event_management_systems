from datetime import datetime
from typing import Dict, Any
from pydantic import BaseModel, Field

class NotificationBase(BaseModel):
    """Base schema for notifications"""
    type: str = Field(..., min_length=1, max_length=50)
    message: str = Field(..., min_length=1, max_length=500)
    data: Dict[str, Any] = Field(default_factory=dict)

class NotificationCreate(NotificationBase):
    """Schema for creating notifications"""
    user_id: int
    event_id: int

class NotificationUpdate(BaseModel):
    """Schema for updating notifications"""
    is_read: bool = True

class NotificationResponse(NotificationBase):
    """Schema for notification response"""
    id: int
    user_id: int
    event_id: int
    created_at: datetime
    updated_at: datetime
    is_read: bool

    class Config:
        from_attributes = True

class WebSocketMessage(BaseModel):
    """Schema for WebSocket messages"""
    type: str = Field(..., pattern="^(notification|error|ping)$")
    data: Dict[str, Any] 