#!/usr/bin/env python3
"""
Seed script to create initial data for the application.
Run this after deployment to populate the database with test data.
"""
import asyncio
import datetime
from app.db.database import AsyncSessionLocal
from app.models.user import User
from app.models.event import Event
from app.core.security import get_password_hash
from app.models.enums import PermissionRole
from app.models.permissions import EventPermission

async def seed_data():
    """Seed the database with initial data."""
    print("Starting database seeding...")
    
    async with AsyncSessionLocal() as session:
        # Create test users
        admin_user = User(
            email="admin@example.com",
            username="admin",
            hashed_password=get_password_hash("admin123"),
            full_name="Admin User",
            is_active=True,
            is_superuser=True
        )
        
        test_user = User(
            email="test@example.com",
            username="testuser",
            hashed_password=get_password_hash("test123"),
            full_name="Test User",
            is_active=True
        )
        
        demo_user = User(
            email="demo@example.com",
            username="demouser",
            hashed_password=get_password_hash("demo123"),
            full_name="Demo User",
            is_active=True
        )
        
        # Add users to session
        session.add(admin_user)
        session.add(test_user)
        session.add(demo_user)
        await session.commit()
        
        # Refresh to get IDs
        await session.refresh(admin_user)
        await session.refresh(test_user)
        await session.refresh(demo_user)
        
        print(f"Created users: admin_user(id={admin_user.id}), test_user(id={test_user.id}), demo_user(id={demo_user.id})")
        
        # Create sample events
        now = datetime.datetime.now(datetime.UTC)
        
        event1 = Event(
            title="Team Meeting",
            description="Weekly team sync",
            start_time=now + datetime.timedelta(days=1),
            end_time=now + datetime.timedelta(days=1, hours=1),
            owner_id=admin_user.id,
            location="Conference Room A",
            is_recurring=True,
            recurrence_pattern="RRULE:FREQ=WEEKLY;COUNT=4"
        )
        
        event2 = Event(
            title="Project Review",
            description="End of sprint review",
            start_time=now + datetime.timedelta(days=2),
            end_time=now + datetime.timedelta(days=2, hours=2),
            owner_id=admin_user.id,
            location="Meeting Room B",
            is_recurring=False
        )
        
        event3 = Event(
            title="Demo Session",
            description="Product demo for stakeholders",
            start_time=now + datetime.timedelta(days=3),
            end_time=now + datetime.timedelta(days=3, hours=1, minutes=30),
            owner_id=test_user.id,
            location="Main Hall",
            is_recurring=False
        )
        
        # Add events to session
        session.add(event1)
        session.add(event2)
        session.add(event3)
        await session.commit()
        
        # Refresh to get IDs
        await session.refresh(event1)
        await session.refresh(event2)
        await session.refresh(event3)
        
        print(f"Created events: event1(id={event1.id}), event2(id={event2.id}), event3(id={event3.id})")
        
        # Create permissions
        # Admin is already owner of events 1 and 2
        # Test user is already owner of event 3
        
        # Give test user editor access to event 1
        perm1 = EventPermission(
            event_id=event1.id,
            user_id=test_user.id,
            role=PermissionRole.EDITOR
        )
        
        # Give demo user viewer access to events 1, 2, and 3
        perm2 = EventPermission(
            event_id=event1.id,
            user_id=demo_user.id,
            role=PermissionRole.VIEWER
        )
        
        perm3 = EventPermission(
            event_id=event2.id,
            user_id=demo_user.id,
            role=PermissionRole.VIEWER
        )
        
        perm4 = EventPermission(
            event_id=event3.id,
            user_id=demo_user.id,
            role=PermissionRole.VIEWER
        )
        
        # Add permissions to session
        session.add(perm1)
        session.add(perm2)
        session.add(perm3)
        session.add(perm4)
        
        # Commit changes
        await session.commit()
        
        print("Created permissions for test events")
        
    print("Database seeding completed successfully!")

if __name__ == "__main__":
    asyncio.run(seed_data()) 