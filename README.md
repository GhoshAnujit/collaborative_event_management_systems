# Collaborative Event Management System

A FastAPI-based backend system for managing collaborative events with advanced features like real-time notifications, version control, and granular permissions.

## Features

### Authentication & Authorization
- Secure JWT-based authentication
- Role-based access control (OWNER, EDITOR, VIEWER)
- Token refresh mechanism
- Rate limiting (5/min for auth, 100/min for regular endpoints)

### Event Management
- CRUD operations for events
- Recurring events with RFC 5545 RRULE patterns
- Conflict detection and resolution
- Batch operations (up to 50 events)
- Efficient date range querying

### Collaboration
- Granular permission system
- Real-time notifications via WebSocket
- Version history with rollback capability
- Changelog with diff visualization
- Atomic operations

### Performance & Security
- In-memory caching with TTL
- Rate limiting per endpoint/user
- MessagePack support for efficient serialization
- SQL injection prevention
- CORS protection

## Tech Stack

- **Framework**: FastAPI
- **Database**: SQLite with async support (via SQLAlchemy)
- **Authentication**: JWT (python-jose)
- **Password Hashing**: bcrypt
- **WebSocket**: native FastAPI WebSocket support
- **Caching**: In-memory with TTL
- **Serialization**: JSON & MessagePack
- **Testing**: pytest with async support

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd neofi_backend
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Run database migrations:
```bash
alembic upgrade head
```

## Running the Application

1. Start the server:
```bash
uvicorn app.main:app --reload
```

2. Access the API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Deploying to Railway

This application is configured for easy deployment to Railway's platform.

### Prerequisites

- A [Railway](https://railway.app) account
- This repository pushed to your GitHub account

### Deployment Steps

1. Log in to Railway and click "New Project"
2. Select "Deploy from GitHub repo"
3. Connect your GitHub account and select this repository
4. Railway will automatically detect the Python project and build it
5. Once deployed, you can access your API at the provided Railway domain

### Environment Variables

Railway will automatically set most environment variables, but you may need to configure the following in the Railway dashboard:

- `SECRET_KEY`: A secure secret key for JWT generation
- `ENVIRONMENT`: Set to "production" for deployment
- `BACKEND_CORS_ORIGINS`: Configure allowed origins for CORS

### Database

This application uses SQLite by default, which is suitable for demo purposes. The database file is stored in the `sqlite_db` directory, which is created automatically during deployment.

For a production deployment, you might want to:
1. Continue using SQLite for simplicity (works well for demos)
2. Configure a PostgreSQL database for more robust storage

### Seed Data

After deployment, you can run the seed script to populate the database with test data:

```bash
python seed_data.py
```

This will create:
- Admin user: admin@example.com / admin123
- Test user: test@example.com / test123
- Demo user: demo@example.com / demo123
- Sample events with appropriate permissions

### API Documentation

After deployment, your API documentation will be available at:
- Swagger UI: `https://your-railway-app.railway.app/docs`
- ReDoc: `https://your-railway-app.railway.app/redoc`

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## API Documentation

### Authentication Endpoints

#### POST /api/auth/register
Register a new user.
```json
{
    "email": "user@example.com",
    "password": "securepass",
    "username": "username"
}
```

#### POST /api/auth/login
Login and receive tokens.
```json
{
    "username": "user@example.com",
    "password": "securepass"
}
```

### Event Endpoints

#### POST /api/events
Create a new event.
```json
{
    "title": "Team Meeting",
    "description": "Weekly sync",
    "start_time": "2024-03-20T10:00:00Z",
    "end_time": "2024-03-20T11:00:00Z",
    "location": "Conference Room",
    "is_recurring": false
}
```

#### GET /api/events
List events with pagination and filtering.
```
GET /api/events?start_time=2024-03-20T00:00:00Z&end_time=2024-03-21T00:00:00Z&skip=0&limit=100
```

See the full API documentation at `/docs` for more endpoints and details.

## Testing

Run the test suite:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=app tests/
```

### Performance Testing

The system includes comprehensive performance testing:

1. Unit Performance Tests:
```bash
pytest tests/test_performance.py -v
```
These tests measure:
- Response times for different page sizes
- Concurrent request handling
- Caching effectiveness
- WebSocket notification latency
- Search and filtering performance

2. Load Testing with Locust:
```bash
locust -f tests/locustfile.py
```
Then visit http://localhost:8089 to start the load test. The load test simulates:
- Multiple concurrent users
- Various API operations with realistic delays
- Different usage patterns and scenarios

Performance Targets:
- API response time < 100ms for cached requests
- API response time < 1s for uncached requests
- Support for 100+ concurrent users
- WebSocket notification delivery < 500ms
- Batch operations processing 50 events < 5s

3. Parallel Test Execution:
```bash
pytest -n auto  # Runs tests in parallel using available CPU cores
```

4. Benchmark Specific Operations:
```bash
pytest tests/test_performance.py --benchmark-only
```

## Caching Strategy

The system implements a TTL-based caching mechanism:
- Event listings: 5-minute cache
- Event details: 1-minute cache
- Cache invalidation on updates
- Per-user cache isolation

## Rate Limiting

Two-tier rate limiting system:
- Authentication endpoints: 5 requests per minute
- Regular endpoints: 100 requests per minute
- Per-user and per-endpoint tracking
- Automatic cleanup of old records

## WebSocket Notifications

Real-time notifications for:
- Event creation/updates/deletion
- Permission changes
- Version history updates
- System announcements

Connect to WebSocket:
```javascript
ws = new WebSocket("ws://localhost:8000/api/notifications/ws?token=<your-jwt-token>")
```

## Performance Considerations

1. Database Optimization:
   - Efficient indexing on frequently queried fields
   - Async database operations
   - Connection pooling

2. Caching:
   - In-memory caching for frequently accessed data
   - Cache invalidation on updates
   - Per-user cache isolation

3. Rate Limiting:
   - Prevents abuse
   - Ensures system stability
   - Configurable limits

4. MessagePack Support:
   - Reduced payload size
   - Faster serialization/deserialization
   - Content negotiation based on Accept header

## Security Measures

1. Authentication:
   - JWT with refresh tokens
   - Secure password hashing
   - Token blacklisting

2. Authorization:
   - Role-based access control
   - Granular permissions
   - Resource isolation

3. Data Protection:
   - Input validation
   - SQL injection prevention
   - CORS protection

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Database Optimization

The system implements several database optimizations for improved performance:

### Indexes
- B-tree indexes on frequently queried fields
- Composite indexes for common query patterns
- Full-text search indexes using pg_trgm
- Covering indexes for permission checks

Key Indexes:
- Event date range: `(start_time, end_time)`
- Permission lookups: `(event_id, user_id, role)`
- Full-text search: `gin(title, description)`

### Connection Pooling
- Pool size: 20 connections
- Max overflow: 10 connections
- Connection recycling: 30 minutes
- Health checks enabled
- TCP keepalive configured

### Query Optimization
- Efficient date range queries
- Batch operations for bulk changes
- Lazy loading of related data
- Pagination with cursor-based approach
- Materialized views for complex reports

### Monitoring
Monitor database performance using:
```bash
# Show current connections
SELECT * FROM pg_stat_activity;

# Show index usage
SELECT * FROM pg_stat_user_indexes;

# Show table statistics
SELECT * FROM pg_stat_user_tables;
```

## Documentation

- [System Architecture](docs/architecture.md) - Detailed system design and component interactions
- [API Documentation](docs/api.md) - API endpoints and usage
- [Database Schema](docs/architecture.md#database-schema) - Database structure and relationships
- [Caching Strategy](docs/architecture.md#caching-strategy) - Caching implementation details
- [Rate Limiting](docs/architecture.md#rate-limiting) - Rate limiting configuration
