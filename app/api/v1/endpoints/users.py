from fastapi import APIRouter, status
from pydantic import BaseModel

class TestResponse(BaseModel):
    message: str

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized"},
        404: {"description": "User not found"},
        500: {"description": "Internal server error"}
    }
)
 
@router.get(
    "/test",
    response_model=TestResponse,
    status_code=status.HTTP_200_OK,
    summary="Test endpoint",
    description="""
    Simple test endpoint to verify the users router is working.
    
    This endpoint is primarily for development and testing purposes.
    """,
    responses={
        200: {
            "description": "Router is working",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Users endpoint is working"
                    }
                }
            }
        }
    }
)
async def test_endpoint() -> TestResponse:
    """
    Test endpoint to verify router is working.
    
    Returns a simple message confirming the endpoint is accessible.
    """
    return TestResponse(message="Users endpoint is working") 