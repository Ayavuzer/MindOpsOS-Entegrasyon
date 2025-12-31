"""Google OAuth 2.0 configuration and utilities."""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import jwt
from pydantic import BaseModel

from .models import OAuthProvider, GOOGLE_OAUTH_SCOPES


class GoogleOAuthConfig:
    """Google OAuth 2.0 configuration."""
    
    def __init__(self):
        self.client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
        self.client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
        self.redirect_uri = os.getenv(
            "GOOGLE_OAUTH_REDIRECT_URI",
            "https://entegrasyon.mindops.net/api/oauth/google/callback"
        )
        self.scopes = GOOGLE_OAUTH_SCOPES
        
        # OAuth endpoints
        self.auth_uri = "https://accounts.google.com/o/oauth2/v2/auth"
        self.token_uri = "https://oauth2.googleapis.com/token"
        self.userinfo_uri = "https://www.googleapis.com/oauth2/v2/userinfo"
        self.revoke_uri = "https://oauth2.googleapis.com/revoke"
    
    @property
    def is_configured(self) -> bool:
        """Check if OAuth is properly configured."""
        return bool(self.client_id and self.client_secret)


class TenantGoogleOAuthConfig:
    """Tenant-specific Google OAuth 2.0 configuration."""
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = os.getenv(
            "GOOGLE_OAUTH_REDIRECT_URI",
            "https://entegrasyon.mindops.net/api/oauth/google/callback"
        )
        self.scopes = GOOGLE_OAUTH_SCOPES
        
        # OAuth endpoints
        self.auth_uri = "https://accounts.google.com/o/oauth2/v2/auth"
        self.token_uri = "https://oauth2.googleapis.com/token"
        self.userinfo_uri = "https://www.googleapis.com/oauth2/v2/userinfo"
        self.revoke_uri = "https://oauth2.googleapis.com/revoke"
    
    @property
    def is_configured(self) -> bool:
        """Check if OAuth is properly configured."""
        return bool(self.client_id and self.client_secret)


class GoogleOAuthState(BaseModel):
    """OAuth state parameter for CSRF protection."""
    
    tenant_id: int
    email_type: str  # booking or stopsale
    nonce: str
    exp: datetime


def generate_oauth_state(
    tenant_id: int,
    email_type: str,
    secret_key: str,
    expires_minutes: int = 10,
) -> str:
    """Generate a secure OAuth state parameter."""
    payload = {
        "tenant_id": tenant_id,
        "email_type": email_type,
        "nonce": secrets.token_urlsafe(16),
        "exp": datetime.utcnow() + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def verify_oauth_state(
    state: str,
    secret_key: str,
) -> Optional[GoogleOAuthState]:
    """Verify and decode OAuth state parameter."""
    try:
        payload = jwt.decode(state, secret_key, algorithms=["HS256"])
        return GoogleOAuthState(**payload)
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def build_google_auth_url(
    config: GoogleOAuthConfig,
    state: str,
) -> str:
    """Build Google OAuth authorization URL."""
    params = {
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "scope": " ".join(config.scopes),
        "state": state,
        "access_type": "offline",  # Get refresh token
        "prompt": "consent",  # Force consent to get refresh token
    }
    return f"{config.auth_uri}?{urlencode(params)}"


# Singleton instance
_google_config: Optional[GoogleOAuthConfig] = None


def get_google_oauth_config() -> GoogleOAuthConfig:
    """Get Google OAuth configuration singleton."""
    global _google_config
    if _google_config is None:
        _google_config = GoogleOAuthConfig()
    return _google_config
