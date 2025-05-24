from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field, model_validator

class DateRangeQuery(BaseModel):
    """Schema for date range queries"""
    start_date: datetime
    end_date: datetime
    include_recurring: bool = True
    expand_recurring: bool = False  # Whether to expand recurring events into individual instances

    @model_validator(mode='after')
    def validate_date_range(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        if self.end_date - self.start_date > timedelta(days=365):
            raise ValueError("Date range cannot exceed 1 year")
        return self

class EventFilter(BaseModel):
    """Schema for event filtering"""
    date_range: Optional[DateRangeQuery] = None
    search_term: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    owner_id: Optional[int] = None
    is_recurring: Optional[bool] = None
    include_permissions: bool = False
    include_versions: bool = False 