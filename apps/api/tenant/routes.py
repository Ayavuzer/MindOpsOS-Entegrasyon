"""Tenant settings API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user, UserResponse
from .models import (
    TenantSettingsResponse,
    TenantSettingsUpdate,
    ConnectionTestResult,
)
from .service import TenantSettingsService

router = APIRouter(prefix="/api/tenant", tags=["Tenant Settings"])

# Service will be injected from main.py
_settings_service: Optional[TenantSettingsService] = None


def set_settings_service(service: TenantSettingsService):
    """Set settings service instance."""
    global _settings_service
    _settings_service = service


def get_settings_service() -> TenantSettingsService:
    """Get settings service."""
    if _settings_service is None:
        raise HTTPException(500, "Settings service not initialized")
    return _settings_service


@router.get("/settings", response_model=TenantSettingsResponse)
async def get_settings(user: UserResponse = Depends(get_current_user)):
    """
    Get tenant settings.
    
    Returns current configuration (without passwords).
    """
    service = get_settings_service()
    return await service.get_settings(user.tenant_id)


@router.put("/settings", response_model=TenantSettingsResponse)
async def update_settings(
    data: TenantSettingsUpdate,
    user: UserResponse = Depends(get_current_user),
):
    """
    Update tenant settings.
    
    Only admin or superadmin can update settings.
    """
    if user.role not in ("admin", "superadmin"):
        raise HTTPException(403, "Only admins can update settings")
    
    service = get_settings_service()
    return await service.update_settings(user.tenant_id, data)


@router.post("/test/email", response_model=ConnectionTestResult)
async def test_email(
    email_type: str = "booking",
    user: UserResponse = Depends(get_current_user),
):
    """
    Test email connection.
    
    Args:
        email_type: "booking" or "stopsale"
    """
    if email_type not in ("booking", "stopsale"):
        raise HTTPException(400, "email_type must be 'booking' or 'stopsale'")
    
    service = get_settings_service()
    return await service.test_email_connection(user.tenant_id, email_type)


@router.post("/test/sedna", response_model=ConnectionTestResult)
async def test_sedna(user: UserResponse = Depends(get_current_user)):
    """Test Sedna API connection."""
    service = get_settings_service()
    return await service.test_sedna_connection(user.tenant_id)
