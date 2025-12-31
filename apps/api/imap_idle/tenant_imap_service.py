"""IMAP IDLE service for tenant email real-time notifications."""

import asyncio
import logging
from typing import Optional, Callable, Any

import asyncpg

from .imap_idle import (
    IMAPConfig,
    IMAPConnectionManager,
    EmailNotification,
    AuthMethod,
    get_imap_manager,
)
from oauth.service import OAuthService
from tenant.encryption import decrypt_value

logger = logging.getLogger(__name__)


class TenantIMAPService:
    """Service for managing IMAP IDLE connections for tenants."""
    
    def __init__(
        self,
        pool: asyncpg.Pool,
        on_new_email: Optional[Callable[[int, str, EmailNotification], Any]] = None,
    ):
        self.pool = pool
        self.on_new_email = on_new_email  # (tenant_id, email_type, notification)
        self._oauth_service = OAuthService(pool)
        self._manager = get_imap_manager()
    
    async def start_tenant_idle(
        self,
        tenant_id: int,
        email_type: str,  # "booking" or "stopsale"
    ) -> bool:
        """Start IMAP IDLE for a tenant's email configuration."""
        
        # Get tenant settings
        config = await self._get_imap_config(tenant_id, email_type)
        if not config:
            logger.warning(f"No IMAP config for tenant {tenant_id} ({email_type})")
            return False
        
        # Create callback wrapper
        async def on_email(notification: EmailNotification):
            if self.on_new_email:
                try:
                    result = self.on_new_email(tenant_id, email_type, notification)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"Email callback error: {e}")
        
        # Start IDLE
        return await self._manager.start_connection(
            tenant_id=tenant_id,
            email_type=email_type,
            config=config,
            on_new_email=on_email,
        )
    
    async def stop_tenant_idle(self, tenant_id: int, email_type: str) -> None:
        """Stop IMAP IDLE for a tenant."""
        await self._manager.stop_connection(tenant_id, email_type)
    
    async def stop_all(self) -> None:
        """Stop all IMAP IDLE connections."""
        await self._manager.stop_all()
    
    async def start_all_tenants(self) -> dict[str, bool]:
        """Start IMAP IDLE for all configured tenants."""
        results = {}
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    tenant_id,
                    booking_email_host,
                    booking_email_address,
                    booking_auth_method,
                    stopsale_email_host,
                    stopsale_email_address,
                    stopsale_auth_method
                FROM tenant_settings
                WHERE booking_email_host IS NOT NULL 
                   OR stopsale_email_host IS NOT NULL
                """
            )
        
        for row in rows:
            tenant_id = row["tenant_id"]
            
            # Start booking email IDLE if configured
            if row["booking_email_host"] and row["booking_email_address"]:
                key = f"{tenant_id}:booking"
                try:
                    results[key] = await self.start_tenant_idle(tenant_id, "booking")
                except Exception as e:
                    logger.error(f"Failed to start IDLE for {key}: {e}")
                    results[key] = False
            
            # Start stopsale email IDLE if configured
            if row["stopsale_email_host"] and row["stopsale_email_address"]:
                key = f"{tenant_id}:stopsale"
                try:
                    results[key] = await self.start_tenant_idle(tenant_id, "stopsale")
                except Exception as e:
                    logger.error(f"Failed to start IDLE for {key}: {e}")
                    results[key] = False
        
        return results
    
    async def _get_imap_config(
        self,
        tenant_id: int,
        email_type: str,
    ) -> Optional[IMAPConfig]:
        """Get IMAP configuration for a tenant email."""
        
        prefix = email_type
        oauth_prefix = f"{email_type}_oauth"
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT 
                    {prefix}_email_host,
                    {prefix}_email_port,
                    {prefix}_email_address,
                    {prefix}_email_password_encrypted,
                    {prefix}_email_use_ssl,
                    {prefix}_auth_method,
                    {oauth_prefix}_access_token_encrypted,
                    {oauth_prefix}_connected_email
                FROM tenant_settings
                WHERE tenant_id = $1
                """,
                tenant_id,
            )
        
        if not row or not row[f"{prefix}_email_host"]:
            return None
        
        auth_method_str = row[f"{prefix}_auth_method"] or "password"
        auth_method = AuthMethod.OAUTH2 if auth_method_str == "oauth2" else AuthMethod.PASSWORD
        
        config = IMAPConfig(
            host=row[f"{prefix}_email_host"],
            port=row[f"{prefix}_email_port"] or 993,
            use_ssl=row[f"{prefix}_email_use_ssl"] if row[f"{prefix}_email_use_ssl"] is not None else True,
            auth_method=auth_method,
        )
        
        if auth_method == AuthMethod.PASSWORD:
            # Password authentication
            password_encrypted = row[f"{prefix}_email_password_encrypted"]
            if password_encrypted:
                config.password = decrypt_value(password_encrypted)
            config.username = row[f"{prefix}_email_address"]
        else:
            # OAuth2 authentication
            # Refresh token first if needed
            await self._oauth_service.refresh_google_token(tenant_id, email_type)
            
            # Get access token
            access_token = await self._oauth_service.get_decrypted_access_token(
                tenant_id, email_type
            )
            
            if not access_token:
                logger.error(f"No OAuth access token for tenant {tenant_id} ({email_type})")
                return None
            
            config.oauth_access_token = access_token
            config.oauth_email = row[f"{oauth_prefix}_connected_email"]
        
        return config
    
    def get_status(self, tenant_id: int, email_type: str) -> Optional[str]:
        """Get IMAP IDLE connection status."""
        state = self._manager.get_status(tenant_id, email_type)
        return state.value if state else None
    
    def get_all_statuses(self) -> dict[str, str]:
        """Get all IMAP IDLE connection statuses."""
        return self._manager.get_all_statuses()


# Global service instance
_tenant_imap_service: Optional[TenantIMAPService] = None


def get_tenant_imap_service() -> Optional[TenantIMAPService]:
    """Get global tenant IMAP service."""
    return _tenant_imap_service


def set_tenant_imap_service(service: TenantIMAPService) -> None:
    """Set global tenant IMAP service."""
    global _tenant_imap_service
    _tenant_imap_service = service
