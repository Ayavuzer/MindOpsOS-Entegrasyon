"""POP3 email service with PostgreSQL storage."""

import asyncio
import email
import email.policy
import email.utils
import poplib
import ssl
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator, Callable, Awaitable
import hashlib

import asyncpg

from src.models.database import (
    EmailRecord,
    EmailStatus,
    EmailType,
    ProcessingLog,
    CREATE_TABLES_SQL,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class Pop3Config:
    """POP3 connection configuration."""
    
    host: str
    port: int
    username: str
    password: str
    use_ssl: bool = True
    verify_ssl: bool = False
    timeout: int = 30
    delete_after_fetch: bool = False  # Whether to delete emails after fetching


@dataclass
class DatabaseConfig:
    """PostgreSQL database configuration."""
    
    host: str = "localhost"
    port: int = 5432
    database: str = "mindops_entegrasyon"
    user: str = "postgres"
    password: str = ""
    min_connections: int = 2
    max_connections: int = 10


# =============================================================================
# Database Service
# =============================================================================


class DatabaseService:
    """
    PostgreSQL database service for email storage.
    
    Uses asyncpg for async PostgreSQL operations.
    """
    
    def __init__(self, config: DatabaseConfig):
        """Initialize database service."""
        self.config = config
        self._pool: asyncpg.Pool | None = None
    
    async def connect(self) -> None:
        """Create connection pool."""
        logger.info(
            "db_connecting",
            host=self.config.host,
            database=self.config.database,
        )
        
        self._pool = await asyncpg.create_pool(
            host=self.config.host,
            port=self.config.port,
            database=self.config.database,
            user=self.config.user,
            password=self.config.password,
            min_size=self.config.min_connections,
            max_size=self.config.max_connections,
        )
        
        logger.info("db_connected", status="success")
    
    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("db_disconnected")
    
    async def initialize_schema(self) -> None:
        """Create database tables if not exists."""
        async with self._pool.acquire() as conn:
            await conn.execute(CREATE_TABLES_SQL)
            logger.info("db_schema_initialized")
    
    @property
    def pool(self) -> asyncpg.Pool:
        """Get connection pool."""
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool
    
    # =========================================================================
    # Email Operations
    # =========================================================================
    
    async def email_exists(self, message_id: str) -> bool:
        """Check if email already exists in database."""
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM emails WHERE message_id = $1)",
                message_id,
            )
            return result
    
    async def save_email(self, email_record: EmailRecord) -> int:
        """
        Save email to database.
        
        Returns:
            Email ID
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO emails (
                    message_id, uid, subject, sender, recipients,
                    received_at, body_text, body_html, email_type, status,
                    has_pdf, pdf_filename, pdf_content, raw_headers
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (message_id) DO UPDATE SET
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
                """,
                email_record.message_id,
                email_record.uid,
                email_record.subject,
                email_record.sender,
                email_record.recipients,
                email_record.received_at,
                email_record.body_text,
                email_record.body_html,
                email_record.email_type.value,
                email_record.status.value,
                email_record.has_pdf,
                email_record.pdf_filename,
                email_record.pdf_content,
                email_record.raw_headers,
            )
            return row["id"]
    
    async def update_email_status(
        self,
        email_id: int,
        status: EmailStatus,
        error_message: str | None = None,
        sedna_rec_id: int | None = None,
        voucher_no: str | None = None,
    ) -> None:
        """Update email processing status."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE emails SET
                    status = $2,
                    error_message = $3,
                    sedna_rec_id = $4,
                    voucher_no = $5,
                    processed_at = CASE WHEN $2 IN ('processed', 'failed') THEN CURRENT_TIMESTAMP ELSE processed_at END,
                    retry_count = CASE WHEN $2 = 'failed' THEN retry_count + 1 ELSE retry_count END
                WHERE id = $1
                """,
                email_id,
                status.value,
                error_message,
                sedna_rec_id,
                voucher_no,
            )
    
    async def get_pending_emails(
        self,
        email_type: EmailType | None = None,
        limit: int = 50,
    ) -> list[EmailRecord]:
        """Get pending emails for processing."""
        async with self.pool.acquire() as conn:
            query = """
                SELECT * FROM emails
                WHERE status = 'pending'
            """
            params = []
            
            if email_type:
                query += " AND email_type = $1"
                params.append(email_type.value)
            
            query += f" ORDER BY received_at ASC LIMIT {limit}"
            
            rows = await conn.fetch(query, *params)
            
            return [self._row_to_email_record(row) for row in rows]
    
    async def get_email_by_id(self, email_id: int) -> EmailRecord | None:
        """Get email by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM emails WHERE id = $1",
                email_id,
            )
            if row:
                return self._row_to_email_record(row)
            return None
    
    def _row_to_email_record(self, row) -> EmailRecord:
        """Convert database row to EmailRecord."""
        return EmailRecord(
            id=row["id"],
            message_id=row["message_id"],
            uid=row["uid"],
            subject=row["subject"],
            sender=row["sender"],
            recipients=list(row["recipients"]) if row["recipients"] else [],
            received_at=row["received_at"],
            body_text=row["body_text"],
            body_html=row["body_html"],
            email_type=EmailType(row["email_type"]),
            status=EmailStatus(row["status"]),
            processed_at=row["processed_at"],
            error_message=row["error_message"],
            retry_count=row["retry_count"],
            has_pdf=row["has_pdf"],
            pdf_filename=row["pdf_filename"],
            pdf_content=row["pdf_content"],
            sedna_rec_id=row["sedna_rec_id"],
            voucher_no=row["voucher_no"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            raw_headers=row["raw_headers"],
        )
    
    # =========================================================================
    # Logging Operations
    # =========================================================================
    
    async def log_processing(
        self,
        email_id: int,
        action: str,
        status: str,
        message: str | None = None,
        details: dict | None = None,
    ) -> None:
        """Log processing attempt."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO processing_logs (email_id, action, status, message, details)
                VALUES ($1, $2, $3, $4, $5)
                """,
                email_id,
                action,
                status,
                message,
                details,
            )
    
    # =========================================================================
    # Reservation Operations
    # =========================================================================
    
    async def save_reservation(
        self,
        voucher_no: str,
        hotel_name: str,
        check_in,
        check_out,
        room_type: str,
        board_type: str,
        adults: int,
        children: int,
        guests: list,
        total_price=None,
        currency: str = "EUR",
        source_email_id: int | None = None,
    ) -> int:
        """Save reservation to database."""
        import json
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO reservations (
                    voucher_no, hotel_name, check_in, check_out,
                    room_type, board_type, adults, children,
                    guests, total_price, currency, source_email_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (voucher_no) DO UPDATE SET
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
                """,
                voucher_no,
                hotel_name,
                check_in,
                check_out,
                room_type,
                board_type,
                adults,
                children,
                json.dumps([g.dict() if hasattr(g, 'dict') else g for g in guests]),
                total_price,
                currency,
                source_email_id,
            )
            return row["id"]
    
    # =========================================================================
    # Stop Sale Operations
    # =========================================================================
    
    async def save_stop_sale(
        self,
        hotel_name: str,
        date_from,
        date_to,
        room_types: list[str] = None,
        board_types: list[str] = None,
        is_close: bool = True,
        reason: str | None = None,
        source_email_id: int | None = None,
        hotel_id: int | None = None,
    ) -> int:
        """Save stop sale to database."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO stop_sales (
                    hotel_name, hotel_id, date_from, date_to,
                    room_types, board_types, is_close, reason, source_email_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
                """,
                hotel_name,
                hotel_id,
                date_from,
                date_to,
                room_types or [],
                board_types or [],
                is_close,
                reason,
                source_email_id,
            )
            return row["id"]
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    async def get_stats(self) -> dict:
        """Get processing statistics."""
        async with self.pool.acquire() as conn:
            stats = {}
            
            # Email counts by status
            rows = await conn.fetch(
                "SELECT status, COUNT(*) as count FROM emails GROUP BY status"
            )
            stats["emails_by_status"] = {row["status"]: row["count"] for row in rows}
            
            # Total counts
            stats["total_emails"] = await conn.fetchval("SELECT COUNT(*) FROM emails")
            stats["total_reservations"] = await conn.fetchval("SELECT COUNT(*) FROM reservations")
            stats["total_stop_sales"] = await conn.fetchval("SELECT COUNT(*) FROM stop_sales")
            
            # Today's counts
            stats["emails_today"] = await conn.fetchval(
                "SELECT COUNT(*) FROM emails WHERE created_at >= CURRENT_DATE"
            )
            
            return stats


# =============================================================================
# POP3 Email Service
# =============================================================================


class Pop3EmailService:
    """
    POP3 email service with PostgreSQL storage.
    
    Fetches emails via POP3 and stores them in PostgreSQL for processing.
    """
    
    def __init__(
        self,
        pop3_config: Pop3Config,
        db_service: DatabaseService,
    ):
        """Initialize POP3 service."""
        self.config = pop3_config
        self.db = db_service
    
    async def fetch_and_store_emails(
        self,
        max_count: int = 50,
        classify: bool = True,
    ) -> dict:
        """
        Fetch emails from POP3 and store in database.
        
        Returns:
            Statistics dict
        """
        stats = {
            "fetched": 0,
            "new": 0,
            "skipped": 0,
            "errors": 0,
            "reservations": 0,
            "stop_sales": 0,
        }
        
        logger.info(
            "pop3_fetch_start",
            host=self.config.host,
            username=self.config.username,
        )
        
        try:
            # Connect to POP3
            if self.config.use_ssl:
                context = ssl.create_default_context()
                if not self.config.verify_ssl:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                
                server = poplib.POP3_SSL(
                    self.config.host,
                    self.config.port,
                    context=context,
                    timeout=self.config.timeout,
                )
            else:
                server = poplib.POP3(
                    self.config.host,
                    self.config.port,
                    timeout=self.config.timeout,
                )
            
            # Login
            server.user(self.config.username)
            server.pass_(self.config.password)
            
            logger.info("pop3_connected", status="success")
            
            # Get message count
            num_messages = len(server.list()[1])
            logger.info("pop3_messages_found", count=num_messages)
            
            # Fetch messages (newest first, limited)
            messages_to_fetch = min(num_messages, max_count)
            
            for i in range(num_messages, max(0, num_messages - messages_to_fetch), -1):
                try:
                    # Fetch email
                    response = server.retr(i)
                    raw_email = b"\n".join(response[1])
                    
                    # Parse email
                    msg = email.message_from_bytes(raw_email, policy=email.policy.default)
                    
                    # Get message ID or generate one
                    message_id = msg.get("Message-ID", "")
                    if not message_id:
                        # Generate from hash
                        message_id = f"<{hashlib.md5(raw_email[:500]).hexdigest()}@pop3>"
                    
                    stats["fetched"] += 1
                    
                    # Check if already exists
                    if await self.db.email_exists(message_id):
                        stats["skipped"] += 1
                        continue
                    
                    # Parse and store
                    email_record = await self._parse_and_store(msg, message_id, classify)
                    
                    if email_record:
                        stats["new"] += 1
                        
                        if email_record.email_type == EmailType.RESERVATION:
                            stats["reservations"] += 1
                        elif email_record.email_type == EmailType.STOPSALE:
                            stats["stop_sales"] += 1
                        
                        # Delete from server if configured
                        if self.config.delete_after_fetch:
                            server.dele(i)
                    
                except Exception as e:
                    logger.error("pop3_message_error", message_num=i, error=str(e))
                    stats["errors"] += 1
            
            # Quit (commits deletes if any)
            server.quit()
            
        except Exception as e:
            logger.error("pop3_fetch_error", error=str(e))
            raise
        
        logger.info("pop3_fetch_complete", stats=stats)
        return stats
    
    async def _parse_and_store(
        self,
        msg: email.message.Message,
        message_id: str,
        classify: bool = True,
    ) -> EmailRecord | None:
        """Parse email and store in database."""
        
        # Extract headers
        subject = msg.get("Subject", "")
        sender = msg.get("From", "")
        recipients = msg.get_all("To", [])
        date_str = msg.get("Date", "")
        
        # Parse date
        received_at = datetime.now()
        if date_str:
            try:
                received_at = email.utils.parsedate_to_datetime(date_str)
            except Exception:
                pass
        
        # Extract body
        body_text = ""
        body_html = None
        pdf_filename = None
        pdf_content = None
        has_pdf = False
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename and filename.lower().endswith(".pdf"):
                        has_pdf = True
                        pdf_filename = filename
                        pdf_content = part.get_payload(decode=True)
                elif content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode("utf-8", errors="ignore")
                elif content_type == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_html = payload.decode("utf-8", errors="ignore")
        else:
            content_type = msg.get_content_type()
            payload = msg.get_payload(decode=True)
            if payload:
                if content_type == "text/plain":
                    body_text = payload.decode("utf-8", errors="ignore")
                elif content_type == "text/html":
                    body_html = payload.decode("utf-8", errors="ignore")
        
        # Classify email
        email_type = EmailType.UNKNOWN
        if classify:
            email_type = self._classify_email(subject, body_text, has_pdf)
        
        # Build headers dict
        raw_headers = {key: str(value) for key, value in msg.items()}
        
        # Create record
        email_record = EmailRecord(
            message_id=message_id,
            subject=subject,
            sender=sender,
            recipients=recipients if isinstance(recipients, list) else [recipients],
            received_at=received_at,
            body_text=body_text,
            body_html=body_html,
            email_type=email_type,
            status=EmailStatus.PENDING,
            has_pdf=has_pdf,
            pdf_filename=pdf_filename,
            pdf_content=pdf_content,
            raw_headers=raw_headers,
        )
        
        # Save to database
        email_id = await self.db.save_email(email_record)
        email_record.id = email_id
        
        logger.info(
            "email_stored",
            id=email_id,
            subject=subject[:50],
            email_type=email_type.value,
            has_pdf=has_pdf,
        )
        
        return email_record
    
    def _classify_email(self, subject: str, body: str, has_pdf: bool) -> EmailType:
        """Classify email type based on content."""
        text = f"{subject} {body}".lower()
        
        # Stop sale keywords
        stop_sale_keywords = [
            "stop sale", "stopsale", "stop-sale",
            "satış durdurma", "closed", "unavailable",
            "sold out", "blackout",
        ]
        
        for keyword in stop_sale_keywords:
            if keyword in text:
                return EmailType.STOPSALE
        
        # Reservation keywords (must have PDF)
        if has_pdf:
            reservation_keywords = [
                "reservation", "booking", "confirmation", "voucher",
                "rezervasyon", "onay", "juniper", "travel",
            ]
            
            for keyword in reservation_keywords:
                if keyword in text:
                    return EmailType.RESERVATION
        
        return EmailType.UNKNOWN


# =============================================================================
# Factory Functions
# =============================================================================


async def create_pop3_service(
    pop3_host: str,
    pop3_port: int,
    pop3_username: str,
    pop3_password: str,
    db_host: str = "localhost",
    db_port: int = 5432,
    db_name: str = "mindops_entegrasyon",
    db_user: str = "postgres",
    db_password: str = "",
) -> tuple[Pop3EmailService, DatabaseService]:
    """
    Create and initialize POP3 email service with database.
    
    Returns:
        Tuple of (Pop3EmailService, DatabaseService)
    """
    # Create configs
    pop3_config = Pop3Config(
        host=pop3_host,
        port=pop3_port,
        username=pop3_username,
        password=pop3_password,
    )
    
    db_config = DatabaseConfig(
        host=db_host,
        port=db_port,
        database=db_name,
        user=db_user,
        password=db_password,
    )
    
    # Initialize database
    db_service = DatabaseService(db_config)
    await db_service.connect()
    await db_service.initialize_schema()
    
    # Create POP3 service
    pop3_service = Pop3EmailService(pop3_config, db_service)
    
    return pop3_service, db_service
