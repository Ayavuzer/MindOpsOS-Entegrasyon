"""Background job for OAuth token refresh."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import asyncpg

from .service import OAuthService

logger = logging.getLogger(__name__)


class TokenRefreshJob:
    """Background job that monitors and refreshes OAuth tokens before expiry."""
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.service = OAuthService(pool)
        self.running = False
        self._task: Optional[asyncio.Task] = None
        
        # Configuration
        self.check_interval_seconds = 300  # Check every 5 minutes
        self.refresh_before_expiry_minutes = 10  # Refresh 10 min before expiry
    
    async def start(self) -> None:
        """Start the background refresh job."""
        if self.running:
            logger.warning("Token refresh job already running")
            return
        
        self.running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("✅ Token refresh job started")
    
    async def stop(self) -> None:
        """Stop the background refresh job."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("👋 Token refresh job stopped")
    
    async def _run_loop(self) -> None:
        """Main loop that periodically checks for tokens needing refresh."""
        while self.running:
            try:
                await self._check_and_refresh_tokens()
            except Exception as e:
                logger.error(f"Token refresh job error: {e}")
            
            # Wait for next check
            await asyncio.sleep(self.check_interval_seconds)
    
    async def _check_and_refresh_tokens(self) -> None:
        """Find tokens expiring soon and refresh them."""
        
        # Calculate threshold time (timezone-aware)
        threshold = datetime.now(timezone.utc) + timedelta(minutes=self.refresh_before_expiry_minutes)
        
        async with self.pool.acquire() as conn:
            # Find tenants with tokens expiring soon
            rows = await conn.fetch(
                """
                SELECT tenant_id,
                       booking_oauth_token_expiry,
                       stopsale_oauth_token_expiry
                FROM tenant_settings
                WHERE (
                    booking_auth_method = 'oauth2' 
                    AND booking_oauth_token_expiry IS NOT NULL
                    AND booking_oauth_token_expiry <= $1
                ) OR (
                    stopsale_auth_method = 'oauth2'
                    AND stopsale_oauth_token_expiry IS NOT NULL
                    AND stopsale_oauth_token_expiry <= $1
                )
                """,
                threshold,
            )
        
        if not rows:
            return
        
        logger.info(f"Found {len(rows)} tenant(s) with tokens expiring soon")
        
        for row in rows:
            tenant_id = row["tenant_id"]
            
            # Check and refresh booking token
            if row["booking_oauth_token_expiry"] and row["booking_oauth_token_expiry"] <= threshold:
                success = await self._refresh_token_safe(tenant_id, "booking")
                if success:
                    logger.info(f"Refreshed booking token for tenant {tenant_id}")
                else:
                    logger.warning(f"Failed to refresh booking token for tenant {tenant_id}")
            
            # Check and refresh stopsale token
            if row["stopsale_oauth_token_expiry"] and row["stopsale_oauth_token_expiry"] <= threshold:
                success = await self._refresh_token_safe(tenant_id, "stopsale")
                if success:
                    logger.info(f"Refreshed stopsale token for tenant {tenant_id}")
                else:
                    logger.warning(f"Failed to refresh stopsale token for tenant {tenant_id}")
    
    async def _refresh_token_safe(self, tenant_id: int, email_type: str) -> bool:
        """Safely refresh a token with error handling."""
        try:
            return await self.service.refresh_google_token(tenant_id, email_type)
        except Exception as e:
            logger.error(f"Token refresh error for tenant {tenant_id} ({email_type}): {e}")
            return False
    
    async def get_status(self) -> dict:
        """Get current status of the token refresh job."""
        
        # Count tokens by status
        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) FILTER (WHERE booking_auth_method = 'oauth2') as booking_oauth_count,
                    COUNT(*) FILTER (WHERE stopsale_auth_method = 'oauth2') as stopsale_oauth_count,
                    COUNT(*) FILTER (
                        WHERE booking_auth_method = 'oauth2' 
                        AND booking_oauth_token_expiry <= NOW() + INTERVAL '10 minutes'
                    ) as booking_expiring_soon,
                    COUNT(*) FILTER (
                        WHERE stopsale_auth_method = 'oauth2' 
                        AND stopsale_oauth_token_expiry <= NOW() + INTERVAL '10 minutes'
                    ) as stopsale_expiring_soon,
                    COUNT(*) FILTER (
                        WHERE booking_auth_method = 'oauth2' 
                        AND booking_oauth_token_expiry <= NOW()
                    ) as booking_expired,
                    COUNT(*) FILTER (
                        WHERE stopsale_auth_method = 'oauth2' 
                        AND stopsale_oauth_token_expiry <= NOW()
                    ) as stopsale_expired
                FROM tenant_settings
                """
            )
        
        return {
            "running": self.running,
            "check_interval_seconds": self.check_interval_seconds,
            "refresh_before_expiry_minutes": self.refresh_before_expiry_minutes,
            "stats": {
                "booking_oauth_count": stats["booking_oauth_count"] or 0,
                "stopsale_oauth_count": stats["stopsale_oauth_count"] or 0,
                "booking_expiring_soon": stats["booking_expiring_soon"] or 0,
                "stopsale_expiring_soon": stats["stopsale_expiring_soon"] or 0,
                "booking_expired": stats["booking_expired"] or 0,
                "stopsale_expired": stats["stopsale_expired"] or 0,
            },
        }


# Global instance
_token_refresh_job: Optional[TokenRefreshJob] = None


def get_token_refresh_job() -> Optional[TokenRefreshJob]:
    """Get the global token refresh job instance."""
    return _token_refresh_job


def set_token_refresh_job(job: TokenRefreshJob) -> None:
    """Set the global token refresh job instance."""
    global _token_refresh_job
    _token_refresh_job = job
