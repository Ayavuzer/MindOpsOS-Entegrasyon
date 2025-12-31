"""Microsoft OAuth 2.0 configuration and utilities."""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import jwt
from pydantic import BaseModel


# Microsoft OAuth scopes for email access
MICROSOFT_OAUTH_SCOPES = [
    "openid",
    "profile",
    "email",
    "offline_access",  # Required for refresh tokens
    "https://outlook.office.com/IMAP.AccessAsUser.All",
    "https://outlook.office.com/SMTP.Send",
]


class MicrosoftOAuthConfig:
    """Microsoft OAuth 2.0 configuration (system-level fallback)."""
    
    def __init__(self):
        self.client_id = os.getenv("MICROSOFT_OAUTH_CLIENT_ID", "")
        self.client_secret = os.getenv("MICROSOFT_OAUTH_CLIENT_SECRET", "")
        self.tenant_id = os.getenv("MICROSOFT_OAUTH_TENANT_ID", "common")  # 'common' for multi-tenant
        self.redirect_uri = os.getenv(
            "MICROSOFT_OAUTH_REDIRECT_URI",
            "https://entegrasyon.mindops.net/api/oauth/microsoft/callback"
        )
        self.scopes = MICROSOFT_OAUTH_SCOPES
        
        # OAuth endpoints (using tenant-specific or common endpoint)
        self.auth_uri = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize"
        self.token_uri = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        self.userinfo_uri = "https://graph.microsoft.com/v1.0/me"
    
    @property
    def is_configured(self) -> bool:
        """Check if OAuth is properly configured."""
        return bool(self.client_id and self.client_secret)


class TenantMicrosoftOAuthConfig:
    """Tenant-specific Microsoft OAuth 2.0 configuration."""
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str = "common",
        redirect_uri: str = "https://entegrasyon.mindops.net/api/oauth/microsoft/callback",
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id or "common"
        self.redirect_uri = redirect_uri
        self.scopes = MICROSOFT_OAUTH_SCOPES
        
        # OAuth endpoints
        self.auth_uri = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize"
        self.token_uri = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        self.userinfo_uri = "https://graph.microsoft.com/v1.0/me"
    
    @property
    def is_configured(self) -> bool:
        """Check if OAuth is properly configured."""
        return bool(self.client_id and self.client_secret)


class MicrosoftOAuthState(BaseModel):
    """OAuth state parameter for CSRF protection."""
    
    tenant_id: int
    email_type: str  # booking or stopsale
    nonce: str
    exp: datetime


def generate_microsoft_oauth_state(
    tenant_id: int,
    email_type: str,
    secret_key: str,
    expires_minutes: int = 10,
) -> str:
    """Generate a secure OAuth state parameter."""
    payload = {
        "tenant_id": tenant_id,
        "email_type": email_type,
        "provider": "microsoft",
        "nonce": secrets.token_urlsafe(16),
        "exp": datetime.utcnow() + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def verify_microsoft_oauth_state(
    state: str,
    secret_key: str,
) -> Optional[MicrosoftOAuthState]:
    """Verify and decode OAuth state parameter."""
    try:
        payload = jwt.decode(state, secret_key, algorithms=["HS256"])
        if payload.get("provider") != "microsoft":
            return None
        return MicrosoftOAuthState(**payload)
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def build_microsoft_auth_url(
    config: MicrosoftOAuthConfig,
    state: str,
) -> str:
    """Build Microsoft OAuth authorization URL."""
    params = {
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "scope": " ".join(config.scopes),
        "state": state,
        "response_mode": "query",
        "prompt": "consent",  # Force consent to get refresh token
    }
    return f"{config.auth_uri}?{urlencode(params)}"


# Singleton instance
_microsoft_config: Optional[MicrosoftOAuthConfig] = None


def get_microsoft_oauth_config() -> MicrosoftOAuthConfig:
    """Get Microsoft OAuth configuration singleton."""
    global _microsoft_config
    if _microsoft_config is None:
        _microsoft_config = MicrosoftOAuthConfig()
    return _microsoft_config
