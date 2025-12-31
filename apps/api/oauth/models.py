"""OAuth 2.0 models for email integration."""

from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field


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


class OAuthConfigBase(BaseModel):
    """Base OAuth configuration (for input)."""
    
    provider: OAuthProvider = OAuthProvider.NONE
    client_id: Optional[str] = None
    client_secret: Optional[str] = None  # Only for input
    scopes: list[str] = Field(default_factory=list)


class OAuthConfigResponse(BaseModel):
    """OAuth configuration response (no secrets)."""
    
    provider: OAuthProvider = OAuthProvider.NONE
    is_connected: bool = False
    connected_email: Optional[str] = None
    token_expiry: Optional[datetime] = None
    scopes: list[str] = Field(default_factory=list)


class OAuthTokens(BaseModel):
    """OAuth tokens for internal use (encrypted storage)."""
    
    access_token: str
    refresh_token: Optional[str] = None
    token_expiry: Optional[datetime] = None
    scopes: list[str] = Field(default_factory=list)


class OAuthAuthorizeRequest(BaseModel):
    """OAuth authorization request."""
    
    email_type: str = Field(..., pattern="^(booking|stopsale)$")
    provider: OAuthProvider


class OAuthAuthorizeResponse(BaseModel):
    """OAuth authorization URL response."""
    
    authorization_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    """OAuth callback request."""
    
    code: str
    state: str
    error: Optional[str] = None
    error_description: Optional[str] = None


class OAuthCallbackResponse(BaseModel):
    """OAuth callback response."""
    
    success: bool
    message: str
    connected_email: Optional[str] = None
    provider: Optional[OAuthProvider] = None


class OAuthDisconnectRequest(BaseModel):
    """OAuth disconnect request."""
    
    email_type: str = Field(..., pattern="^(booking|stopsale)$")


class EmailHealthStatus(BaseModel):
    """Email connection health status."""
    
    email_type: str
    connection_status: str  # connected, disconnected, error
    auth_method: EmailAuthMethod
    
    # OAuth info (if applicable)
    oauth_provider: Optional[OAuthProvider] = None
    oauth_connected_email: Optional[str] = None
    oauth_token_expiry: Optional[datetime] = None
    
    # Health metrics
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count_24h: int = 0
    
    # Processing stats
    emails_processed_24h: int = 0
    emails_failed_24h: int = 0


class EmailHealthResponse(BaseModel):
    """Email health response for both email types."""
    
    booking: EmailHealthStatus
    stopsale: EmailHealthStatus


# Google OAuth specific scopes - mail.google.com is required for IMAP access
GOOGLE_OAUTH_SCOPES = [
    "https://mail.google.com/",  # Required for IMAP/SMTP access
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/userinfo.email",
]

# Microsoft Graph specific scopes
MICROSOFT_OAUTH_SCOPES = [
    "offline_access",
    "User.Read",
    "Mail.Read",
    "Mail.ReadWrite",
]
