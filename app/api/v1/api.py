from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, events, notifications

api_router = APIRouter()
 
# Include all route modules
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(events.router)
api_router.include_router(notifications.router)