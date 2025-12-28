"""Email module."""

from .routes import router, set_email_service
from .service import TenantEmailService, FetchResult

__all__ = [
    "router",
    "set_email_service",
    "TenantEmailService",
    "FetchResult",
]
