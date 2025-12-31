"""Bulk sync service for batch Sedna synchronization with SSE support."""

import uuid
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, AsyncGenerator
import json

import asyncpg

from sedna.service import TenantSednaService, SyncResult
from emailfetch.parser import EmailParserService


@dataclass
class BulkSyncProgress:
    """Progress update for bulk sync operation."""
    
    current: int
    total: int
    email_id: int
    item_type: str  # reservation, stop_sale
    status: str  # success, failed
    sedna_id: Optional[int] = None
    error: Optional[str] = None
    stop_sale_id: Optional[int] = None  # For hotel selection modal
    hotel_name: Optional[str] = None  # For hotel selection modal



@dataclass
class BulkSyncSummary:
    """Final summary of bulk sync operation."""
    
    sync_id: str
    total: int
    successful: int
    failed: int
    duration_seconds: float
    completed_at: datetime


@dataclass
class BulkSyncItem:
    """Item in bulk sync."""
    
    email_id: int
    item_type: str  # reservation, stop_sale, unknown
    reservation_id: Optional[int] = None
    stop_sale_id: Optional[int] = None


class BulkSyncService:
    """Service for bulk synchronization of emails to Sedna."""
    
    def __init__(
        self,
        pool: asyncpg.Pool,
        sedna_service: TenantSednaService,
        parser_service: EmailParserService,
    ):
        self.pool = pool
        self.sedna_service = sedna_service
        self.parser_service = parser_service
        
        # In-memory progress tracking (for SSE)
        self._progress_queues: dict[str, asyncio.Queue] = {}
    
    async def start_bulk_sync(
        self,
        tenant_id: int,
        email_ids: list[int],
    ) -> str:
        """
        Start bulk sync for selected emails.
        
        Args:
            tenant_id: Tenant ID
            email_ids: List of email IDs to sync
            
        Returns:
            sync_id for tracking progress
        """
        sync_id = str(uuid.uuid4())[:8]  # Short UUID
        
        # Create sync run record
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sync_runs (tenant_id, sync_id, status, total_items, started_at)
                VALUES ($1, $2, 'pending', $3, NOW())
                """,
                tenant_id, sync_id, len(email_ids),
            )
            
            # Create sync items
            for email_id in email_ids:
                # Get email type
                row = await conn.fetchrow(
                    "SELECT email_type FROM emails WHERE id = $1 AND tenant_id = $2",
                    email_id, tenant_id,
                )
                email_type = row["email_type"] if row else "unknown"
                
                # Map to item type
                if email_type == "booking":
                    item_type = "reservation"
                elif email_type == "stopsale":
                    item_type = "stop_sale"
                else:
                    item_type = "unknown"
                
                await conn.execute(
                    """
                    INSERT INTO sync_items (sync_run_id, email_id, item_type, status)
                    SELECT id, $2, $3, 'pending'
                    FROM sync_runs WHERE sync_id = $1
                    """,
                    sync_id, email_id, item_type,
                )
        
        # Create progress queue for SSE
        self._progress_queues[sync_id] = asyncio.Queue()
        
        # Start background processing
        asyncio.create_task(self._process_sync(tenant_id, sync_id, email_ids))
        
        return sync_id
    
    async def _process_sync(
        self,
        tenant_id: int,
        sync_id: str,
        email_ids: list[int],
    ):
        """Background task to process sync items."""
        start_time = datetime.now()
        successful = 0
        failed = 0
        
        async with self.pool.acquire() as conn:
            # Update status to running
            await conn.execute(
                "UPDATE sync_runs SET status = 'running' WHERE sync_id = $1",
                sync_id,
            )
        
        queue = self._progress_queues.get(sync_id)
        
        for i, email_id in enumerate(email_ids):
            try:
                # Get email details
                async with self.pool.acquire() as conn:
                    email = await conn.fetchrow(
                        "SELECT * FROM emails WHERE id = $1 AND tenant_id = $2",
                        email_id, tenant_id,
                    )
                
                if not email:
                    # Email not found
                    progress = BulkSyncProgress(
                        current=i + 1,
                        total=len(email_ids),
                        email_id=email_id,
                        item_type="unknown",
                        status="failed",
                        error="Email not found",
                    )
                    failed += 1
                else:
                    # First, ensure email is parsed (creates reservation/stop_sale record)
                    if email["status"] == "pending":
                        parse_result = await self.parser_service.parse_email(email_id, tenant_id)
                        if not parse_result.success:
                            progress = BulkSyncProgress(
                                current=i + 1,
                                total=len(email_ids),
                                email_id=email_id,
                                item_type="unknown",
                                status="failed",
                                error=parse_result.message,
                            )
                            failed += 1
                            if queue:
                                await queue.put(progress)
                            await self._update_sync_item(sync_id, email_id, "failed", None, parse_result.message)
                            await asyncio.sleep(0.1)  # Small delay for SSE
                            continue
                    
                    # Now sync to Sedna based on email type
                    email_type = email["email_type"]
                    
                    if email_type == "booking":
                        # Sync reservation
                        result = await self.sedna_service.sync_reservation(tenant_id, email_id)
                        item_type = "reservation"
                    elif email_type == "stopsale":
                        # Get stop_sale data
                        stop_sale_id_for_modal = None
                        hotel_name_for_modal = None
                        async with self.pool.acquire() as conn:
                            stop_sale = await conn.fetchrow(
                                "SELECT id, hotel_name FROM stop_sales WHERE email_id = $1 AND tenant_id = $2",
                                email_id, tenant_id,
                            )
                        
                        if stop_sale:
                            stop_sale_id_for_modal = stop_sale["id"]
                            hotel_name_for_modal = stop_sale["hotel_name"]
                            result = await self.sedna_service.sync_stop_sale(tenant_id, stop_sale["id"])
                        else:
                            result = SyncResult(success=False, message="Stop sale record not found")
                        item_type = "stop_sale"
                    else:
                        result = SyncResult(success=False, message="Unknown email type - cannot sync")
                        item_type = "unknown"
                    
                    # Create progress update
                    progress = BulkSyncProgress(
                        current=i + 1,
                        total=len(email_ids),
                        email_id=email_id,
                        item_type=item_type,
                        status="success" if result.success else "failed",
                        sedna_id=result.sedna_rec_id,
                        error=None if result.success else result.message,
                        stop_sale_id=stop_sale_id_for_modal if email_type == "stopsale" else None,
                        hotel_name=hotel_name_for_modal if email_type == "stopsale" else None,
                    )
                    
                    if result.success:
                        successful += 1
                    else:
                        failed += 1
                
                # Update sync item in database
                await self._update_sync_item(
                    sync_id, 
                    email_id, 
                    progress.status, 
                    progress.sedna_id, 
                    progress.error,
                )
                
                # Send progress to SSE queue
                if queue:
                    await queue.put(progress)
                
                # Rate limit Sedna API calls
                await asyncio.sleep(0.2)  # 5 requests per second max
                
            except Exception as e:
                progress = BulkSyncProgress(
                    current=i + 1,
                    total=len(email_ids),
                    email_id=email_id,
                    item_type="unknown",
                    status="failed",
                    error=str(e),
                )
                failed += 1
                
                await self._update_sync_item(sync_id, email_id, "failed", None, str(e))
                
                if queue:
                    await queue.put(progress)
        
        # Calculate duration
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Update sync run as completed
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE sync_runs 
                SET status = 'completed', 
                    successful_count = $2, 
                    failed_count = $3,
                    completed_at = NOW()
                WHERE sync_id = $1
                """,
                sync_id, successful, failed,
            )
        
        # Send completion event
        summary = BulkSyncSummary(
            sync_id=sync_id,
            total=len(email_ids),
            successful=successful,
            failed=failed,
            duration_seconds=round(duration, 2),
            completed_at=end_time,
        )
        
        if queue:
            await queue.put(summary)
            await queue.put(None)  # Signal completion
    
    async def _update_sync_item(
        self,
        sync_id: str,
        email_id: int,
        status: str,
        sedna_rec_id: Optional[int],
        error_message: Optional[str],
    ):
        """Update sync item status in database."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE sync_items 
                SET status = $3, sedna_rec_id = $4, error_message = $5, processed_at = NOW()
                WHERE sync_run_id = (SELECT id FROM sync_runs WHERE sync_id = $1)
                AND email_id = $2
                """,
                sync_id, email_id, status, sedna_rec_id, error_message,
            )
    
    async def get_progress_stream(self, sync_id: str) -> AsyncGenerator[str, None]:
        """
        Get SSE stream for sync progress.
        
        Yields:
            SSE data strings
        """
        queue = self._progress_queues.get(sync_id)
        
        if not queue:
            # Check if sync exists but already completed
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM sync_runs WHERE sync_id = $1",
                    sync_id,
                )
                
                if not row:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Sync not found'})}\n\n"
                    return
                
                if row["status"] == "completed":
                    # Send completed event
                    yield f"data: {json.dumps({'type': 'complete', 'summary': {'total': row['total_items'], 'successful': row['successful_count'], 'failed': row['failed_count']}})}\n\n"
                    return
            
            # Wait for queue to be created
            for _ in range(50):  # 5 seconds timeout
                await asyncio.sleep(0.1)
                queue = self._progress_queues.get(sync_id)
                if queue:
                    break
            
            if not queue:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Sync queue timeout'})}\n\n"
                return
        
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=30)
                
                if item is None:
                    # Completed
                    break
                
                if isinstance(item, BulkSyncSummary):
                    yield f"data: {json.dumps({'type': 'complete', 'summary': {'sync_id': item.sync_id, 'total': item.total, 'successful': item.successful, 'failed': item.failed, 'duration_seconds': item.duration_seconds}})}\n\n"
                elif isinstance(item, BulkSyncProgress):
                    yield f"data: {json.dumps({'type': 'progress', 'current': item.current, 'total': item.total, 'item': {'email_id': item.email_id, 'type': item.item_type, 'status': item.status, 'sedna_id': item.sedna_id, 'error': item.error, 'stop_sale_id': item.stop_sale_id, 'hotel_name': item.hotel_name}})}\n\n"
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        
        # Cleanup queue
        if sync_id in self._progress_queues:
            del self._progress_queues[sync_id]
    
    async def get_sync_result(self, sync_id: str, tenant_id: int) -> Optional[dict]:
        """Get final sync results."""
        async with self.pool.acquire() as conn:
            run = await conn.fetchrow(
                "SELECT * FROM sync_runs WHERE sync_id = $1 AND tenant_id = $2",
                sync_id, tenant_id,
            )
            
            if not run:
                return None
            
            # Get items
            items = await conn.fetch(
                """
                SELECT si.*, e.subject
                FROM sync_items si
                JOIN emails e ON si.email_id = e.id
                WHERE si.sync_run_id = $1
                """,
                run["id"],
            )
            
            successful = []
            failed = []
            
            for item in items:
                item_data = {
                    "email_id": item["email_id"],
                    "subject": item["subject"],
                    "type": item["item_type"],
                }
                
                if item["status"] == "success":
                    item_data["sedna_id"] = item["sedna_rec_id"]
                    successful.append(item_data)
                else:
                    item_data["error"] = item["error_message"]
                    failed.append(item_data)
            
            duration = 0
            if run["completed_at"] and run["started_at"]:
                duration = (run["completed_at"] - run["started_at"]).total_seconds()
            
            return {
                "sync_id": sync_id,
                "status": run["status"],
                "summary": {
                    "total": run["total_items"],
                    "successful": run["successful_count"],
                    "failed": run["failed_count"],
                    "duration_seconds": round(duration, 2),
                },
                "successful": successful,
                "failed": failed,
            }
    
    async def get_sync_history(self, tenant_id: int, limit: int = 20) -> list[dict]:
        """Get recent sync runs for tenant."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT sync_id, status, total_items, successful_count, 
                       failed_count, started_at, completed_at
                FROM sync_runs
                WHERE tenant_id = $1
                ORDER BY started_at DESC
                LIMIT $2
                """,
                tenant_id, limit,
            )
            
            return [
                {
                    "sync_id": row["sync_id"],
                    "status": row["status"],
                    "total": row["total_items"],
                    "successful": row["successful_count"],
                    "failed": row["failed_count"],
                    "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                    "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
                }
                for row in rows
            ]
    
    async def get_sync_info(self, sync_id: str) -> Optional[dict]:
        """Get sync metadata including tenant_id (for auth-free endpoints)."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT sync_id, tenant_id, status FROM sync_runs WHERE sync_id = $1",
                sync_id,
            )
            
            if not row:
                return None
            
            return {
                "sync_id": row["sync_id"],
                "tenant_id": row["tenant_id"],
                "status": row["status"],
            }


# Module-level service instance
_bulk_sync_service: Optional[BulkSyncService] = None


def set_bulk_sync_service(service: BulkSyncService):
    """Set the bulk sync service instance."""
    global _bulk_sync_service
    _bulk_sync_service = service


def get_bulk_sync_service() -> BulkSyncService:
    """Get the bulk sync service instance."""
    if not _bulk_sync_service:
        raise RuntimeError("Bulk sync service not initialized")
    return _bulk_sync_service
