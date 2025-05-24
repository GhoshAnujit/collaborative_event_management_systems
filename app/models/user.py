from typing import List
from datetime import datetime
from sqlalchemy import String, Enum as SQLAEnum, Column, Integer, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from .base import Base
from .enums import UserRole
from .notification import Notification
from .event import Event
from .permission import EventPermission
from .version import EventVersion

class User(Base):
    """User model for authentication and authorization"""
    
    __tablename__ = "user"  # Changed from "users" to "user" to match migration
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Required fields
    email: Mapped[str] = mapped_column(
        String(255), 
        unique=True, 
        index=True, 
        nullable=False
    )
    username: Mapped[str] = mapped_column(
        String(50), 
        unique=True, 
        index=True, 
        nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255), 
        nullable=False
    )
    
    # Optional fields
    full_name: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(default=True)
    is_superuser: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    owned_events: Mapped[List["Event"]] = relationship(
        "Event",
        back_populates="owner",
        cascade="all, delete-orphan"
    )
    event_permissions: Mapped[List["EventPermission"]] = relationship(
        "EventPermission",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    event_versions: Mapped[List["EventVersion"]] = relationship(
        "EventVersion",
        back_populates="changed_by"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.username}>" 