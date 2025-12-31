"""IMAP IDLE API routes for real-time email monitoring."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
from auth.models import UserResponse
from .tenant_imap_service import get_tenant_imap_service


router = APIRouter(prefix="/api/email/idle", tags=["email-idle"])


class IdleStartRequest(BaseModel):
    """Request to start IMAP IDLE."""
    email_type: str  # "booking" or "stopsale"


class IdleStatusResponse(BaseModel):
    """IMAP IDLE connection status."""
    email_type: str
    status: str | None
    message: str


@router.post("/start")
async def start_idle(
    request: IdleStartRequest,
    user: UserResponse = Depends(get_current_user),
):
    """
    Start IMAP IDLE for a specific email type.
    
    This enables real-time email notifications instead of polling.
    """
    service = get_tenant_imap_service()
    if not service:
        raise HTTPException(status_code=503, detail="IMAP IDLE service not available")
    
    if request.email_type not in ["booking", "stopsale"]:
        raise HTTPException(status_code=400, detail="email_type must be 'booking' or 'stopsale'")
    
    success = await service.start_tenant_idle(
        tenant_id=user.tenant_id,
        email_type=request.email_type,
    )
    
    return {
        "success": success,
        "message": f"IMAP IDLE {'started' if success else 'failed to start'} for {request.email_type}",
        "status": service.get_status(user.tenant_id, request.email_type),
    }


@router.post("/stop")
async def stop_idle(
    request: IdleStartRequest,
    user: UserResponse = Depends(get_current_user),
):
    """
    Stop IMAP IDLE for a specific email type.
    """
    service = get_tenant_imap_service()
    if not service:
        raise HTTPException(status_code=503, detail="IMAP IDLE service not available")
    
    if request.email_type not in ["booking", "stopsale"]:
        raise HTTPException(status_code=400, detail="email_type must be 'booking' or 'stopsale'")
    
    await service.stop_tenant_idle(
        tenant_id=user.tenant_id,
        email_type=request.email_type,
    )
    
    return {
        "success": True,
        "message": f"IMAP IDLE stopped for {request.email_type}",
    }


@router.get("/status/{email_type}", response_model=IdleStatusResponse)
async def get_idle_status(
    email_type: str,
    user: UserResponse = Depends(get_current_user),
):
    """
    Get IMAP IDLE connection status for a specific email type.
    """
    service = get_tenant_imap_service()
    if not service:
        return IdleStatusResponse(
            email_type=email_type,
            status=None,
            message="IMAP IDLE service not available",
        )
    
    if email_type not in ["booking", "stopsale"]:
        raise HTTPException(status_code=400, detail="email_type must be 'booking' or 'stopsale'")
    
    status = service.get_status(user.tenant_id, email_type)
    
    return IdleStatusResponse(
        email_type=email_type,
        status=status,
        message=f"Connection is {status}" if status else "No active IMAP IDLE connection",
    )


@router.get("/status")
async def get_all_idle_status(
    user: UserResponse = Depends(get_current_user),
):
    """
    Get IMAP IDLE connection status for all email types.
    """
    service = get_tenant_imap_service()
    if not service:
        return {
            "booking": None,
            "stopsale": None,
            "message": "IMAP IDLE service not available",
        }
    
    booking_status = service.get_status(user.tenant_id, "booking")
    stopsale_status = service.get_status(user.tenant_id, "stopsale")
    
    return {
        "booking": booking_status,
        "stopsale": stopsale_status,
        "active_connections": sum(1 for s in [booking_status, stopsale_status] if s),
    }


# Admin endpoint for system-wide status
@router.get("/admin/all")
async def get_all_connections(
    user: UserResponse = Depends(get_current_user),
):
    """
    Get all IMAP IDLE connections (admin only).
    
    Note: Should add admin role check in production.
    """
    service = get_tenant_imap_service()
    if not service:
        return {"connections": {}, "message": "IMAP IDLE service not available"}
    
    return {
        "connections": service.get_all_statuses(),
        "total": len(service.get_all_statuses()),
    }


# =============================================================================
# Email Health Dashboard
# =============================================================================

@router.get("/health")
async def get_email_health(
    user: UserResponse = Depends(get_current_user),
):
    """
    Get complete email health status for the tenant.
    
    Returns health status for booking and stopsale email configurations,
    including OAuth status, IMAP IDLE status, and processing statistics.
    """
    from .health_service import get_email_health_service
    
    service = get_email_health_service()
    if not service:
        raise HTTPException(status_code=503, detail="Email health service not available")
    
    return await service.get_tenant_health(user.tenant_id)


@router.get("/health/summary")
async def get_email_health_summary(
    user: UserResponse = Depends(get_current_user),
):
    """
    Get simplified email health summary.
    
    Returns a quick overview suitable for dashboard widgets.
    """
    from .health_service import get_email_health_service
    
    service = get_email_health_service()
    if not service:
        return {
            "status": "unknown",
            "message": "Email health service not available",
        }
    
    health = await service.get_tenant_health(user.tenant_id)
    
    # Count active connections
    active = 0
    if health.booking.imap_idle.active:
        active += 1
    if health.stopsale.imap_idle.active:
        active += 1
    
    # Count OAuth issues
    oauth_issues = 0
    if health.booking.configured and health.booking.auth_method == "oauth2":
        if health.booking.oauth.is_expired or not health.booking.oauth.connected:
            oauth_issues += 1
    if health.stopsale.configured and health.stopsale.auth_method == "oauth2":
        if health.stopsale.oauth.is_expired or not health.stopsale.oauth.connected:
            oauth_issues += 1
    
    # Total errors
    total_errors = health.booking.errors_today + health.stopsale.errors_today
    
    # Status icon
    if health.overall_health == "healthy":
        icon = "✅"
    elif health.overall_health == "warning":
        icon = "⚠️"
    else:
        icon = "❌"
    
    return {
        "status": health.overall_health,
        "icon": icon,
        "booking_score": health.booking.health_score if health.booking.configured else None,
        "stopsale_score": health.stopsale.health_score if health.stopsale.configured else None,
        "active_idle_connections": active,
        "oauth_issues": oauth_issues,
        "errors_today": total_errors,
        "checked_at": health.checked_at,
    }
