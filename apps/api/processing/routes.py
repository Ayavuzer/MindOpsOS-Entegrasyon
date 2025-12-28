"""Processing pipeline API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, UserResponse
from .service import ProcessingService

router = APIRouter(prefix="/api/processing", tags=["Processing"])

# Service will be injected from main.py
_processing_service: Optional[ProcessingService] = None


def set_processing_service(service: ProcessingService):
    """Set processing service instance."""
    global _processing_service
    _processing_service = service


def get_processing_service() -> ProcessingService:
    """Get processing service."""
    if _processing_service is None:
        raise HTTPException(500, "Processing service not initialized")
    return _processing_service


class ProcessingResponse(BaseModel):
    """Processing response model."""
    
    success: bool
    message: str
    booking_emails_fetched: int = 0
    stopsale_emails_fetched: int = 0
    reservations_parsed: int = 0
    stop_sales_parsed: int = 0
    reservations_synced: int = 0
    stop_sales_synced: int = 0
    errors: list[str] = []
    duration_seconds: float = 0


@router.post("/run", response_model=ProcessingResponse)
async def run_processing(
    user: UserResponse = Depends(get_current_user),
):
    """
    Run full processing pipeline:
    1. Fetch booking emails
    2. Fetch stop sale emails  
    3. Sync pending items to Sedna
    
    Returns detailed stats on what was processed.
    """
    service = get_processing_service()
    result = await service.run_full_pipeline(user.tenant_id)
    
    return ProcessingResponse(
        success=result.success,
        message=result.message,
        booking_emails_fetched=result.booking_emails_fetched,
        stopsale_emails_fetched=result.stopsale_emails_fetched,
        reservations_parsed=result.reservations_parsed,
        stop_sales_parsed=result.stop_sales_parsed,
        reservations_synced=result.reservations_synced,
        stop_sales_synced=result.stop_sales_synced,
        errors=result.errors,
        duration_seconds=result.duration_seconds,
    )


@router.get("/history")
async def get_processing_history(
    limit: int = 10,
    user: UserResponse = Depends(get_current_user),
):
    """Get recent processing runs for current tenant."""
    service = get_processing_service()
    return await service.get_processing_history(user.tenant_id, limit)
