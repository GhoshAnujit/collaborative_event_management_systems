from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict

class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = ConfigDict(from_attributes=True)

class TimestampSchema(BaseSchema):
    """Schema with timestamp fields."""
    created_at: datetime | None = None
    updated_at: datetime | None = None 