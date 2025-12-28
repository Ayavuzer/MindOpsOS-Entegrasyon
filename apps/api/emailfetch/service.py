"""Tenant-aware email fetch service."""

import poplib
import ssl
import email as email_lib
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

import asyncpg

from tenant.service import TenantSettingsService


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
        Fetch emails for a tenant from their configured POP3 server.
        
        Args:
            tenant_id: Tenant ID
            email_type: "booking" or "stopsale"
            
        Returns:
            FetchResult with stats
        """
        # Get decrypted credentials
        credentials = await self.settings_service.get_decrypted_credentials(tenant_id)
        
        if not credentials:
            return FetchResult(
                success=False,
                message="Settings not configured",
            )
        
        email_config = credentials.get(f"{email_type}_email", {})
        
        if not email_config.get("host") or not email_config.get("address"):
            return FetchResult(
                success=False,
                message=f"{email_type.title()} email not configured",
            )
        
        if not email_config.get("password"):
            return FetchResult(
                success=False,
                message="Password not set",
            )
        
        # Connect to POP3
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            server = poplib.POP3_SSL(
                email_config["host"],
                email_config.get("port", 995),
                context=context,
                timeout=30,
            )
            
            server.user(email_config["address"])
            server.pass_(email_config["password"])
            
            # Get message list
            num_messages = len(server.list()[1])
            
            if num_messages == 0:
                server.quit()
                return FetchResult(
                    success=True,
                    message="No new emails",
                    emails_fetched=0,
                )
            
            result = FetchResult(
                success=True,
                message="Fetch completed",
                emails_fetched=num_messages,
            )
            
            # Fetch each email
            for i in range(1, num_messages + 1):
                try:
                    # Get email content
                    response, lines, octets = server.retr(i)
                    raw_email = b"\n".join(lines)
                    
                    # Parse email
                    msg = email_lib.message_from_bytes(raw_email, policy=email_lib.policy.default)
                    
                    # Get message ID
                    message_id = msg.get("Message-ID", f"<no-id-{i}-{datetime.now().timestamp()}>")
                    
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
                        if date_str:
                            try:
                                received_at = email_lib.utils.parsedate_to_datetime(date_str)
                            except:
                                received_at = datetime.now()
                        else:
                            received_at = datetime.now()
                        
                        # Get body
                        body_text = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body_text = part.get_content()
                                    break
                        else:
                            body_text = msg.get_content() if msg.get_content_type() == "text/plain" else ""
                        
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
                    result.errors.append(f"Email {i}: {str(e)}")
            
            server.quit()
            
            result.message = f"Fetched {result.emails_new} new emails, {result.emails_skipped} skipped"
            return result
            
        except Exception as e:
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
