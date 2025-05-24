from locust import HttpUser, task, between
from datetime import datetime, timedelta
import json

class EventUser(HttpUser):
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    token = None
    
    def on_start(self):
        """Log in before starting tasks."""
        # Register a new user
        username = f"loadtest_{self.user_id}@example.com"
        response = self.client.post(
            "/api/auth/register",
            json={
                "email": username,
                "password": "loadtest123",
                "username": f"loadtest_{self.user_id}"
            }
        )
        
        # Login to get token
        response = self.client.post(
            "/api/auth/login",
            data={
                "username": username,
                "password": "loadtest123"
            }
        )
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(3)  # Higher weight for common operations
    def list_events(self):
        """List events with date range."""
        start_time = datetime.utcnow().isoformat()
        end_time = (datetime.utcnow() + timedelta(days=30)).isoformat()
        self.client.get(
            f"/api/events/?start_time={start_time}&end_time={end_time}",
            headers=self.headers,
            name="/api/events/ [GET]"
        )
    
    @task(2)
    def get_event(self):
        """Get a specific event."""
        # First create an event
        event_data = {
            "title": f"Load Test Event {self.user_id}",
            "description": "Load testing",
            "start_time": datetime.utcnow().isoformat(),
            "end_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "is_recurring": False
        }
        response = self.client.post(
            "/api/events/",
            json=event_data,
            headers=self.headers,
            name="/api/events/ [POST]"
        )
        
        if response.status_code == 201:
            event_id = response.json()["id"]
            self.client.get(
                f"/api/events/{event_id}",
                headers=self.headers,
                name="/api/events/{id} [GET]"
            )
    
    @task(1)
    def create_and_update_event(self):
        """Create an event and then update it."""
        # Create event
        event_data = {
            "title": f"Update Test Event {self.user_id}",
            "description": "Will be updated",
            "start_time": datetime.utcnow().isoformat(),
            "end_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "is_recurring": False
        }
        response = self.client.post(
            "/api/events/",
            json=event_data,
            headers=self.headers,
            name="/api/events/ [POST]"
        )
        
        if response.status_code == 201:
            event_id = response.json()["id"]
            # Update event
            update_data = {
                "title": f"Updated Event {self.user_id}",
                "description": "Updated in load test"
            }
            self.client.put(
                f"/api/events/{event_id}",
                json=update_data,
                headers=self.headers,
                name="/api/events/{id} [PUT]"
            )
    
    @task(1)
    def batch_create_events(self):
        """Create multiple events in batch."""
        events = []
        for i in range(5):  # Create 5 events in batch
            events.append({
                "title": f"Batch Event {self.user_id}-{i}",
                "description": f"Batch created in load test {i}",
                "start_time": (datetime.utcnow() + timedelta(days=i)).isoformat(),
                "end_time": (datetime.utcnow() + timedelta(days=i, hours=1)).isoformat(),
                "is_recurring": False
            })
        
        self.client.post(
            "/api/events/batch",
            json={"events": events},
            headers=self.headers,
            name="/api/events/batch [POST]"
        )
    
    @task(1)
    def search_events(self):
        """Search events with different criteria."""
        scenarios = [
            # Date range search
            f"start_time={datetime.utcnow().isoformat()}&end_time={(datetime.utcnow() + timedelta(days=30)).isoformat()}",
            # Title search
            "search=Load Test",
            # Complex search
            f"start_time={datetime.utcnow().isoformat()}&end_time={(datetime.utcnow() + timedelta(days=30)).isoformat()}&search=Event&sort=start_time"
        ]
        
        for query in scenarios:
            self.client.get(
                f"/api/events/?{query}",
                headers=self.headers,
                name=f"/api/events/ [GET] {query.split('&')[0]}"
            )
    
    def on_stop(self):
        """Clean up after tasks."""
        self.client.post(
            "/api/auth/logout",
            headers=self.headers,
            name="/api/auth/logout [POST]"
        ) 