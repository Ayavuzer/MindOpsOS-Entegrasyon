"""Tenant-aware email fetch service with OAuth support."""

import imaplib
import socket
import ssl
import email as email_lib
from email import policy as email_policy
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

import asyncpg

from tenant.service import TenantSettingsService
from tenant.encryption import decrypt_value

# Set default socket timeout for IMAP operations
socket.setdefaulttimeout(30)


@dataclass
class FetchResult:
    """Result of email fetch operation."""
    
    success: bool
    message: str
    emails_fetched: int = 0
    emails_new: int = 0
    emails_skipped: int = 0
    errors: list[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class TenantEmailService:
    """Tenant-aware email fetch service."""
    
    def __init__(self, pool: asyncpg.Pool, settings_service: TenantSettingsService):
        self.pool = pool
        self.settings_service = settings_service
    
    async def fetch_emails(
        self,
        tenant_id: int,
        email_type: str = "booking",  # "booking" or "stopsale"
    ) -> FetchResult:
        """
        Fetch emails for a tenant using IMAP (supports OAuth2).
        
        Args:
            tenant_id: Tenant ID
            email_type: "booking" or "stopsale"
            
        Returns:
            FetchResult with stats
        """
        # Get email configuration including OAuth
        config = await self._get_email_config(tenant_id, email_type)
        
        if not config:
            return FetchResult(
                success=False,
                message=f"{email_type.title()} email not configured",
            )
        
        if config.get("auth_method") == "oauth2":
            return await self._fetch_with_oauth(tenant_id, email_type, config)
        else:
            return await self._fetch_with_password(tenant_id, email_type, config)
    
    async def _get_email_config(self, tenant_id: int, email_type: str) -> Optional[dict]:
        """Get email configuration from database."""
        prefix = email_type
        oauth_prefix = f"{email_type}_oauth"
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT 
                    {prefix}_email_host,
                    {prefix}_email_port,
                    {prefix}_email_address,
                    {prefix}_email_password_encrypted,
                    {prefix}_email_use_ssl,
                    {prefix}_auth_method,
                    {oauth_prefix}_access_token_encrypted,
                    {oauth_prefix}_refresh_token_encrypted,
                    {oauth_prefix}_connected_email,
                    {oauth_prefix}_provider
                FROM tenant_settings
                WHERE tenant_id = $1
                """,
                tenant_id,
            )
        
        if not row or not row[f"{prefix}_email_host"]:
            return None
        
        return {
            "host": row[f"{prefix}_email_host"],
            "port": row[f"{prefix}_email_port"] or 993,
            "address": row[f"{prefix}_email_address"],
            "password_encrypted": row[f"{prefix}_email_password_encrypted"],
            "use_ssl": row[f"{prefix}_email_use_ssl"] if row[f"{prefix}_email_use_ssl"] is not None else True,
            "auth_method": row[f"{prefix}_auth_method"] or "password",
            "access_token_encrypted": row[f"{oauth_prefix}_access_token_encrypted"],
            "refresh_token_encrypted": row[f"{oauth_prefix}_refresh_token_encrypted"],
            "connected_email": row[f"{oauth_prefix}_connected_email"],
            "provider": row[f"{oauth_prefix}_provider"],
        }
    
    async def _refresh_oauth_token(self, tenant_id: int, email_type: str, config: dict) -> Optional[str]:
        """Refresh OAuth token if needed and return access token."""
        from oauth.service import OAuthService
        
        oauth_service = OAuthService(self.pool)
        provider = config.get("provider", "google")
        
        # Refresh token
        if provider == "microsoft":
            await oauth_service.refresh_microsoft_token(tenant_id, email_type)
        else:
            await oauth_service.refresh_google_token(tenant_id, email_type)
        
        # Get fresh access token
        return await oauth_service.get_decrypted_access_token(tenant_id, email_type)
    
    async def _fetch_with_oauth(self, tenant_id: int, email_type: str, config: dict) -> FetchResult:
        """Fetch emails using OAuth2 authentication."""
        
        # Refresh and get access token
        access_token = await self._refresh_oauth_token(tenant_id, email_type, config)
        
        if not access_token:
            return FetchResult(
                success=False,
                message="OAuth token not available - please reconnect",
            )
        
        email_address = config.get("connected_email") or config.get("address")
        if not email_address:
            return FetchResult(
                success=False,
                message="No email address configured",
            )
        
        # Connect to IMAP with OAuth
        try:
            context = ssl.create_default_context()
            
            imap = imaplib.IMAP4_SSL(
                config["host"],
                config.get("port", 993),
                ssl_context=context,
            )
            
            # XOAUTH2 authentication
            auth_string = f"user={email_address}\x01auth=Bearer {access_token}\x01\x01"
            imap.authenticate("XOAUTH2", lambda x: auth_string.encode())
            
            # Fetch emails
            return await self._process_imap_emails(imap, tenant_id, email_type)
            
        except imaplib.IMAP4.error as e:
            return FetchResult(
                success=False,
                message=f"IMAP OAuth error: {e}",
            )
        except Exception as e:
            return FetchResult(
                success=False,
                message=str(e),
            )
    
    async def _fetch_with_password(self, tenant_id: int, email_type: str, config: dict) -> FetchResult:
        """Fetch emails using password authentication."""
        
        password = decrypt_value(config["password_encrypted"]) if config.get("password_encrypted") else None
        
        if not password:
            return FetchResult(
                success=False,
                message="Password not set",
            )
        
        # Connect to IMAP with password
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            if config.get("use_ssl", True):
                imap = imaplib.IMAP4_SSL(
                    config["host"],
                    config.get("port", 993),
                    ssl_context=context,
                )
            else:
                imap = imaplib.IMAP4(
                    config["host"],
                    config.get("port", 143),
                )
            
            imap.login(config["address"], password)
            
            # Fetch emails
            return await self._process_imap_emails(imap, tenant_id, email_type)
            
        except imaplib.IMAP4.error as e:
            return FetchResult(
                success=False,
                message=f"IMAP error: {e}",
            )
        except Exception as e:
            return FetchResult(
                success=False,
                message=str(e),
            )
    
    async def _process_imap_emails(self, imap: imaplib.IMAP4, tenant_id: int, email_type: str) -> FetchResult:
        """Process emails from IMAP connection."""
        try:
            # Select inbox
            imap.select("INBOX")
            
            # Search for emails from the last 7 days only
            # Note: We don't filter by UNSEEN because Gmail marks emails as seen on sync
            from datetime import timedelta
            since_date = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
            
            # Search for all emails from the last 7 days (we'll dedupe by message_id in processing)
            _, message_nums = imap.search(None, f'SINCE {since_date}')
            message_list = message_nums[0].split()
            
            if not message_list:
                imap.logout()
                return FetchResult(
                    success=True,
                    message="No emails in the last 7 days",
                    emails_fetched=0,
                )
            
            # Limit to last 100 emails per batch to prevent timeout
            max_emails = 100
            if len(message_list) > max_emails:
                message_list = message_list[-max_emails:]  # Get the most recent ones
            
            result = FetchResult(
                success=True,
                message="Fetch completed",
                emails_fetched=len(message_list),
            )
            
            for num in message_list:
                try:
                    # Fetch email
                    _, msg_data = imap.fetch(num, "(RFC822)")
                    raw_email = msg_data[0][1]
                    
                    # Parse email
                    msg = email_lib.message_from_bytes(raw_email, policy=email_policy.default)
                    
                    # Get message ID
                    message_id = msg.get("Message-ID", f"<no-id-{num}-{datetime.now().timestamp()}>")
                    
                    # Check if already exists
                    async with self.pool.acquire() as conn:
                        existing = await conn.fetchval(
                            "SELECT id FROM emails WHERE message_id = $1 AND tenant_id = $2",
                            message_id,
                            tenant_id,
                        )
                        
                        if existing:
                            result.emails_skipped += 1
                            continue
                        
                        # Parse email details
                        subject = msg.get("Subject", "")
                        sender = msg.get("From", "")
                        recipients = msg.get("To", "").split(",")
                        date_str = msg.get("Date")
                        
                        # Parse date
                        received_at = datetime.now()
                        if date_str:
                            try:
                                received_at = email_lib.utils.parsedate_to_datetime(date_str)
                            except:
                                pass
                        
                        # Get body (improved to handle multipart, HTML, and forwarded emails)
                        body_text = ""
                        html_body = ""
                        
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                
                                # Skip attachments
                                if part.get_content_disposition() == "attachment":
                                    continue
                                
                                try:
                                    if content_type == "text/plain" and not body_text:
                                        content = part.get_content()
                                        if isinstance(content, str):
                                            body_text = content
                                    
                                    elif content_type == "text/html" and not html_body:
                                        content = part.get_content()
                                        if isinstance(content, str):
                                            html_body = content
                                    
                                    # Handle forwarded emails (nested message/rfc822)
                                    elif content_type == "message/rfc822":
                                        nested_msg = part.get_content()
                                        if hasattr(nested_msg, 'get_content'):
                                            nested_content = nested_msg.get_content()
                                            if isinstance(nested_content, str):
                                                if not body_text:
                                                    body_text = nested_content
                                except Exception:
                                    pass
                        else:
                            try:
                                content = msg.get_content()
                                if msg.get_content_type() == "text/plain":
                                    body_text = content if isinstance(content, str) else ""
                                elif msg.get_content_type() == "text/html":
                                    html_body = content if isinstance(content, str) else ""
                            except Exception:
                                pass
                        
                        # If no plain text, extract from HTML
                        if not body_text and html_body:
                            import re
                            # Remove HTML tags to get plain text
                            body_text = re.sub('<[^<]+?>', ' ', html_body)
                            body_text = re.sub(r'\s+', ' ', body_text).strip()
                        
                        # Check for PDF
                        has_pdf = False
                        pdf_filename = None
                        pdf_content = None
                        
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "application/pdf":
                                    has_pdf = True
                                    pdf_filename = part.get_filename()
                                    pdf_content = part.get_payload(decode=True)
                                    break
                        
                        # Classify email type
                        detected_type = self._classify_email(subject, body_text, has_pdf)
                        
                        # Save to database
                        await conn.execute(
                            """
                            INSERT INTO emails (
                                tenant_id, message_id, subject, sender, recipients,
                                received_at, body_text, email_type, status,
                                has_pdf, pdf_filename, pdf_content, created_at
                            ) VALUES (
                                $1, $2, $3, $4, $5, $6, $7, $8, 'pending',
                                $9, $10, $11, NOW()
                            )
                            """,
                            tenant_id, message_id, subject, sender, recipients,
                            received_at, body_text, detected_type,
                            has_pdf, pdf_filename, pdf_content,
                        )
                        
                        result.emails_new += 1
                        
                except Exception as e:
                    result.errors.append(f"Email {num}: {str(e)}")
            
            imap.logout()
            
            result.message = f"Fetched {result.emails_new} new emails, {result.emails_skipped} skipped"
            return result
            
        except Exception as e:
            try:
                imap.logout()
            except:
                pass
            return FetchResult(
                success=False,
                message=str(e),
            )
    
    def _classify_email(self, subject: str, body: str, has_pdf: bool) -> str:
        """Classify email type based on content."""
        subject_lower = subject.lower() if subject else ""
        body_lower = body.lower() if body else ""
        
        # Check for booking indicators
        booking_indicators = [
            "reservation", "booking", "voucher", "confirmation",
            "rezervasyon", "onay", "konaklama"
        ]
        
        for indicator in booking_indicators:
            if indicator in subject_lower or indicator in body_lower:
                return "booking"
        
        # Check for stop sale indicators
        stopsale_indicators = [
            "stop sale", "stopsale", "stop-sale", "availability",
            "close out", "closeout", "block", "satış durdur"
        ]
        
        for indicator in stopsale_indicators:
            if indicator in subject_lower or indicator in body_lower:
                return "stopsale"
        
        # Default based on PDF presence
        if has_pdf:
            return "booking"
        
        return "unknown"
