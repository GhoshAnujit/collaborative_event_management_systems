from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_token_pair,
    verify_token,
    get_password_hash,
    verify_password,
    get_current_user
)
from app.db.database import get_db
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserResponse
from app.crud.user import create_user, get_user_by_email
from app.models.user import User

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
    responses={
        401: {"description": "Authentication failed"},
        403: {"description": "Forbidden - insufficient permissions"},
        404: {"description": "Resource not found"},
        500: {"description": "Internal server error"}
    }
)

@router.post(
    "/login",
    response_model=Token,
    summary="Login for access token",
    description="""
    OAuth2 compatible token login endpoint. Authenticates a user and returns an access token
    and refresh token for future requests.
    
    The access token is valid for a limited time, while the refresh token can be used
    to obtain new access tokens without re-authentication.
    """,
    responses={
        200: {
            "description": "Successful login",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1...",
                        "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1...",
                        "token_type": "bearer"
                    }
                }
            }
        },
        401: {
            "description": "Invalid credentials",
            "content": {
                "application/json": {
                    "example": {"detail": "Incorrect email or password"}
                }
            }
        }
    }
)
async def login(
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    Authenticate user and return JWT token pair.
    
    - **username**: Email address of the user (used as username)
    - **password**: User's password
    """
    user = await get_user_by_email(db, email=form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token, refresh_token = create_token_pair({"sub": user.email})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    summary="Register new user",
    description="""
    Register a new user in the system.
    
    The endpoint performs the following:
    * Validates the email is not already registered
    * Securely hashes the password
    * Creates a new user record
    * Returns the created user's basic information
    """,
    responses={
        201: {
            "description": "User successfully created",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "email": "user@example.com",
                        "username": "johndoe"
                    }
                }
            }
        },
        400: {
            "description": "Email already registered",
            "content": {
                "application/json": {
                    "example": {"detail": "A user with this email already exists"}
                }
            }
        }
    }
)
async def register(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: UserCreate
) -> UserResponse:
    """
    Register a new user with the following information:
    
    - **email**: Unique email address
    - **password**: Strong password (min 8 characters)
    - **username**: Optional username
    """
    user = await get_user_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists",
        )
    
    try:
        user = await create_user(db, user_in)
        return UserResponse(id=user.id, email=user.email, username=user.username)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh access token",
    description="""
    Get a new access token using a valid refresh token.
    
    This endpoint allows clients to obtain a new access token without requiring the user
    to re-authenticate. The refresh token must be provided in the Authorization header
    with the Bearer prefix.
    """,
    responses={
        200: {
            "description": "New token pair generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1...",
                        "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1...",
                        "token_type": "bearer"
                    }
                }
            }
        },
        401: {
            "description": "Invalid or expired refresh token",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid refresh token"}
                }
            }
        }
    }
)
async def refresh_token(
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(..., description="The refresh token obtained during login, with Bearer prefix")
) -> Any:
    """
    Exchange a refresh token for a new access token.
    
    - **authorization**: Valid refresh token with Bearer prefix (provided in Authorization header)
    """
    try:
        # Extract token from Authorization header
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format",
                headers={"WWW-Authenticate": "Bearer"},
            )
        refresh_token = authorization.split(" ")[1]
        
        payload = verify_token(refresh_token, "refresh")
        email = payload.get("sub")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user = await get_user_by_email(db, email=email)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token, new_refresh_token = create_token_pair({"sub": user.email})
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post(
    "/logout",
    summary="Logout user",
    description="""
    Logout the current user.
    
    This endpoint invalidates the current session. The client should discard
    both access and refresh tokens after calling this endpoint.
    """,
    responses={
        200: {
            "description": "Successfully logged out",
            "content": {
                "application/json": {
                    "example": {"message": "Successfully logged out"}
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authenticated"}
                }
            }
        }
    }
)
async def logout(
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Logout the current authenticated user.
    
    Requires a valid access token in the Authorization header.
    """
    # In a more complex implementation, you might want to:
    # 1. Add the token to a blacklist
    # 2. Clear any session data
    # 3. Revoke refresh tokens
    # For now, we'll just return a success message as the client should discard the tokens
    return {"message": "Successfully logged out"}

async def get_current_user_from_token(token: str, db: AsyncSession = Depends(get_db)) -> User:
    """
    Retrieve the current user based on the provided JWT token.
    
    Parameters:
    - **token**: JWT token for authentication
    
    Returns the current user if the token is valid.
    Raises HTTPException if the token is invalid or expired.
    """
    user_id = verify_token(token)  # Implement this function to decode the token and extract user ID
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Fetch the user from the database
    user = await db.execute(User.select().where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    return user