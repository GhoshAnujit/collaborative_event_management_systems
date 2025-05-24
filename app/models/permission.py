from sqlalchemy import ForeignKey, Enum as SQLAEnum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base
from .enums import UserRole

class EventPermission(Base):
    """Event permission model."""
    
    __tablename__ = "event_permissions"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Required fields
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[UserRole] = mapped_column(SQLAEnum(UserRole), nullable=False)
    
    # Relationships
    event: Mapped["Event"] = relationship(back_populates="permissions")
    user: Mapped["User"] = relationship(back_populates="event_permissions")
    
    def __repr__(self):
        return f"<EventPermission(event_id={self.event_id}, user_id={self.user_id}, role={self.role})>"
    
    # Unique constraint to prevent duplicate permissions
    __table_args__ = (
        UniqueConstraint('event_id', 'user_id', name='uq_event_user_permission'),
    ) 