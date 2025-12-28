"""Sedna sync API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, UserResponse
from .service import TenantSednaService

router = APIRouter(prefix="/api/sedna", tags=["Sedna Sync"])

# Service will be injected from main.py
_sedna_service: Optional[TenantSednaService] = None


def set_sedna_service(service: TenantSednaService):
    """Set sedna service instance."""
    global _sedna_service
    _sedna_service = service


def get_sedna_service() -> TenantSednaService:
    """Get sedna service."""
    if _sedna_service is None:
        raise HTTPException(500, "Sedna service not initialized")
    return _sedna_service


class SyncResponse(BaseModel):
    """Sync response model."""
    
    success: bool
    message: str
    sedna_rec_id: Optional[int] = None
    details: dict = {}


class SyncPendingResponse(BaseModel):
    """Sync pending response model."""
    
    reservations_synced: int = 0
    reservations_failed: int = 0
    stop_sales_synced: int = 0
    stop_sales_failed: int = 0
    errors: list[str] = []


@router.post("/sync/reservation/{email_id}", response_model=SyncResponse)
async def sync_reservation(
    email_id: int,
    user: UserResponse = Depends(get_current_user),
):
    """Sync a reservation (by source email ID) to Sedna."""
    service = get_sedna_service()
    result = await service.sync_reservation(user.tenant_id, email_id)
    
    return SyncResponse(
        success=result.success,
        message=result.message,
        sedna_rec_id=result.sedna_rec_id,
        details=result.details,
    )


@router.post("/sync/stop-sale/{stop_sale_id}", response_model=SyncResponse)
async def sync_stop_sale(
    stop_sale_id: int,
    user: UserResponse = Depends(get_current_user),
):
    """Sync a stop sale to Sedna."""
    service = get_sedna_service()
    result = await service.sync_stop_sale(user.tenant_id, stop_sale_id)
    
    return SyncResponse(
        success=result.success,
        message=result.message,
        sedna_rec_id=result.sedna_rec_id,
        details=result.details,
    )


@router.post("/sync/pending", response_model=SyncPendingResponse)
async def sync_all_pending(
    user: UserResponse = Depends(get_current_user),
):
    """Sync all pending reservations and stop sales to Sedna."""
    service = get_sedna_service()
    results = await service.sync_pending(user.tenant_id)
    
    return SyncPendingResponse(**results)
