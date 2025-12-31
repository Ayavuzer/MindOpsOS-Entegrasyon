"""Processing pipeline service - orchestrates fetch → parse → sync."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import asyncpg

from emailfetch.service import TenantEmailService
from emailfetch.parser import EmailParserService
from sedna.service import TenantSednaService


@dataclass
class ProcessingResult:
    """Result of full processing pipeline."""
    
    success: bool
    message: str
    
    # Email fetch stats
    booking_emails_fetched: int = 0
    stopsale_emails_fetched: int = 0
    
    # Parse stats
    reservations_parsed: int = 0
    stop_sales_parsed: int = 0
    
    # Sync stats
    reservations_synced: int = 0
    stop_sales_synced: int = 0
    
    # Errors
    errors: list[str] = field(default_factory=list)
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0


class ProcessingService:
    """Orchestrates the full processing pipeline."""
    
    def __init__(
        self,
        pool: asyncpg.Pool,
        email_service: TenantEmailService,
        sedna_service: TenantSednaService,
    ):
        self.pool = pool
        self.email_service = email_service
        self.sedna_service = sedna_service
        self.parser_service = EmailParserService(pool)
    
    async def run_full_pipeline(self, tenant_id: int) -> ProcessingResult:
        """
        Run full processing pipeline for a tenant:
        1. Fetch booking emails
        2. Fetch stop sale emails
        3. Parse pending emails
        4. Sync pending to Sedna
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            ProcessingResult with all stats
        """
        result = ProcessingResult(
            success=True,
            message="Processing started",
            started_at=datetime.now(),
        )
        
        try:
            # Step 1: Fetch booking emails
            booking_fetch = await self.email_service.fetch_emails(tenant_id, "booking")
            result.booking_emails_fetched = booking_fetch.emails_new
            if not booking_fetch.success and booking_fetch.message != "Booking email not configured":
                result.errors.append(f"Booking fetch: {booking_fetch.message}")
            
            # Step 2: Fetch stop sale emails
            stopsale_fetch = await self.email_service.fetch_emails(tenant_id, "stopsale")
            result.stopsale_emails_fetched = stopsale_fetch.emails_new
            if not stopsale_fetch.success and stopsale_fetch.message != "Stopsale email not configured":
                result.errors.append(f"Stop sale fetch: {stopsale_fetch.message}")
            
            # Step 3: Parse pending emails
            parse_result = await self.parser_service.parse_pending_emails(tenant_id)
            result.reservations_parsed = parse_result["reservations_created"]
            result.stop_sales_parsed = parse_result["stop_sales_created"]
            if parse_result.get("errors"):
                result.errors.extend(parse_result["errors"])
            
            # Step 4: Sync pending to Sedna
            sync_result = await self.sedna_service.sync_pending(tenant_id)
            result.reservations_synced = sync_result["reservations_synced"]
            result.stop_sales_synced = sync_result["stop_sales_synced"]
            if sync_result.get("errors"):
                result.errors.extend(sync_result["errors"])
            
            # Set final message
            total_new = result.booking_emails_fetched + result.stopsale_emails_fetched
            total_parsed = result.reservations_parsed + result.stop_sales_parsed
            total_synced = result.reservations_synced + result.stop_sales_synced
            
            if result.errors:
                result.message = f"Completed with {len(result.errors)} errors"
            else:
                result.message = f"Fetched {total_new} emails, parsed {total_parsed}, synced {total_synced}"
            
        except Exception as e:
            result.success = False
            result.message = str(e)
            result.errors.append(str(e))
        
        result.completed_at = datetime.now()
        
        # Log processing run
        await self._log_processing_run(tenant_id, result)
        
        return result
    
    async def _log_processing_run(self, tenant_id: int, result: ProcessingResult):
        """Log processing run to database."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO pipeline_runs (
                        tenant_id, started_at, completed_at,
                        booking_emails_fetched, stopsale_emails_fetched,
                        reservations_parsed, stop_sales_parsed,
                        reservations_synced, stop_sales_synced,
                        success, message, errors
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
                    )
                    """,
                    tenant_id, result.started_at, result.completed_at,
                    result.booking_emails_fetched, result.stopsale_emails_fetched,
                    result.reservations_parsed, result.stop_sales_parsed,
                    result.reservations_synced, result.stop_sales_synced,
                    result.success, result.message, 
                    ",".join(result.errors) if result.errors else "",  # Convert list to string
                )
        except Exception as e:
            # Log error but don't fail the pipeline
            print(f"Failed to log pipeline run: {e}")
    
    async def get_processing_history(
        self,
        tenant_id: int,
        limit: int = 10,
    ) -> list[dict]:
        """Get recent processing runs for a tenant."""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM pipeline_runs
                    WHERE tenant_id = $1
                    ORDER BY started_at DESC
                    LIMIT $2
                    """,
                    tenant_id, limit,
                )
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"Failed to get history: {e}")
            return []
