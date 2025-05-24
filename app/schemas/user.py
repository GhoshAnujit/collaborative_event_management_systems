from pydantic import BaseModel, EmailStr, Field
from app.models.user import UserRole
from .base import BaseSchema

class UserBase(BaseSchema):
    """Base schema for user data"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str | None = None

class UserCreate(UserBase):
    """Schema for user registration"""
    password: str = Field(..., min_length=8)

class UserUpdate(UserBase):
    """Schema for user update"""
    email: EmailStr | None = None
    username: str | None = Field(None, min_length=3, max_length=50)
    password: str | None = Field(None, min_length=8)

class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str

class UserResponse(UserBase):
    """Schema for user response data"""
    id: int
    is_active: bool = True
    is_superuser: bool = False

    class Config:
        from_attributes = True

class Token(BaseModel):
    """Schema for JWT token"""
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Schema for JWT token payload"""
    email: str | None = None
    user_id: int | None = None 