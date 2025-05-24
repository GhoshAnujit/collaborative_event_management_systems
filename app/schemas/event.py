from datetime import datetime, timedelta, UTC
from typing import Any, Dict, Optional, List, Union
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationInfo
from dateutil.rrule import rrulestr


# --- Base Schemas ---
class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = {
        "from_attributes": True,
        "json_encoders": {
            datetime: lambda dt: dt.isoformat() if dt.tzinfo else dt.replace(tzinfo=UTC).isoformat()
        }
    }

    @classmethod
    def serialize_datetime(cls, dt: Optional[datetime]) -> Optional[str]:
        """Serialize datetime consistently across the application."""
        if dt is None:
            return None
        return dt.isoformat() if dt.tzinfo else dt.replace(tzinfo=UTC).isoformat()


class TimestampSchema(BaseSchema):
    created_at: datetime
    updated_at: datetime


# --- Recurrence ---
class RecurrencePattern(BaseSchema):
    """Schema for event recurrence pattern"""
    rrule: str = Field(..., description="RFC 5545 RRULE string")

    @field_validator("rrule")
    @classmethod
    def validate_rrule(cls, v: str) -> str:
        try:
            rrulestr(v)
            return v
        except Exception:
            raise ValueError("Invalid RRULE string")


# --- Core Event Schemas ---
class UserInfo(BaseSchema):
    id: int
    email: str


class EventBase(BaseSchema):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    location: Optional[str] = Field(None, max_length=200)
    start_time: datetime
    end_time: datetime
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def parse_datetime(cls, v: Any) -> datetime:
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
                return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
            except ValueError as e:
                raise ValueError("Invalid datetime format") from e
        elif isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=UTC)
        raise ValueError("Invalid datetime type")

    @model_validator(mode="after")
    def validate_dates(self) -> "EventBase":
        if self.start_time >= self.end_time:
            raise ValueError("End time must be after start time")
        return self

    @field_validator("recurrence_pattern")
    @classmethod
    def validate_recurrence_pattern(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not v.startswith("RRULE:"):
            v = f"RRULE:{v}"
        try:
            rrulestr(v)
            return v
        except Exception as e:
            raise ValueError(f"Invalid RRULE string: {str(e)}") from e


class EventCreate(EventBase):
    pass


class EventBatchCreate(BaseSchema):
    events: List[EventCreate] = Field(..., min_length=1, max_length=50)


class EventUpdate(EventBase):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_recurring: Optional[bool] = None

    @model_validator(mode="after")
    def validate_update(self) -> "EventUpdate":
        update_fields = {
            k: v for k, v in self.model_dump().items()
            if v is not None and k != "id"
        }
        if not update_fields:
            raise ValueError("At least one field must be updated")
        return self
        
    @model_validator(mode="after")
    def validate_dates(self) -> "EventUpdate":
        # Only validate dates if both start_time and end_time are provided
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError("End time must be after start time")
        return self


class EventResponse(EventBase):
    id: int
    created_by: UserInfo
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_response(self) -> "EventResponse":
        if not self.created_by:
            raise ValueError("created_by field is required")
        return self


class EventInDB(EventBase, TimestampSchema):
    id: int
    owner_id: int
    current_version: int


# --- Permissions ---
class EventPermissionCreate(BaseModel):
    user_id: int
    role: str = Field(..., pattern="^(OWNER|EDITOR|VIEWER)$")


class EventPermissionResponse(BaseModel):
    user_id: int
    role: str
    model_config = {"from_attributes": True}


class EventWithPermissions(EventResponse):
    permissions: List[EventPermissionResponse] = []


# --- Versioning ---
class EventVersionResponse(BaseSchema):
    version_number: int
    changed_by_id: int
    event_data: Dict[str, Any]
    changes: Dict[str, Any]
    change_description: Optional[str] = None
    created_at: datetime


class EventVersionDiff(BaseSchema):
    version1: int
    version2: int
    changes: Dict[str, Dict[str, Any]]
    changed_by: Dict[str, Any]
    changed_at: datetime
    model_config = {"from_attributes": True}


# --- Filtering and Search ---
class DateRangeQuery(BaseSchema):
    start_date: datetime
    end_date: datetime
    include_recurring: bool = True
    expand_recurring: bool = False

    @model_validator(mode="after")
    def validate_date_range(self) -> "DateRangeQuery":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        if self.end_date - self.start_date > timedelta(days=365):
            raise ValueError("Date range cannot exceed 1 year")
        return self


class EventFilter(BaseSchema):
    date_range: Optional[DateRangeQuery] = None
    search_term: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    owner_id: Optional[int] = None
    is_recurring: Optional[bool] = None
    include_permissions: bool = False
    include_versions: bool = False


class EventListResponse(BaseSchema):
    items: List[EventResponse]
    total: int
    page: int
    size: int
    filters_applied: Optional[EventFilter] = None
    date_range: Optional[DateRangeQuery] = None


# --- Occurrences and Conflicts ---
class EventOccurrence(BaseModel):
    event_id: int
    start_time: datetime
    end_time: datetime
    is_recurring: bool
    is_original: bool


class EventConflict(BaseSchema):
    event_id: int
    title: str
    start_time: datetime
    end_time: datetime
    owner_id: int


# --- Audit Log ---
class AuditLogEntry(BaseSchema):
    timestamp: datetime
    action: str = Field(..., pattern="^(CREATE|UPDATE|DELETE|SHARE|UNSHARE|VERSION)$")
    user_id: int
    event_id: int
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
