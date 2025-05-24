from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import Field, model_validator
from .base import BaseSchema, TimestampSchema

class ChangeField(BaseSchema):
    """Schema for tracking field changes"""
    old_value: Any | None = None
    new_value: Any
    field_type: str = Field(..., description="Data type of the field")

class EventVersionBase(BaseSchema):
    """Base schema for event versions"""
    version_number: int = Field(..., gt=0)
    event_data: Dict[str, Any]
    change_description: str | None = Field(None, max_length=500)
    changed_fields: Dict[str, ChangeField] = {}
    concurrent_edit_id: str | None = None  # For tracking concurrent edits
    client_timestamp: datetime = Field(..., description="Client-side timestamp for conflict resolution")

class EventVersionCreate(EventVersionBase):
    """Schema for creating event versions"""
    pass

class EventVersionResponse(EventVersionBase, TimestampSchema):
    """Schema for event version response"""
    id: int
    event_id: int
    changed_by_id: int
    changed_by: 'UserResponse'

class EventDiffResponse(BaseSchema):
    """Schema for version diff response"""
    changes: Dict[str, Dict[str, Any]]
    version1: EventVersionResponse
    version2: EventVersionResponse
    field_by_field_diff: Dict[str, ChangeField]
    summary: str = Field(..., description="Human-readable summary of changes")

class ChangelogEntry(BaseSchema):
    """Schema for changelog entries"""
    version: EventVersionResponse
    timestamp: datetime
    user: 'UserResponse'
    summary: str
    affected_fields: List[str]

class ChangelogResponse(BaseSchema):
    """Schema for paginated changelog"""
    entries: List[ChangelogEntry]
    total: int
    page: int
    size: int

class TemporalQuery(BaseSchema):
    """Schema for temporal queries"""
    point_in_time: datetime
    include_changes: bool = False  # Whether to include change history
    version_number: int | None = None  # Optional specific version to query 