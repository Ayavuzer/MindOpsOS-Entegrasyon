"""Authentication API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .models import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    UserResponse,
    MessageResponse,
)
from .service import AuthService
from .jwt import decode_token, extract_jti

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
security = HTTPBearer(auto_error=False)

# Service will be injected from main.py
_auth_service: Optional[AuthService] = None


def set_auth_service(service: AuthService):
    """Set auth service instance."""
    global _auth_service
    _auth_service = service


def get_auth_service() -> AuthService:
    """Get auth service."""
    if _auth_service is None:
        raise HTTPException(500, "Auth service not initialized")
    return _auth_service


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UserResponse:
    """
    Dependency to get current authenticated user.
    
    Raises:
        HTTPException 401 if not authenticated
    """
    if credentials is None:
        raise HTTPException(401, "Not authenticated")
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None:
        raise HTTPException(401, "Invalid or expired token")
    
    # Check if session is still valid
    service = get_auth_service()
    jti = payload.get("jti")
    if jti and not await service.is_session_valid(jti):
        raise HTTPException(401, "Session expired")
    
    # Get fresh user data
    user_id = int(payload["sub"])
    user = await service.get_user_by_id(user_id)
    
    if user is None:
        raise HTTPException(401, "User not found or disabled")
    
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[UserResponse]:
    """Dependency to get current user if authenticated."""
    if credentials is None:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


@router.post("/register", response_model=AuthResponse)
async def register(data: RegisterRequest):
    """
    Register new user and organization.
    
    Creates a new tenant (organization) and user as admin.
    """
    service = get_auth_service()
    
    try:
        return await service.register(
            email=data.email,
            password=data.password,
            company_name=data.company_name,
            name=data.name,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/login", response_model=AuthResponse)
async def login(data: LoginRequest):
    """
    Login with email and password.
    
    Returns JWT token on success.
    """
    service = get_auth_service()
    
    try:
        return await service.login(
            email=data.email,
            password=data.password,
        )
    except ValueError as e:
        raise HTTPException(401, str(e))


@router.post("/logout", response_model=MessageResponse)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Logout current session.
    
    Invalidates the current JWT token.
    """
    if credentials is None:
        raise HTTPException(401, "Not authenticated")
    
    token = credentials.credentials
    jti = extract_jti(token)
    
    if jti:
        service = get_auth_service()
        await service.logout(jti)
    
    return MessageResponse(success=True, message="Logged out successfully")


@router.get("/me", response_model=UserResponse)
async def get_me(user: UserResponse = Depends(get_current_user)):
    """
    Get current user info.
    
    Returns user and tenant details.
    """
    return user
