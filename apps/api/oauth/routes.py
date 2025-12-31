"""OAuth API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, HTMLResponse

from .models import (
    OAuthProvider,
    OAuthAuthorizeRequest,
    OAuthAuthorizeResponse,
    OAuthCallbackResponse,
    OAuthDisconnectRequest,
)
from .service import OAuthService
from auth import get_current_user
from auth.models import UserResponse


router = APIRouter(prefix="/api/oauth", tags=["oauth"])


def get_oauth_service(request: Request) -> OAuthService:
    """Get OAuth service from request state."""
    return OAuthService(request.app.state.pool)


@router.post("/google/authorize", response_model=OAuthAuthorizeResponse)
async def google_authorize(
    data: OAuthAuthorizeRequest,
    user: UserResponse = Depends(get_current_user),
    service: OAuthService = Depends(get_oauth_service),
):
    """
    Get Google OAuth authorization URL.
    
    Returns a URL that the frontend should redirect to for OAuth consent.
    """
    try:
        return await service.get_authorization_url(
            tenant_id=user.tenant_id,
            email_type=data.email_type,
            provider="google",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/google/callback")
async def google_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    error_description: str = Query(None),
    request: Request = None,
):
    """
    Handle Google OAuth callback.
    
    This endpoint is called by Google after user consent.
    Redirects back to the settings page with success/error status.
    """
    # Error from Google
    if error:
        error_msg = error_description or error
        return RedirectResponse(
            url=f"/settings?oauth_error={error_msg}",
            status_code=302,
        )
    
    # Missing parameters
    if not code or not state:
        return RedirectResponse(
            url="/settings?oauth_error=Missing%20authorization%20code",
            status_code=302,
        )
    
    # Process callback
    service = OAuthService(request.app.state.pool)
    result = await service.handle_google_callback(code, state)
    
    if result.success:
        return RedirectResponse(
            url=f"/settings?oauth_success=true&email={result.connected_email}",
            status_code=302,
        )
    else:
        return RedirectResponse(
            url=f"/settings?oauth_error={result.message}",
            status_code=302,
        )


# =============================================================================
# Microsoft OAuth Routes
# =============================================================================

@router.post("/microsoft/authorize", response_model=OAuthAuthorizeResponse)
async def microsoft_authorize(
    data: OAuthAuthorizeRequest,
    user: UserResponse = Depends(get_current_user),
    service: OAuthService = Depends(get_oauth_service),
):
    """
    Get Microsoft OAuth authorization URL.
    
    Returns a URL that the frontend should redirect to for OAuth consent.
    """
    try:
        return await service.get_authorization_url(
            tenant_id=user.tenant_id,
            email_type=data.email_type,
            provider="microsoft",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/microsoft/callback")
async def microsoft_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    error_description: str = Query(None),
    request: Request = None,
):
    """
    Handle Microsoft OAuth callback.
    
    This endpoint is called by Microsoft after user consent.
    Redirects back to the settings page with success/error status.
    """
    # Error from Microsoft
    if error:
        error_msg = error_description or error
        return RedirectResponse(
            url=f"/settings?oauth_error={error_msg}",
            status_code=302,
        )
    
    # Missing parameters
    if not code or not state:
        return RedirectResponse(
            url="/settings?oauth_error=Missing%20authorization%20code",
            status_code=302,
        )
    
    # Process callback
    service = OAuthService(request.app.state.pool)
    result = await service.handle_microsoft_callback(code, state)
    
    if result.success:
        return RedirectResponse(
            url=f"/settings?oauth_success=true&email={result.connected_email}",
            status_code=302,
        )
    else:
        return RedirectResponse(
            url=f"/settings?oauth_error={result.message}",
            status_code=302,
        )


@router.post("/microsoft/disconnect")
async def microsoft_disconnect(
    data: OAuthDisconnectRequest,
    user: UserResponse = Depends(get_current_user),
    service: OAuthService = Depends(get_oauth_service),
):
    """
    Disconnect Microsoft OAuth and revert to password authentication.
    """
    success = await service.disconnect_oauth(
        tenant_id=user.tenant_id,
        email_type=data.email_type,
    )
    
    return {
        "success": success,
        "message": "Successfully disconnected from Microsoft" if success else "Failed to disconnect",
    }


@router.post("/google/disconnect")
async def google_disconnect(
    data: OAuthDisconnectRequest,
    user: UserResponse = Depends(get_current_user),
    service: OAuthService = Depends(get_oauth_service),
):
    """
    Disconnect Google OAuth and revert to password authentication.
    """
    success = await service.disconnect_oauth(
        tenant_id=user.tenant_id,
        email_type=data.email_type,
    )
    
    return {
        "success": success,
        "message": "Successfully disconnected from Google" if success else "Failed to disconnect",
    }


@router.post("/refresh")
async def refresh_token(
    email_type: str = Query(..., pattern="^(booking|stopsale)$"),
    user: UserResponse = Depends(get_current_user),
    service: OAuthService = Depends(get_oauth_service),
):
    """
    Manually refresh OAuth token.
    
    Usually not needed as tokens are refreshed automatically.
    """
    success = await service.refresh_google_token(
        tenant_id=user.tenant_id,
        email_type=email_type,
    )
    
    return {
        "success": success,
        "message": "Token refreshed" if success else "Failed to refresh token",
    }


# Development-only: OAuth status check
@router.get("/status")
async def oauth_status(
    user: UserResponse = Depends(get_current_user),
    request: Request = None,
):
    """
    Check OAuth configuration status.
    """
    from .google import get_google_oauth_config
    from .microsoft import get_microsoft_oauth_config
    
    google_config = get_google_oauth_config()
    microsoft_config = get_microsoft_oauth_config()
    
    return {
        "google": {
            "configured": google_config.is_configured,
            "client_id_set": bool(google_config.client_id),
            "client_secret_set": bool(google_config.client_secret),
            "redirect_uri": google_config.redirect_uri,
            "scopes": google_config.scopes,
        },
        "microsoft": {
            "configured": microsoft_config.is_configured,
            "client_id_set": bool(microsoft_config.client_id),
            "client_secret_set": bool(microsoft_config.client_secret),
            "tenant_id": microsoft_config.tenant_id,
            "redirect_uri": microsoft_config.redirect_uri,
            "scopes": microsoft_config.scopes,
        },
    }


@router.get("/token-refresh/status")
async def token_refresh_status(
    user: UserResponse = Depends(get_current_user),
):
    """
    Get token refresh job status and statistics.
    """
    from .token_refresh_job import get_token_refresh_job
    
    job = get_token_refresh_job()
    if not job:
        return {
            "running": False,
            "message": "Token refresh job not initialized",
        }
    
    return await job.get_status()
