"""OAuth module for email authentication."""

from .models import (
    OAuthProvider,
    EmailAuthMethod,
    OAuthConfigBase,
    OAuthConfigResponse,
    OAuthTokens,
    OAuthAuthorizeRequest,
    OAuthAuthorizeResponse,
    OAuthCallbackRequest,
    OAuthCallbackResponse,
    OAuthDisconnectRequest,
    EmailHealthStatus,
    EmailHealthResponse,
    GOOGLE_OAUTH_SCOPES,
    MICROSOFT_OAUTH_SCOPES,
)
from .google import (
    GoogleOAuthConfig,
    get_google_oauth_config,
    generate_oauth_state,
    verify_oauth_state,
    build_google_auth_url,
)


# Lazy import to avoid circular dependencies
def get_oauth_router():
    """Get OAuth router (lazy import to avoid circular deps)."""
    from .routes import router
    return router


# For backward compatibility
@property
def oauth_router():
    return get_oauth_router()


__all__ = [
    # Models
    "OAuthProvider",
    "EmailAuthMethod",
    "OAuthConfigBase",
    "OAuthConfigResponse",
    "OAuthTokens",
    "OAuthAuthorizeRequest",
    "OAuthAuthorizeResponse",
    "OAuthCallbackRequest",
    "OAuthCallbackResponse",
    "OAuthDisconnectRequest",
    "EmailHealthStatus",
    "EmailHealthResponse",
    "GOOGLE_OAUTH_SCOPES",
    "MICROSOFT_OAUTH_SCOPES",
    # Google
    "GoogleOAuthConfig",
    "get_google_oauth_config",
    "generate_oauth_state",
    "verify_oauth_state",
    "build_google_auth_url",
    # Router
    "get_oauth_router",
]
