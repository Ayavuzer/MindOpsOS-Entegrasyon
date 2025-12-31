"""Pydantic models for tenant settings."""

from datetime import datetime
from typing import Optional, TYPE_CHECKING
from pydantic import BaseModel, Field
from enum import Enum


# Define enums locally to avoid circular imports
class OAuthProvider(str, Enum):
    """Supported OAuth providers."""
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    NONE = "none"


class EmailAuthMethod(str, Enum):
    """Email authentication methods."""
    PASSWORD = "password"
    OAUTH2 = "oauth2"
    APP_PASSWORD = "app_password"


class OAuthConfigResponse(BaseModel):
    """OAuth configuration response (no secrets)."""
    
    provider: OAuthProvider = OAuthProvider.NONE
    is_connected: bool = False
    connected_email: Optional[str] = None
    token_expiry: Optional[datetime] = None
    scopes: list[str] = Field(default_factory=list)


class EmailConfig(BaseModel):
    """Email server configuration."""
    
    host: Optional[str] = None
    port: int = 993
    address: Optional[str] = None
    password: Optional[str] = None  # Only used for input, never returned
    protocol: str = "imap"  # pop3 or imap
    use_ssl: bool = True
    folder: str = "INBOX"
    
    # Authentication method
    auth_method: EmailAuthMethod = EmailAuthMethod.PASSWORD
    
    # OAuth configuration (response only, no secrets)
    oauth: Optional[OAuthConfigResponse] = None
    
    # Real-time settings
    use_idle: bool = True
    
    # Health info (read-only, returned in response)
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count_24h: int = 0


class SednaConfig(BaseModel):
    """Sedna API configuration."""
    
    api_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None  # Only used for input, never returned
    operator_id: Optional[int] = None
    operator_code: Optional[str] = None  # Operator code for OperatorRemark (e.g., "7STAR")
    authority_id: Optional[int] = 207  # Authority ID for stop sales (default: 207)


class ProcessingConfig(BaseModel):
    """Processing settings."""
    
    email_check_interval_seconds: int = 60
    auto_process_enabled: bool = True
    delete_after_fetch: bool = False


class MicrosoftOAuthConfig(BaseModel):
    """Microsoft/Azure OAuth configuration for tenant."""
    
    client_id: Optional[str] = None
    client_secret: Optional[str] = None  # Only used for input, never returned
    tenant_id: str = "common"  # Azure AD tenant ID or 'common' for any


class GoogleOAuthConfig(BaseModel):
    """Google OAuth configuration for tenant."""
    
    client_id: Optional[str] = None
    client_secret: Optional[str] = None  # Only used for input, never returned


class TenantSettingsResponse(BaseModel):
    """Tenant settings response (no passwords)."""
    
    booking_email: EmailConfig
    stopsale_email: EmailConfig
    sedna: SednaConfig
    processing: ProcessingConfig
    microsoft_oauth: Optional[MicrosoftOAuthConfig] = None
    google_oauth: Optional[GoogleOAuthConfig] = None
    
    # Password indicators
    has_booking_password: bool = False
    has_stopsale_password: bool = False
    has_sedna_password: bool = False
    has_microsoft_oauth: bool = False
    has_google_oauth: bool = False
    
    # OAuth indicators
    has_booking_oauth: bool = False
    has_stopsale_oauth: bool = False


class EmailConfigUpdate(BaseModel):
    """Email configuration update request."""
    
    host: Optional[str] = None
    port: Optional[int] = None
    address: Optional[str] = None
    password: Optional[str] = None
    protocol: Optional[str] = None
    use_ssl: Optional[bool] = None
    folder: Optional[str] = None
    auth_method: Optional[EmailAuthMethod] = None
    use_idle: Optional[bool] = None


class TenantSettingsUpdate(BaseModel):
    """Tenant settings update request."""
    
    booking_email: Optional[EmailConfigUpdate] = None
    stopsale_email: Optional[EmailConfigUpdate] = None
    sedna: Optional[SednaConfig] = None
    processing: Optional[ProcessingConfig] = None
    microsoft_oauth: Optional[MicrosoftOAuthConfig] = None
    google_oauth: Optional[GoogleOAuthConfig] = None


class ConnectionTestResult(BaseModel):
    """Connection test result."""
    
    success: bool
    message: str
    details: Optional[dict] = None
