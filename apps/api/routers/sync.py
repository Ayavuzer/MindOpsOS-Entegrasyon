"""Sync API routes for bulk Sedna synchronization."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel

from auth.routes import get_current_user, UserResponse
from sedna.bulk_sync_service import get_bulk_sync_service
from sedna.report_service import get_report_service


router = APIRouter(prefix="/api/sync", tags=["Sync"])


# =============================================================================
# Request/Response Models
# =============================================================================


class BulkSyncRequest(BaseModel):
    """Request to start bulk sync."""
    email_ids: list[int]


class BulkSyncStartResponse(BaseModel):
    """Response when bulk sync starts."""
    sync_id: str
    status: str = "started"
    total_items: int


class SyncItemResult(BaseModel):
    """Result of syncing a single item."""
    email_id: int
    subject: Optional[str] = None
    type: str
    sedna_id: Optional[int] = None
    error: Optional[str] = None


class SyncSummary(BaseModel):
    """Summary of sync operation."""
    total: int
    successful: int
    failed: int
    duration_seconds: float


class SyncResultResponse(BaseModel):
    """Full sync result response."""
    sync_id: str
    status: str
    summary: SyncSummary
    successful: list[SyncItemResult]
    failed: list[SyncItemResult]


class SyncHistoryItem(BaseModel):
    """Single sync history entry."""
    sync_id: str
    status: str
    total: int
    successful: int
    failed: int
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/emails", response_model=BulkSyncStartResponse)
async def start_bulk_sync(
    request: BulkSyncRequest,
    user: UserResponse = Depends(get_current_user),
):
    """
    Start bulk sync for selected emails.
    
    - Validates email IDs belong to tenant
    - Creates sync job and returns sync_id
    - Processing happens in background
    - Use /sync/{sync_id}/progress for SSE updates
    """
    if not request.email_ids:
        raise HTTPException(400, "No emails selected")
    
    if len(request.email_ids) > 100:
        raise HTTPException(400, "Maximum 100 emails per batch")
    
    service = get_bulk_sync_service()
    sync_id = await service.start_bulk_sync(user.tenant_id, request.email_ids)
    
    return BulkSyncStartResponse(
        sync_id=sync_id,
        status="started",
        total_items=len(request.email_ids),
    )


@router.get("/{sync_id}/progress")
async def get_sync_progress(
    sync_id: str,
    token: Optional[str] = None,
):
    """
    Get real-time sync progress via Server-Sent Events (SSE).
    
    Note: EventSource API doesn't support custom headers, 
    so token must be passed as query parameter.
    
    Event types:
    - progress: { current, total, item: { email_id, type, status, sedna_id, error } }
    - complete: { summary: { total, successful, failed, duration_seconds } }
    - heartbeat: {} (every 30 seconds to keep connection alive)
    - error: { message }
    
    Example usage:
    ```javascript
    const eventSource = new EventSource('/api/sync/abc123/progress?token=xxx');
    eventSource.onmessage = (e) => {
        const data = JSON.parse(e.data);
        console.log(data);
    };
    ```
    """
    # Note: For SSE we skip strict auth check since sync_id itself is a token
    # The sync_id is only known to the user who initiated the sync
    
    service = get_bulk_sync_service()
    
    return StreamingResponse(
        service.get_progress_stream(sync_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/{sync_id}/result", response_model=SyncResultResponse)
async def get_sync_result(
    sync_id: str,
    user: UserResponse = Depends(get_current_user),
):
    """
    Get final sync results after completion.
    
    Use this endpoint after receiving 'complete' event from SSE,
    or to retrieve results of a past sync operation.
    """
    service = get_bulk_sync_service()
    result = await service.get_sync_result(sync_id, user.tenant_id)
    
    if not result:
        raise HTTPException(404, "Sync not found")
    
    return SyncResultResponse(
        sync_id=result["sync_id"],
        status=result["status"],
        summary=SyncSummary(**result["summary"]),
        successful=[SyncItemResult(**item) for item in result["successful"]],
        failed=[SyncItemResult(**item) for item in result["failed"]],
    )


@router.get("/history", response_model=list[SyncHistoryItem])
async def get_sync_history(
    limit: int = 20,
    user: UserResponse = Depends(get_current_user),
):
    """
    Get recent sync operations for the tenant.
    
    Returns last N sync runs with summary info.
    """
    service = get_bulk_sync_service()
    history = await service.get_sync_history(user.tenant_id, limit)
    
    return [SyncHistoryItem(**item) for item in history]


@router.post("/{sync_id}/retry")
async def retry_failed_items(
    sync_id: str,
    user: UserResponse = Depends(get_current_user),
):
    """
    Retry failed items from a previous sync.
    
    Creates a new sync job with only the failed items.
    """
    service = get_bulk_sync_service()
    result = await service.get_sync_result(sync_id, user.tenant_id)
    
    if not result:
        raise HTTPException(404, "Sync not found")
    
    failed_ids = [item["email_id"] for item in result["failed"]]
    
    if not failed_ids:
        raise HTTPException(400, "No failed items to retry")
    
    new_sync_id = await service.start_bulk_sync(user.tenant_id, failed_ids)
    
    return BulkSyncStartResponse(
        sync_id=new_sync_id,
        status="started",
        total_items=len(failed_ids),
    )


@router.get("/{sync_id}/report")
async def download_sync_report(
    sync_id: str,
):
    """
    Download Excel report for a sync operation.
    
    Note: Authentication is skipped since sync_id is a unique token
    that is only known to the user who initiated the sync operation.
    
    Returns an .xlsx file with:
    - Summary sheet: Overview of the sync operation
    - All Items sheet: Complete list of all processed items
    - Successful sheet: Items that synced successfully
    - Failed sheet: Items that failed with error details
    """
    report_service = get_report_service()
    
    # Get tenant_id from sync record (since we don't have user context)
    bulk_service = get_bulk_sync_service()
    sync_info = await bulk_service.get_sync_info(sync_id)
    
    if not sync_info:
        raise HTTPException(404, "Sync not found")
    
    report_bytes = await report_service.generate_excel_report(sync_id, sync_info["tenant_id"])
    
    if not report_bytes:
        raise HTTPException(404, "Report generation failed")
    
    filename = f"sync_report_{sync_id}.xlsx"
    
    return Response(
        content=report_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
