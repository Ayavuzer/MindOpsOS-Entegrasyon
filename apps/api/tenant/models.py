"""Pydantic models for tenant settings."""

from typing import Optional
from pydantic import BaseModel


class EmailConfig(BaseModel):
    """Email server configuration."""
    
    host: Optional[str] = None
    port: int = 995
    address: Optional[str] = None
    password: Optional[str] = None  # Only used for input, never returned
    protocol: str = "pop3"  # pop3 or imap
    use_ssl: bool = True


class SednaConfig(BaseModel):
    """Sedna API configuration."""
    
    api_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None  # Only used for input, never returned
    operator_id: Optional[int] = None


class ProcessingConfig(BaseModel):
    """Processing settings."""
    
    email_check_interval_seconds: int = 60
    auto_process_enabled: bool = True
    delete_after_fetch: bool = False


class TenantSettingsResponse(BaseModel):
    """Tenant settings response (no passwords)."""
    
    booking_email: EmailConfig
    stopsale_email: EmailConfig
    sedna: SednaConfig
    processing: ProcessingConfig
    has_booking_password: bool = False
    has_stopsale_password: bool = False
    has_sedna_password: bool = False


class TenantSettingsUpdate(BaseModel):
    """Tenant settings update request."""
    
    booking_email: Optional[EmailConfig] = None
    stopsale_email: Optional[EmailConfig] = None
    sedna: Optional[SednaConfig] = None
    processing: Optional[ProcessingConfig] = None


class ConnectionTestResult(BaseModel):
    """Connection test result."""
    
    success: bool
    message: str
    details: Optional[dict] = None
