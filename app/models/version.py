from typing import Dict, Any
from sqlalchemy import ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

class EventVersion(Base):
    """Model for tracking event versions and changes"""
    
    __tablename__ = "event_versions"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Required fields
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(nullable=False)
    changed_by_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    event_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    
    # Optional fields
    changes: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    change_description: Mapped[str | None] = mapped_column(String(500))
    client_timestamp: Mapped[str | None] = mapped_column(String(50))  # For conflict resolution
    
    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="versions")
    changed_by: Mapped["User"] = relationship("User", back_populates="event_versions")
    
    # Unique constraint for version numbers per event
    __table_args__ = (
        UniqueConstraint('event_id', 'version_number', name='uq_event_version_number'),
    )
    
    def get_diff(self, other: "EventVersion") -> Dict[str, Any]:
        """Calculate the difference between two versions"""
        diff = {}
        for key in set(self.event_data.keys()) | set(other.event_data.keys()):
            old_value = self.event_data.get(key)
            new_value = other.event_data.get(key)
            if old_value != new_value:
                diff[key] = {
                    'old': old_value,
                    'new': new_value
                }
        return diff 