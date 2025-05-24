# API Documentation

## Authentication

### Register User
```http
POST /api/auth/register
Content-Type: application/json

{
    "email": "user@example.com",
    "password": "securepass",
    "username": "username"
}
```

Response:
```json
{
    "id": 1,
    "email": "user@example.com",
    "username": "username",
    "created_at": "2024-03-19T10:00:00Z"
}
```

### Login
```http
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=securepass
```

Response:
```json
{
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "bearer"
}
```

### Refresh Token
```http
POST /api/auth/refresh
Authorization: Bearer <refresh_token>
```

Response:
```json
{
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "bearer"
}
```

### Logout
```http
POST /api/auth/logout
Authorization: Bearer <access_token>
```

Response: `204 No Content`

## Events

### Create Event
```http
POST /api/events
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "title": "Team Meeting",
    "description": "Weekly sync",
    "start_time": "2024-03-20T10:00:00Z",
    "end_time": "2024-03-20T11:00:00Z",
    "location": "Conference Room",
    "is_recurring": false
}
```

Response:
```json
{
    "id": 1,
    "title": "Team Meeting",
    "description": "Weekly sync",
    "start_time": "2024-03-20T10:00:00Z",
    "end_time": "2024-03-20T11:00:00Z",
    "location": "Conference Room",
    "is_recurring": false,
    "created_by": 1,
    "created_at": "2024-03-19T10:00:00Z",
    "updated_at": "2024-03-19T10:00:00Z"
}
```

### List Events
```http
GET /api/events?start_time=2024-03-20T00:00:00Z&end_time=2024-03-21T00:00:00Z&skip=0&limit=100
Authorization: Bearer <access_token>
```

Response:
```json
{
    "total": 1,
    "items": [
        {
            "id": 1,
            "title": "Team Meeting",
            "description": "Weekly sync",
            "start_time": "2024-03-20T10:00:00Z",
            "end_time": "2024-03-20T11:00:00Z",
            "location": "Conference Room",
            "is_recurring": false,
            "created_by": 1,
            "created_at": "2024-03-19T10:00:00Z",
            "updated_at": "2024-03-19T10:00:00Z"
        }
    ]
}
```

### Get Event
```http
GET /api/events/{event_id}
Authorization: Bearer <access_token>
```

Response:
```json
{
    "id": 1,
    "title": "Team Meeting",
    "description": "Weekly sync",
    "start_time": "2024-03-20T10:00:00Z",
    "end_time": "2024-03-20T11:00:00Z",
    "location": "Conference Room",
    "is_recurring": false,
    "created_by": 1,
    "created_at": "2024-03-19T10:00:00Z",
    "updated_at": "2024-03-19T10:00:00Z",
    "permissions": [
        {
            "user_id": 1,
            "role": "OWNER"
        }
    ]
}
```

### Update Event
```http
PUT /api/events/{event_id}
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "title": "Updated Team Meeting",
    "description": "Updated description"
}
```

Response:
```json
{
    "id": 1,
    "title": "Updated Team Meeting",
    "description": "Updated description",
    "start_time": "2024-03-20T10:00:00Z",
    "end_time": "2024-03-20T11:00:00Z",
    "location": "Conference Room",
    "is_recurring": false,
    "created_by": 1,
    "created_at": "2024-03-19T10:00:00Z",
    "updated_at": "2024-03-19T10:30:00Z"
}
```

### Delete Event
```http
DELETE /api/events/{event_id}
Authorization: Bearer <access_token>
```

Response: `204 No Content`

### Share Event
```http
POST /api/events/{event_id}/share
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "user_id": 2,
    "role": "EDITOR"
}
```

Response:
```json
{
    "event_id": 1,
    "user_id": 2,
    "role": "EDITOR"
}
```

### Batch Create Events
```http
POST /api/events/batch
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "events": [
        {
            "title": "Event 1",
            "start_time": "2024-03-20T10:00:00Z",
            "end_time": "2024-03-20T11:00:00Z"
        },
        {
            "title": "Event 2",
            "start_time": "2024-03-21T10:00:00Z",
            "end_time": "2024-03-21T11:00:00Z"
        }
    ]
}
```

Response:
```json
{
    "created": 2,
    "events": [
        {
            "id": 1,
            "title": "Event 1",
            "start_time": "2024-03-20T10:00:00Z",
            "end_time": "2024-03-20T11:00:00Z"
        },
        {
            "id": 2,
            "title": "Event 2",
            "start_time": "2024-03-21T10:00:00Z",
            "end_time": "2024-03-21T11:00:00Z"
        }
    ]
}
```

## Notifications

### List Notifications
```http
GET /api/notifications
Authorization: Bearer <access_token>
```

Response:
```json
{
    "total": 1,
    "items": [
        {
            "id": 1,
            "type": "event.update",
            "event_id": 1,
            "message": "Event 'Team Meeting' was updated",
            "is_read": false,
            "created_at": "2024-03-19T10:30:00Z"
        }
    ]
}
```

### Mark Notification as Read
```http
PUT /api/notifications/{notification_id}/read
Authorization: Bearer <access_token>
```

Response:
```json
{
    "id": 1,
    "type": "event.update",
    "event_id": 1,
    "message": "Event 'Team Meeting' was updated",
    "is_read": true,
    "created_at": "2024-03-19T10:30:00Z"
}
```

### Mark All Notifications as Read
```http
PUT /api/notifications/read-all
Authorization: Bearer <access_token>
```

Response: `204 No Content`

### WebSocket Connection
```javascript
const ws = new WebSocket("ws://localhost:8000/api/notifications/ws?token=<access_token>");

ws.onmessage = (event) => {
    const notification = JSON.parse(event.data);
    console.log(notification);
};
```

Example notification:
```json
{
    "type": "notification",
    "data": {
        "type": "event.update",
        "event_id": 1,
        "message": "Event 'Team Meeting' was updated",
        "timestamp": "2024-03-19T10:30:00Z"
    }
}
```

## Response Formats

The API supports both JSON and MessagePack formats. To use MessagePack:

1. Set the Accept header:
```http
Accept: application/x-msgpack
```

2. For POST/PUT requests, set Content-Type:
```http
Content-Type: application/x-msgpack
```

## Rate Limiting

- Authentication endpoints: 5 requests per minute per IP
- Regular endpoints: 100 requests per minute per user
- Rate limit headers in response:
  - `X-RateLimit-Limit`: Maximum requests per window
  - `X-RateLimit-Remaining`: Remaining requests in current window
  - `X-RateLimit-Reset`: Time when the rate limit resets

## Error Responses

### 400 Bad Request
```json
{
    "detail": {
        "code": "VALIDATION_ERROR",
        "message": "Validation error",
        "errors": [
            {
                "field": "title",
                "message": "Field required"
            }
        ]
    }
}
```

### 401 Unauthorized
```json
{
    "detail": {
        "code": "UNAUTHORIZED",
        "message": "Invalid credentials"
    }
}
```

### 403 Forbidden
```json
{
    "detail": {
        "code": "FORBIDDEN",
        "message": "Insufficient permissions"
    }
}
```

### 404 Not Found
```json
{
    "detail": {
        "code": "NOT_FOUND",
        "message": "Event not found"
    }
}
```

### 429 Too Many Requests
```json
{
    "detail": {
        "code": "RATE_LIMIT_EXCEEDED",
        "message": "Too many requests",
        "reset_at": "2024-03-19T10:01:00Z"
    }
}
``` 