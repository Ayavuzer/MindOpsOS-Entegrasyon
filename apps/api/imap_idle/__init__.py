"""Email module for IMAP IDLE and email processing."""

from .imap_idle import (
    IMAPConfig,
    IMAPIdleClient,
    IMAPConnectionManager,
    EmailNotification,
    ConnectionState,
    AuthMethod,
    get_imap_manager,
)

from .tenant_imap_service import (
    TenantIMAPService,
    get_tenant_imap_service,
    set_tenant_imap_service,
)

__all__ = [
    # IMAP IDLE
    "IMAPConfig",
    "IMAPIdleClient",
    "IMAPConnectionManager",
    "EmailNotification",
    "ConnectionState",
    "AuthMethod",
    "get_imap_manager",
    # Tenant Service
    "TenantIMAPService",
    "get_tenant_imap_service",
    "set_tenant_imap_service",
]
