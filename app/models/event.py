from datetime import datetime, timedelta, UTC
from typing import List, Dict, Any, Optional
from sqlalchemy import String, DateTime, Boolean, JSON, ForeignKey, Index, select, Column, Integer, Enum, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship
from dateutil.rrule import rrulestr
from sqlalchemy.sql import func
from .base import Base
from app.models.enums import PermissionRole
from app.schemas.event import BaseSchema

class Event(Base):
    """Event model for the core event management functionality"""
    
    __tablename__ = "events"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Required fields
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    
    # Optional fields
    description: Mapped[str | None] = mapped_column(String(1000))
    location: Mapped[str | None] = mapped_column(String(200))
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence_pattern: Mapped[Dict[str, Any] | None] = mapped_column(String(500))  # RFC 5545 RRULE format
    current_version: Mapped[int] = mapped_column(default=1)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="owned_events"
    )
    permissions: Mapped[List["EventPermission"]] = relationship(
        "EventPermission",
        back_populates="event",
        cascade="all, delete-orphan"
    )
    versions: Mapped[List["EventVersion"]] = relationship(
        "EventVersion",
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="EventVersion.version_number"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification",
        back_populates="event",
        cascade="all, delete-orphan"
    )
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('ix_event_date_range', 'start_time', 'end_time'),
        Index('ix_event_owner_dates', 'owner_id', 'start_time', 'end_time'),
    )
    
    def __repr__(self):
        return f"<Event(id={self.id}, title={self.title})>"
    
    def has_permission(self, user: Any, required_role: str = "VIEWER") -> bool:
        """Check if a user has the required permission level for this event"""
        if user.is_superuser or user.id == self.owner_id:
            return True
            
        for permission in self.permissions:
            if permission.user_id == user.id:
                role_values = {
                    "OWNER": 3,
                    "EDITOR": 2,
                    "VIEWER": 1
                }
                return role_values[permission.role] >= role_values[required_role]
        return False
    
    def add_version(self, changed_by: Any, changes: Dict[str, Any], description: str | None = None) -> Any:
        """Create a new version of this event"""
        from .version import EventVersion
        
        version = EventVersion(
            event_id=self.id,
            version_number=self.current_version + 1,
            changed_by_id=changed_by.id,
            event_data=self.dict(),
            changes=changes,
            change_description=description
        )
        self.versions.append(version)
        self.current_version += 1
        return version
    
    def get_next_occurrence(self, from_date: datetime | None = None) -> datetime | None:
        """Calculate the next occurrence of a recurring event"""
        if not self.is_recurring or not self.recurrence_pattern:
            return None
            
        if not from_date:
            from_date = datetime.utcnow()
        
        try:
            # Convert the recurrence pattern to an rrule string
            rrule_str = self.recurrence_pattern.get("rrule")
            if not rrule_str:
                return None
            
            # Parse the rrule and get the next occurrence
            rule = rrulestr(rrule_str, dtstart=self.start_time)
            next_dates = list(rule.after(from_date, inc=True) for _ in range(1))
            return next_dates[0] if next_dates else None
        except Exception:
            return None
    
    def get_occurrences(
        self,
        start: datetime,
        end: datetime,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get all occurrences of the event between start and end dates"""
        if not self.is_recurring or not self.recurrence_pattern:
            if start <= self.start_time <= end:
                return [{
                    "start_time": self.start_time,
                    "end_time": self.end_time,
                    "is_original": True
                }]
            return []
        
        try:
            rrule_str = self.recurrence_pattern.get("rrule")
            if not rrule_str:
                return []
            
            # Parse the rrule and get all occurrences
            rule = rrulestr(rrule_str, dtstart=self.start_time)
            occurrences = []
            
            # Calculate event duration
            duration = self.end_time - self.start_time
            
            # Get all start times within the range
            for dt in rule.between(start, end, inc=True):
                if len(occurrences) >= limit:
                    break
                    
                occurrences.append({
                    "start_time": dt,
                    "end_time": dt + duration,
                    "is_original": dt == self.start_time
                })
            
            return occurrences
        except Exception:
            return []
    
    async def check_conflicts(
        self,
        db: AsyncSession,
        start_time: datetime,
        end_time: datetime,
        exclude_self: bool = True
    ) -> List["Event"]:
        """Check for conflicting events in the given time range"""
        query = select(Event).where(
            and_(
                Event.is_deleted == False,
                or_(
                    and_(
                        Event.start_time <= end_time,
                        Event.end_time >= start_time
                    ),
                    and_(
                        Event.start_time >= start_time,
                        Event.start_time <= end_time
                    ),
                    and_(
                        Event.end_time >= start_time,
                        Event.end_time <= end_time
                    )
                )
            )
        )
        
        if exclude_self and self.id:
            query = query.where(Event.id != self.id)
        
        result = await db.execute(query)
        events = result.scalars().all()
        
        # Check recurring events
        recurring_conflicts = []
        for event in events:
            if event.is_recurring:
                occurrences = event.get_occurrences(start_time, end_time)
                if any(
                    occ["start_time"] < end_time and
                    occ["end_time"] > start_time
                    for occ in occurrences
                ):
                    recurring_conflicts.append(event)
            else:
                recurring_conflicts.append(event)
        
        return recurring_conflicts

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for version storage."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "location": self.location,
            "start_time": BaseSchema.serialize_datetime(self.start_time),
            "end_time": BaseSchema.serialize_datetime(self.end_time),
            "is_recurring": self.is_recurring,
            "recurrence_pattern": self.recurrence_pattern,
            "current_version": self.current_version,
            "is_deleted": self.is_deleted,
            "created_at": BaseSchema.serialize_datetime(self.created_at),
            "updated_at": BaseSchema.serialize_datetime(self.updated_at),
            "owner_id": self.owner_id
        } 