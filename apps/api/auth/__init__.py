"""Authentication module."""

from .routes import router, set_auth_service, get_current_user, get_optional_user
from .service import AuthService
from .models import UserResponse, AuthResponse
from .password import hash_password, verify_password
from .jwt import create_access_token, decode_token

__all__ = [
    "router",
    "set_auth_service",
    "get_current_user",
    "get_optional_user",
    "AuthService",
    "UserResponse",
    "AuthResponse",
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_token",
]
