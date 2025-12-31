"""Tenant settings service."""

from typing import Optional
import asyncpg

from .encryption import encrypt_value, decrypt_value
from .models import (
    EmailConfig,
    SednaConfig,
    ProcessingConfig,
    MicrosoftOAuthConfig,
    GoogleOAuthConfig,
    TenantSettingsResponse,
    TenantSettingsUpdate,
    ConnectionTestResult,
)


class TenantSettingsService:
    """Service for managing tenant settings."""
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
    
    async def get_settings(self, tenant_id: int) -> TenantSettingsResponse:
        """Get tenant settings (without passwords)."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM tenant_settings WHERE tenant_id = $1",
                tenant_id,
            )
            
            if not row:
                # Return defaults if no settings exist
                return TenantSettingsResponse(
                    booking_email=EmailConfig(),
                    stopsale_email=EmailConfig(),
                    sedna=SednaConfig(),
                    processing=ProcessingConfig(),
                )
            
            return TenantSettingsResponse(
                booking_email=EmailConfig(
                    host=row["booking_email_host"],
                    port=row["booking_email_port"] or 995,
                    address=row["booking_email_address"],
                    protocol=row["booking_email_protocol"] or "pop3",
                    use_ssl=row["booking_email_use_ssl"] if row["booking_email_use_ssl"] is not None else True,
                ),
                stopsale_email=EmailConfig(
                    host=row["stopsale_email_host"],
                    port=row["stopsale_email_port"] or 995,
                    address=row["stopsale_email_address"],
                    protocol=row["stopsale_email_protocol"] or "pop3",
                    use_ssl=row["stopsale_email_use_ssl"] if row["stopsale_email_use_ssl"] is not None else True,
                ),
                sedna=SednaConfig(
                    api_url=row["sedna_api_url"],
                    username=row["sedna_username"],
                    operator_id=row["sedna_operator_id"],
                    operator_code=row.get("sedna_operator_code"),
                    authority_id=row.get("sedna_authority_id") or 207,
                ),
                processing=ProcessingConfig(
                    email_check_interval_seconds=row["email_check_interval_seconds"] or 60,
                    auto_process_enabled=row["auto_process_enabled"] if row["auto_process_enabled"] is not None else True,
                    delete_after_fetch=row["delete_after_fetch"] if row["delete_after_fetch"] is not None else False,
                ),
                microsoft_oauth=MicrosoftOAuthConfig(
                    client_id=row.get("microsoft_client_id"),
                    tenant_id=row.get("microsoft_tenant_id") or "common",
                ) if row.get("microsoft_client_id") else None,
                google_oauth=GoogleOAuthConfig(
                    client_id=row.get("google_client_id"),
                ) if row.get("google_client_id") else None,
                has_booking_password=row["booking_email_password_encrypted"] is not None,
                has_stopsale_password=row["stopsale_email_password_encrypted"] is not None,
                has_sedna_password=row["sedna_password_encrypted"] is not None,
                has_microsoft_oauth=row.get("microsoft_client_id") is not None and row.get("microsoft_client_secret_encrypted") is not None,
                has_google_oauth=row.get("google_client_id") is not None and row.get("google_client_secret_encrypted") is not None,
            )
    
    async def update_settings(
        self,
        tenant_id: int,
        data: TenantSettingsUpdate,
    ) -> TenantSettingsResponse:
        """Update tenant settings."""
        async with self.pool.acquire() as conn:
            # Check if settings exist
            existing = await conn.fetchval(
                "SELECT id FROM tenant_settings WHERE tenant_id = $1",
                tenant_id,
            )
            
            if not existing:
                # Create new settings
                await conn.execute(
                    "INSERT INTO tenant_settings (tenant_id) VALUES ($1)",
                    tenant_id,
                )
            
            # Build update query dynamically
            updates = []
            params = [tenant_id]
            param_idx = 2
            
            if data.booking_email:
                if data.booking_email.host is not None:
                    updates.append(f"booking_email_host = ${param_idx}")
                    params.append(data.booking_email.host)
                    param_idx += 1
                if data.booking_email.port is not None:
                    updates.append(f"booking_email_port = ${param_idx}")
                    params.append(data.booking_email.port)
                    param_idx += 1
                if data.booking_email.address is not None:
                    updates.append(f"booking_email_address = ${param_idx}")
                    params.append(data.booking_email.address)
                    param_idx += 1
                if data.booking_email.password:
                    updates.append(f"booking_email_password_encrypted = ${param_idx}")
                    params.append(encrypt_value(data.booking_email.password))
                    param_idx += 1
                if data.booking_email.protocol is not None:
                    updates.append(f"booking_email_protocol = ${param_idx}")
                    params.append(data.booking_email.protocol)
                    param_idx += 1
                if data.booking_email.use_ssl is not None:
                    updates.append(f"booking_email_use_ssl = ${param_idx}")
                    params.append(data.booking_email.use_ssl)
                    param_idx += 1
            
            if data.stopsale_email:
                if data.stopsale_email.host is not None:
                    updates.append(f"stopsale_email_host = ${param_idx}")
                    params.append(data.stopsale_email.host)
                    param_idx += 1
                if data.stopsale_email.port is not None:
                    updates.append(f"stopsale_email_port = ${param_idx}")
                    params.append(data.stopsale_email.port)
                    param_idx += 1
                if data.stopsale_email.address is not None:
                    updates.append(f"stopsale_email_address = ${param_idx}")
                    params.append(data.stopsale_email.address)
                    param_idx += 1
                if data.stopsale_email.password:
                    updates.append(f"stopsale_email_password_encrypted = ${param_idx}")
                    params.append(encrypt_value(data.stopsale_email.password))
                    param_idx += 1
                if data.stopsale_email.protocol is not None:
                    updates.append(f"stopsale_email_protocol = ${param_idx}")
                    params.append(data.stopsale_email.protocol)
                    param_idx += 1
                if data.stopsale_email.use_ssl is not None:
                    updates.append(f"stopsale_email_use_ssl = ${param_idx}")
                    params.append(data.stopsale_email.use_ssl)
                    param_idx += 1
            
            if data.sedna:
                if data.sedna.api_url is not None:
                    updates.append(f"sedna_api_url = ${param_idx}")
                    params.append(data.sedna.api_url)
                    param_idx += 1
                if data.sedna.username is not None:
                    updates.append(f"sedna_username = ${param_idx}")
                    params.append(data.sedna.username)
                    param_idx += 1
                if data.sedna.password:
                    updates.append(f"sedna_password_encrypted = ${param_idx}")
                    params.append(encrypt_value(data.sedna.password))
                    param_idx += 1
                if data.sedna.operator_id is not None:
                    updates.append(f"sedna_operator_id = ${param_idx}")
                    params.append(data.sedna.operator_id)
                    param_idx += 1
                if data.sedna.operator_code is not None:
                    updates.append(f"sedna_operator_code = ${param_idx}")
                    params.append(data.sedna.operator_code)
                    param_idx += 1
                if data.sedna.authority_id is not None:
                    updates.append(f"sedna_authority_id = ${param_idx}")
                    params.append(data.sedna.authority_id)
                    param_idx += 1
            
            if data.processing:
                if data.processing.email_check_interval_seconds is not None:
                    updates.append(f"email_check_interval_seconds = ${param_idx}")
                    params.append(data.processing.email_check_interval_seconds)
                    param_idx += 1
                if data.processing.auto_process_enabled is not None:
                    updates.append(f"auto_process_enabled = ${param_idx}")
                    params.append(data.processing.auto_process_enabled)
                    param_idx += 1
                if data.processing.delete_after_fetch is not None:
                    updates.append(f"delete_after_fetch = ${param_idx}")
                    params.append(data.processing.delete_after_fetch)
                    param_idx += 1
            
            if data.microsoft_oauth:
                if data.microsoft_oauth.client_id is not None:
                    updates.append(f"microsoft_client_id = ${param_idx}")
                    params.append(data.microsoft_oauth.client_id)
                    param_idx += 1
                if data.microsoft_oauth.client_secret:
                    updates.append(f"microsoft_client_secret_encrypted = ${param_idx}")
                    params.append(encrypt_value(data.microsoft_oauth.client_secret))
                    param_idx += 1
                if data.microsoft_oauth.tenant_id is not None:
                    updates.append(f"microsoft_tenant_id = ${param_idx}")
                    params.append(data.microsoft_oauth.tenant_id)
                    param_idx += 1
            
            if data.google_oauth:
                if data.google_oauth.client_id is not None:
                    updates.append(f"google_client_id = ${param_idx}")
                    params.append(data.google_oauth.client_id)
                    param_idx += 1
                if data.google_oauth.client_secret:
                    updates.append(f"google_client_secret_encrypted = ${param_idx}")
                    params.append(encrypt_value(data.google_oauth.client_secret))
                    param_idx += 1
            
            if updates:
                updates.append("updated_at = NOW()")
                query = f"UPDATE tenant_settings SET {', '.join(updates)} WHERE tenant_id = $1"
                await conn.execute(query, *params)
            
            return await self.get_settings(tenant_id)
    
    async def get_decrypted_credentials(self, tenant_id: int) -> dict:
        """Get decrypted credentials for processing (internal use only)."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM tenant_settings WHERE tenant_id = $1",
                tenant_id,
            )
            
            if not row:
                return None
            
            return {
                "booking_email": {
                    "host": row["booking_email_host"],
                    "port": row["booking_email_port"] or 995,
                    "address": row["booking_email_address"],
                    "password": decrypt_value(row["booking_email_password_encrypted"]),
                    "protocol": row["booking_email_protocol"] or "pop3",
                    "use_ssl": row["booking_email_use_ssl"] if row["booking_email_use_ssl"] is not None else True,
                },
                "stopsale_email": {
                    "host": row["stopsale_email_host"],
                    "port": row["stopsale_email_port"] or 995,
                    "address": row["stopsale_email_address"],
                    "password": decrypt_value(row["stopsale_email_password_encrypted"]),
                    "protocol": row["stopsale_email_protocol"] or "pop3",
                    "use_ssl": row["stopsale_email_use_ssl"] if row["stopsale_email_use_ssl"] is not None else True,
                },
                "sedna": {
                    "api_url": row["sedna_api_url"],
                    "username": row["sedna_username"],
                    "password": decrypt_value(row["sedna_password_encrypted"]),
                    "operator_id": row["sedna_operator_id"],
                    "operator_code": row.get("sedna_operator_code"),
                    "authority_id": row.get("sedna_authority_id") or 207,
                },
            }
    
    async def test_email_connection(
        self,
        tenant_id: int,
        email_type: str,  # "booking" or "stopsale"
    ) -> ConnectionTestResult:
        """Test email connection with tenant credentials."""
        import poplib
        import ssl
        
        credentials = await self.get_decrypted_credentials(tenant_id)
        if not credentials:
            return ConnectionTestResult(
                success=False,
                message="Settings not configured",
            )
        
        email_config = credentials.get(f"{email_type}_email", {})
        
        if not email_config.get("host") or not email_config.get("address"):
            return ConnectionTestResult(
                success=False,
                message="Email not configured",
            )
        
        if not email_config.get("password"):
            return ConnectionTestResult(
                success=False,
                message="Password not set",
            )
        
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            if email_config["protocol"] == "pop3":
                server = poplib.POP3_SSL(
                    email_config["host"],
                    email_config["port"],
                    context=context,
                    timeout=15,
                )
                
                server.user(email_config["address"])
                server.pass_(email_config["password"])
                
                num_messages = len(server.list()[1])
                server.quit()
                
                return ConnectionTestResult(
                    success=True,
                    message="Connected successfully",
                    details={"message_count": num_messages},
                )
            else:
                # IMAP support can be added later
                return ConnectionTestResult(
                    success=False,
                    message="IMAP not yet supported",
                )
                
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=str(e),
            )
    
    async def test_sedna_connection(self, tenant_id: int) -> ConnectionTestResult:
        """Test Sedna API connection with tenant credentials."""
        import httpx
        
        credentials = await self.get_decrypted_credentials(tenant_id)
        if not credentials:
            return ConnectionTestResult(
                success=False,
                message="Settings not configured",
            )
        
        sedna = credentials.get("sedna", {})
        
        if not sedna.get("api_url") or not sedna.get("username"):
            return ConnectionTestResult(
                success=False,
                message="Sedna API not configured",
            )
        
        if not sedna.get("password"):
            return ConnectionTestResult(
                success=False,
                message="Password not set",
            )
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{sedna['api_url']}/api/Integratiion/AgencyLogin",
                    params={"username": sedna["username"], "password": sedna["password"]},
                    timeout=15,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ErrorType") == 0 and data.get("RecId"):
                        # Update operator_id if successful
                        async with self.pool.acquire() as conn:
                            await conn.execute(
                                "UPDATE tenant_settings SET sedna_operator_id = $1 WHERE tenant_id = $2",
                                str(data["RecId"]),  # Convert to string for VARCHAR column
                                tenant_id,
                            )
                        
                        return ConnectionTestResult(
                            success=True,
                            message="Connected successfully",
                            details={"operator_id": data["RecId"]},
                        )
                    else:
                        return ConnectionTestResult(
                            success=False,
                            message=data.get("Message", "Login failed"),
                        )
                else:
                    return ConnectionTestResult(
                        success=False,
                        message=f"HTTP {response.status_code}",
                    )
                    
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=str(e),
            )
