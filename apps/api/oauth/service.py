"""OAuth service for managing email authentication."""

import os
from datetime import datetime, timedelta
from typing import Optional

import httpx
import asyncpg

from .models import (
    OAuthProvider,
    OAuthTokens,
    OAuthAuthorizeResponse,
    OAuthCallbackResponse,
)
from .google import (
    GoogleOAuthConfig,
    TenantGoogleOAuthConfig,
    get_google_oauth_config,
    generate_oauth_state,
    verify_oauth_state,
    build_google_auth_url,
)
from .microsoft import (
    MicrosoftOAuthConfig,
    TenantMicrosoftOAuthConfig,
    get_microsoft_oauth_config,
    generate_microsoft_oauth_state,
    verify_microsoft_oauth_state,
    build_microsoft_auth_url,
)
from tenant.encryption import encrypt_value, decrypt_value


class OAuthService:
    """Service for OAuth authentication flows."""
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.google_config = get_google_oauth_config()
        self.microsoft_config = get_microsoft_oauth_config()
        self.jwt_secret = os.getenv("JWT_SECRET", "change-me-in-production")
    
    async def _get_tenant_microsoft_config(
        self,
        tenant_id: int,
    ) -> Optional[TenantMicrosoftOAuthConfig]:
        """Get tenant-specific Microsoft OAuth configuration from database."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    microsoft_client_id,
                    microsoft_client_secret_encrypted,
                    microsoft_tenant_id
                FROM tenant_settings
                WHERE tenant_id = $1
                """,
                tenant_id,
            )
            
            if not row or not row["microsoft_client_id"]:
                return None
            
            client_secret = decrypt_value(row["microsoft_client_secret_encrypted"]) if row["microsoft_client_secret_encrypted"] else ""
            
            return TenantMicrosoftOAuthConfig(
                client_id=row["microsoft_client_id"],
                client_secret=client_secret,
                tenant_id=row["microsoft_tenant_id"] or "common",
            )
    
    async def _get_tenant_google_config(
        self,
        tenant_id: int,
    ) -> Optional[TenantGoogleOAuthConfig]:
        """Get tenant-specific Google OAuth configuration from database."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    google_client_id,
                    google_client_secret_encrypted
                FROM tenant_settings
                WHERE tenant_id = $1
                """,
                tenant_id,
            )
            
            if not row or not row["google_client_id"]:
                return None
            
            client_secret = decrypt_value(row["google_client_secret_encrypted"]) if row["google_client_secret_encrypted"] else ""
            
            return TenantGoogleOAuthConfig(
                client_id=row["google_client_id"],
                client_secret=client_secret,
            )
    
    async def get_authorization_url(
        self,
        tenant_id: int,
        email_type: str,
        provider: str,
    ) -> OAuthAuthorizeResponse:
        """Generate OAuth authorization URL."""
        
        if provider == "google":
            # Get tenant-specific Google OAuth config
            google_config = await self._get_tenant_google_config(tenant_id)
            if not google_config or not google_config.is_configured:
                raise ValueError("Google OAuth is not configured. Please add your Google credentials in Settings.")
            
            state = generate_oauth_state(
                tenant_id=tenant_id,
                email_type=email_type,
                secret_key=self.jwt_secret,
            )
            
            auth_url = build_google_auth_url(
                config=google_config,
                state=state,
            )
            
            return OAuthAuthorizeResponse(
                authorization_url=auth_url,
                state=state,
            )
        
        elif provider == "microsoft":
            # Get tenant-specific Microsoft OAuth config
            ms_config = await self._get_tenant_microsoft_config(tenant_id)
            if not ms_config or not ms_config.is_configured:
                raise ValueError("Microsoft OAuth is not configured. Please add your Azure credentials in Settings.")
            
            state = generate_microsoft_oauth_state(
                tenant_id=tenant_id,
                email_type=email_type,
                secret_key=self.jwt_secret,
            )
            
            auth_url = build_microsoft_auth_url(
                config=ms_config,
                state=state,
            )
            
            return OAuthAuthorizeResponse(
                authorization_url=auth_url,
                state=state,
            )
        
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    async def handle_google_callback(
        self,
        code: str,
        state: str,
    ) -> OAuthCallbackResponse:
        """Handle Google OAuth callback."""
        
        # Verify state
        state_data = verify_oauth_state(state, self.jwt_secret)
        if not state_data:
            return OAuthCallbackResponse(
                success=False,
                message="Invalid or expired state parameter",
            )
        
        tenant_id = state_data.tenant_id
        email_type = state_data.email_type
        
        # Get tenant-specific Google config
        google_config = await self._get_tenant_google_config(tenant_id)
        if not google_config or not google_config.is_configured:
            return OAuthCallbackResponse(
                success=False,
                message="Google OAuth credentials not configured for this tenant",
            )
        
        # Exchange code for tokens
        try:
            tokens = await self._exchange_google_code(code, google_config)
        except Exception as e:
            return OAuthCallbackResponse(
                success=False,
                message=f"Failed to exchange code: {str(e)}",
            )
        
        # Get user email
        try:
            user_email = await self._get_google_user_email(tokens.access_token)
        except Exception as e:
            return OAuthCallbackResponse(
                success=False,
                message=f"Failed to get user info: {str(e)}",
            )
        
        # Store tokens in database
        await self._store_oauth_tokens(
            tenant_id=tenant_id,
            email_type=email_type,
            provider=OAuthProvider.GOOGLE,
            tokens=tokens,
            connected_email=user_email,
        )
        
        return OAuthCallbackResponse(
            success=True,
            message="Successfully connected to Google",
            connected_email=user_email,
            provider=OAuthProvider.GOOGLE,
        )
    
    async def _exchange_google_code(self, code: str, config: TenantGoogleOAuthConfig) -> OAuthTokens:
        """Exchange authorization code for tokens using tenant-specific config."""
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config.token_uri,
                data={
                    "client_id": config.client_id,
                    "client_secret": config.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": config.redirect_uri,
                },
            )
            
            if response.status_code != 200:
                error_data = response.json()
                raise Exception(error_data.get("error_description", "Token exchange failed"))
            
            data = response.json()
            
            # Calculate token expiry
            expires_in = data.get("expires_in", 3600)
            token_expiry = datetime.utcnow().replace(microsecond=0)
            token_expiry += timedelta(seconds=expires_in)
            
            return OAuthTokens(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                token_expiry=token_expiry,
                scopes=data.get("scope", "").split(" "),
            )
    
    async def _get_google_user_email(self, access_token: str) -> str:
        """Get user email from Google."""
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.google_config.userinfo_uri,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            
            if response.status_code != 200:
                raise Exception("Failed to get user info")
            
            data = response.json()
            return data.get("email", "")
    
    async def _store_oauth_tokens(
        self,
        tenant_id: int,
        email_type: str,  # booking or stopsale
        provider: OAuthProvider,
        tokens: OAuthTokens,
        connected_email: str,
    ) -> None:
        """Store OAuth tokens in database."""
        
        prefix = f"{email_type}_oauth"
        
        # Encrypt sensitive tokens
        access_token_encrypted = encrypt_value(tokens.access_token)
        refresh_token_encrypted = encrypt_value(tokens.refresh_token) if tokens.refresh_token else None
        
        async with self.pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE tenant_settings SET
                    {prefix}_provider = $2,
                    {prefix}_access_token_encrypted = $3,
                    {prefix}_refresh_token_encrypted = $4,
                    {prefix}_token_expiry = $5,
                    {prefix}_scopes = $6,
                    {prefix}_connected_email = $7,
                    {email_type}_auth_method = 'oauth2',
                    updated_at = NOW()
                WHERE tenant_id = $1
                """,
                tenant_id,
                provider.value,
                access_token_encrypted,
                refresh_token_encrypted,
                tokens.token_expiry,
                tokens.scopes,
                connected_email,
            )
    
    async def refresh_google_token(
        self,
        tenant_id: int,
        email_type: str,
    ) -> bool:
        """Refresh Google OAuth token if needed."""
        
        prefix = f"{email_type}_oauth"
        
        # Get tenant-specific Google config
        google_config = await self._get_tenant_google_config(tenant_id)
        if not google_config or not google_config.is_configured:
            return False
        
        async with self.pool.acquire() as conn:
            # Get current tokens
            row = await conn.fetchrow(
                f"""
                SELECT 
                    {prefix}_refresh_token_encrypted,
                    {prefix}_token_expiry
                FROM tenant_settings
                WHERE tenant_id = $1
                """,
                tenant_id,
            )
            
            if not row or not row[f"{prefix}_refresh_token_encrypted"]:
                return False
            
            # Check if refresh is needed (5 minutes before expiry)
            token_expiry = row[f"{prefix}_token_expiry"]
            if token_expiry:
                # Make sure we compare naive datetimes
                if token_expiry.tzinfo is not None:
                    token_expiry = token_expiry.replace(tzinfo=None)
                if datetime.utcnow() < token_expiry - timedelta(minutes=5):
                    return True  # Token still valid
            
            # Decrypt refresh token
            refresh_token = decrypt_value(row[f"{prefix}_refresh_token_encrypted"])
            if not refresh_token:
                return False
            
            # Exchange refresh token for new access token
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        google_config.token_uri,
                        data={
                            "client_id": google_config.client_id,
                            "client_secret": google_config.client_secret,
                            "refresh_token": refresh_token,
                            "grant_type": "refresh_token",
                        },
                    )
                    
                    if response.status_code != 200:
                        return False
                    
                    data = response.json()
                    
                    # Calculate new expiry
                    expires_in = data.get("expires_in", 3600)
                    new_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
                    
                    # Update tokens
                    new_access_encrypted = encrypt_value(data["access_token"])
                    
                    await conn.execute(
                        f"""
                        UPDATE tenant_settings SET
                            {prefix}_access_token_encrypted = $2,
                            {prefix}_token_expiry = $3,
                            updated_at = NOW()
                        WHERE tenant_id = $1
                        """,
                        tenant_id,
                        new_access_encrypted,
                        new_expiry,
                    )
                    
                    return True
                    
            except Exception:
                return False
    
    async def disconnect_oauth(
        self,
        tenant_id: int,
        email_type: str,
    ) -> bool:
        """Disconnect OAuth and revert to password auth."""
        
        prefix = f"{email_type}_oauth"
        
        async with self.pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE tenant_settings SET
                    {prefix}_provider = NULL,
                    {prefix}_client_id = NULL,
                    {prefix}_client_secret_encrypted = NULL,
                    {prefix}_access_token_encrypted = NULL,
                    {prefix}_refresh_token_encrypted = NULL,
                    {prefix}_token_expiry = NULL,
                    {prefix}_scopes = NULL,
                    {prefix}_connected_email = NULL,
                    {email_type}_auth_method = 'password',
                    updated_at = NOW()
                WHERE tenant_id = $1
                """,
                tenant_id,
            )
            return True
    
    async def get_decrypted_access_token(
        self,
        tenant_id: int,
        email_type: str,
    ) -> Optional[str]:
        """Get decrypted access token for email operations."""
        
        prefix = f"{email_type}_oauth"
        
        # First try to refresh if needed
        await self.refresh_google_token(tenant_id, email_type)
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT {prefix}_access_token_encrypted
                FROM tenant_settings
                WHERE tenant_id = $1
                """,
                tenant_id,
            )
            
            if not row or not row[f"{prefix}_access_token_encrypted"]:
                return None
            
            return decrypt_value(row[f"{prefix}_access_token_encrypted"])
    
    # =========================================================================
    # Microsoft OAuth Methods
    # =========================================================================
    
    async def handle_microsoft_callback(
        self,
        code: str,
        state: str,
    ) -> OAuthCallbackResponse:
        """Handle Microsoft OAuth callback."""
        
        # Verify state
        state_data = verify_microsoft_oauth_state(state, self.jwt_secret)
        if not state_data:
            return OAuthCallbackResponse(
                success=False,
                message="Invalid or expired state parameter",
            )
        
        tenant_id = state_data.tenant_id
        email_type = state_data.email_type
        
        # Get tenant-specific config
        ms_config = await self._get_tenant_microsoft_config(tenant_id)
        if not ms_config or not ms_config.is_configured:
            return OAuthCallbackResponse(
                success=False,
                message="Microsoft OAuth not configured for this tenant",
            )
        
        # Exchange code for tokens
        try:
            tokens = await self._exchange_microsoft_code(code, ms_config)
        except Exception as e:
            return OAuthCallbackResponse(
                success=False,
                message=f"Failed to exchange code: {str(e)}",
            )
        
        # Get user email
        try:
            user_email = await self._get_microsoft_user_email(tokens.access_token)
        except Exception as e:
            return OAuthCallbackResponse(
                success=False,
                message=f"Failed to get user info: {str(e)}",
            )
        
        # Store tokens in database
        await self._store_oauth_tokens(
            tenant_id=tenant_id,
            email_type=email_type,
            provider=OAuthProvider.MICROSOFT,
            tokens=tokens,
            connected_email=user_email,
        )
        
        return OAuthCallbackResponse(
            success=True,
            message="Successfully connected to Microsoft",
            connected_email=user_email,
            provider=OAuthProvider.MICROSOFT,
        )
    
    async def _exchange_microsoft_code(
        self,
        code: str,
        config: TenantMicrosoftOAuthConfig,
    ) -> OAuthTokens:
        """Exchange Microsoft authorization code for tokens."""
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config.token_uri,
                data={
                    "client_id": config.client_id,
                    "client_secret": config.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": config.redirect_uri,
                    "scope": " ".join(config.scopes),
                },
            )
            
            if response.status_code != 200:
                error_data = response.json()
                raise Exception(error_data.get("error_description", "Token exchange failed"))
            
            data = response.json()
            
            # Calculate token expiry
            expires_in = data.get("expires_in", 3600)
            token_expiry = datetime.utcnow().replace(microsecond=0)
            token_expiry += timedelta(seconds=expires_in)
            
            return OAuthTokens(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                token_expiry=token_expiry,
                scopes=data.get("scope", "").split(" "),
            )
    
    async def _get_microsoft_user_email(self, access_token: str) -> str:
        """Get user email from Microsoft Graph API."""
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            
            if response.status_code != 200:
                raise Exception("Failed to get user info")
            
            data = response.json()
            # Microsoft returns 'mail' or 'userPrincipalName'
            return data.get("mail") or data.get("userPrincipalName", "")
    
    async def refresh_microsoft_token(
        self,
        tenant_id: int,
        email_type: str,
    ) -> bool:
        """Refresh Microsoft OAuth token if needed."""
        
        prefix = f"{email_type}_oauth"
        
        async with self.pool.acquire() as conn:
            # Get current tokens
            row = await conn.fetchrow(
                f"""
                SELECT 
                    {prefix}_refresh_token_encrypted,
                    {prefix}_token_expiry,
                    {prefix}_provider
                FROM tenant_settings
                WHERE tenant_id = $1
                """,
                tenant_id,
            )
            
            if not row or not row[f"{prefix}_refresh_token_encrypted"]:
                return False
            
            # Only process Microsoft tokens
            if row[f"{prefix}_provider"] != "microsoft":
                return False
            
            # Check if refresh is needed (5 minutes before expiry)
            token_expiry = row[f"{prefix}_token_expiry"]
            if token_expiry and datetime.utcnow() < token_expiry - timedelta(minutes=5):
                return True  # Token still valid
            
            # Decrypt refresh token
            refresh_token = decrypt_value(row[f"{prefix}_refresh_token_encrypted"])
            if not refresh_token:
                return False
            
            # Exchange refresh token for new access token
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.microsoft_config.token_uri,
                        data={
                            "client_id": self.microsoft_config.client_id,
                            "client_secret": self.microsoft_config.client_secret,
                            "refresh_token": refresh_token,
                            "grant_type": "refresh_token",
                            "scope": " ".join(self.microsoft_config.scopes),
                        },
                    )
                    
                    if response.status_code != 200:
                        return False
                    
                    data = response.json()
                    
                    # Calculate new expiry
                    expires_in = data.get("expires_in", 3600)
                    new_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
                    
                    # Update tokens
                    new_access_encrypted = encrypt_value(data["access_token"])
                    
                    # Microsoft may return a new refresh token
                    new_refresh_encrypted = None
                    if data.get("refresh_token"):
                        new_refresh_encrypted = encrypt_value(data["refresh_token"])
                    
                    if new_refresh_encrypted:
                        await conn.execute(
                            f"""
                            UPDATE tenant_settings SET
                                {prefix}_access_token_encrypted = $2,
                                {prefix}_refresh_token_encrypted = $3,
                                {prefix}_token_expiry = $4,
                                updated_at = NOW()
                            WHERE tenant_id = $1
                            """,
                            tenant_id,
                            new_access_encrypted,
                            new_refresh_encrypted,
                            new_expiry,
                        )
                    else:
                        await conn.execute(
                            f"""
                            UPDATE tenant_settings SET
                                {prefix}_access_token_encrypted = $2,
                                {prefix}_token_expiry = $3,
                                updated_at = NOW()
                            WHERE tenant_id = $1
                            """,
                            tenant_id,
                            new_access_encrypted,
                            new_expiry,
                        )
                    
                    return True
                    
            except Exception:
                return False
