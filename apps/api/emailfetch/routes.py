"""Email fetch API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, UserResponse
from .service import TenantEmailService, FetchResult

router = APIRouter(prefix="/api/email", tags=["Email"])

# Service will be injected from main.py
_email_service: Optional[TenantEmailService] = None


def set_email_service(service: TenantEmailService):
    """Set email service instance."""
    global _email_service
    _email_service = service


def get_email_service() -> TenantEmailService:
    """Get email service."""
    if _email_service is None:
        raise HTTPException(500, "Email service not initialized")
    return _email_service


class FetchResponse(BaseModel):
    """Fetch response model."""
    
    success: bool
    message: str
    emails_fetched: int = 0
    emails_new: int = 0
    emails_skipped: int = 0
    errors: list[str] = []


@router.post("/fetch", response_model=FetchResponse)
async def fetch_emails(
    email_type: str = "booking",
    user: UserResponse = Depends(get_current_user),
):
    """
    Fetch emails from tenant's configured POP3 server.
    
    Args:
        email_type: "booking" or "stopsale"
    """
    if email_type not in ("booking", "stopsale"):
        raise HTTPException(400, "email_type must be 'booking' or 'stopsale'")
    
    service = get_email_service()
    result = await service.fetch_emails(user.tenant_id, email_type)
    
    return FetchResponse(
        success=result.success,
        message=result.message,
        emails_fetched=result.emails_fetched,
        emails_new=result.emails_new,
        emails_skipped=result.emails_skipped,
        errors=result.errors,
    )


@router.post("/fetch/all", response_model=dict)
async def fetch_all_emails(
    user: UserResponse = Depends(get_current_user),
):
    """
    Fetch emails from both booking and stopsale mailboxes.
    """
    service = get_email_service()
    
    booking_result = await service.fetch_emails(user.tenant_id, "booking")
    stopsale_result = await service.fetch_emails(user.tenant_id, "stopsale")
    
    return {
        "booking": {
            "success": booking_result.success,
            "message": booking_result.message,
            "emails_new": booking_result.emails_new,
        },
        "stopsale": {
            "success": stopsale_result.success,
            "message": stopsale_result.message,
            "emails_new": stopsale_result.emails_new,
        },
        "total_new": booking_result.emails_new + stopsale_result.emails_new,
    }
