"""Email health monitoring service and API."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel

import asyncpg

from oauth.service import OAuthService
from imap_idle import get_imap_manager, ConnectionState
from tenant.encryption import decrypt_value

logger = logging.getLogger(__name__)


class OAuthHealthStatus(BaseModel):
    """OAuth connection health status."""
    connected: bool
    provider: Optional[str] = None
    email: Optional[str] = None
    token_expiry: Optional[datetime] = None
    expires_in_minutes: Optional[int] = None
    is_expiring_soon: bool = False  # <10 min
    is_expired: bool = False


class IMAPIdleStatus(BaseModel):
    """IMAP IDLE connection status."""
    active: bool
    state: Optional[str] = None
    last_error: Optional[str] = None


class EmailHealthStatus(BaseModel):
    """Complete email health status for one email type."""
    email_type: str  # "booking" or "stopsale"
    configured: bool
    email_address: Optional[str] = None
    auth_method: str = "password"
    oauth: OAuthHealthStatus
    imap_idle: IMAPIdleStatus
    last_email_check: Optional[datetime] = None
    emails_processed_today: int = 0
    errors_today: int = 0
    health_score: int = 100  # 0-100


class TenantEmailHealth(BaseModel):
    """Complete tenant email health."""
    tenant_id: int
    checked_at: datetime
    booking: EmailHealthStatus
    stopsale: EmailHealthStatus
    overall_health: str  # "healthy", "warning", "critical"


class EmailHealthService:
    """Service for email health monitoring."""
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self._oauth_service = OAuthService(pool)
        self._imap_manager = get_imap_manager()
    
    async def get_tenant_health(self, tenant_id: int) -> TenantEmailHealth:
        """Get complete email health for a tenant."""
        
        booking_health = await self._get_email_health(tenant_id, "booking")
        stopsale_health = await self._get_email_health(tenant_id, "stopsale")
        
        # Calculate overall health
        scores = []
        if booking_health.configured:
            scores.append(booking_health.health_score)
        if stopsale_health.configured:
            scores.append(stopsale_health.health_score)
        
        avg_score = sum(scores) / len(scores) if scores else 100
        
        if avg_score >= 80:
            overall = "healthy"
        elif avg_score >= 50:
            overall = "warning"
        else:
            overall = "critical"
        
        return TenantEmailHealth(
            tenant_id=tenant_id,
            checked_at=datetime.utcnow(),
            booking=booking_health,
            stopsale=stopsale_health,
            overall_health=overall,
        )
    
    async def _get_email_health(
        self,
        tenant_id: int,
        email_type: str,
    ) -> EmailHealthStatus:
        """Get health status for a specific email type."""
        
        prefix = email_type
        oauth_prefix = f"{email_type}_oauth"
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT 
                    {prefix}_email_host,
                    {prefix}_email_address,
                    {prefix}_auth_method,
                    {oauth_prefix}_provider,
                    {oauth_prefix}_connected_email,
                    {oauth_prefix}_token_expiry
                FROM tenant_settings
                WHERE tenant_id = $1
                """,
                tenant_id,
            )
        
        if not row or not row[f"{prefix}_email_host"]:
            # Not configured
            return EmailHealthStatus(
                email_type=email_type,
                configured=False,
                oauth=OAuthHealthStatus(connected=False),
                imap_idle=IMAPIdleStatus(active=False),
            )
        
        # OAuth status
        oauth_provider = row[f"{oauth_prefix}_provider"]
        oauth_email = row[f"{oauth_prefix}_connected_email"]
        token_expiry = row[f"{oauth_prefix}_token_expiry"]
        
        oauth_connected = bool(oauth_provider and oauth_email)
        is_expiring_soon = False
        is_expired = False
        expires_in_minutes = None
        
        if token_expiry:
            now = datetime.utcnow()
            # Make sure we compare naive datetimes
            if token_expiry.tzinfo is not None:
                token_expiry_naive = token_expiry.replace(tzinfo=None)
            else:
                token_expiry_naive = token_expiry
            expires_in = token_expiry_naive - now
            expires_in_minutes = int(expires_in.total_seconds() / 60)
            is_expiring_soon = expires_in_minutes < 10
            is_expired = expires_in_minutes < 0
        
        oauth_health = OAuthHealthStatus(
            connected=oauth_connected,
            provider=oauth_provider,
            email=oauth_email,
            token_expiry=token_expiry,
            expires_in_minutes=expires_in_minutes,
            is_expiring_soon=is_expiring_soon,
            is_expired=is_expired,
        )
        
        # IMAP IDLE status
        imap_state = self._imap_manager.get_status(tenant_id, email_type)
        imap_active = imap_state in [ConnectionState.IDLE, ConnectionState.AUTHENTICATED] if imap_state else False
        
        imap_health = IMAPIdleStatus(
            active=imap_active,
            state=imap_state.value if imap_state else None,
        )
        
        # Get email processing stats (last 24 hours)
        # Note: email_logs table may not exist yet
        emails_processed = 0
        errors_today = 0
        last_check = None
        
        try:
            async with self.pool.acquire() as conn:
                # Check if email_logs table exists first
                table_exists = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'email_logs'
                    )
                    """
                )
                
                if table_exists:
                    stats = await conn.fetchrow(
                        """
                        SELECT 
                            COUNT(*) FILTER (WHERE status = 'processed') as processed,
                            COUNT(*) FILTER (WHERE status = 'error') as errors,
                            MAX(processed_at) as last_check
                        FROM email_logs
                        WHERE tenant_id = $1 
                          AND email_type = $2
                          AND created_at > NOW() - INTERVAL '24 hours'
                        """,
                        tenant_id,
                        email_type,
                    )
                    
                    if stats:
                        emails_processed = stats["processed"] or 0
                        errors_today = stats["errors"] or 0
                        last_check = stats["last_check"]
        except Exception as e:
            logger.warning(f"Failed to get email stats: {e}")
        
        # Calculate health score
        health_score = 100
        
        auth_method = row[f"{prefix}_auth_method"] or "password"
        
        if auth_method == "oauth2":
            if not oauth_connected:
                health_score -= 50
            elif is_expired:
                health_score -= 40
            elif is_expiring_soon:
                health_score -= 20
        
        if not imap_active:
            health_score -= 10
        
        if errors_today > 0:
            health_score -= min(30, errors_today * 5)
        
        health_score = max(0, health_score)
        
        return EmailHealthStatus(
            email_type=email_type,
            configured=True,
            email_address=row[f"{prefix}_email_address"],
            auth_method=auth_method,
            oauth=oauth_health,
            imap_idle=imap_health,
            last_email_check=last_check,
            emails_processed_today=emails_processed,
            errors_today=errors_today,
            health_score=health_score,
        )


# Global service instance
_email_health_service: Optional[EmailHealthService] = None


def get_email_health_service() -> Optional[EmailHealthService]:
    """Get global email health service."""
    return _email_health_service


def set_email_health_service(service: EmailHealthService) -> None:
    """Set global email health service."""
    global _email_health_service
    _email_health_service = service
