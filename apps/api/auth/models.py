"""Pydantic models for authentication."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator
import re


class RegisterRequest(BaseModel):
    """Registration request model."""
    
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    company_name: str = Field(min_length=2, max_length=255)
    name: Optional[str] = None
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Password must have uppercase, lowercase, and number."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        return v
    
    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, v: str) -> str:
        """Clean company name."""
        return v.strip()


class LoginRequest(BaseModel):
    """Login request model."""
    
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token response model."""
    
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class UserResponse(BaseModel):
    """User info response."""
    
    id: int
    email: str
    name: Optional[str]
    role: str
    tenant_id: int
    tenant_name: str
    tenant_slug: str


class AuthResponse(BaseModel):
    """Full auth response with user and token."""
    
    user: UserResponse
    token: TokenResponse


class MessageResponse(BaseModel):
    """Simple message response."""
    
    success: bool
    message: str
