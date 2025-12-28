"""Email service for IMAP-based email fetching and processing."""

import asyncio
import email
import email.policy
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import AsyncIterator, Callable, Awaitable
import imaplib
import ssl

from pydantic import BaseModel

from src.utils.logger import get_logger, mask_sensitive

logger = get_logger(__name__)


# =============================================================================
# Data Models
# =============================================================================


class EmailAttachment(BaseModel):
    """Email attachment data."""

    filename: str
    content_type: str
    size: int
    content: bytes

    class Config:
        arbitrary_types_allowed = True


class EmailMessage(BaseModel):
    """Parsed email message."""

    message_id: str
    uid: str
    subject: str
    sender: str
    recipients: list[str]
    date: datetime | None
    body_text: str
    body_html: str | None
    attachments: list[EmailAttachment]
    raw_headers: dict[str, str]

    class Config:
        arbitrary_types_allowed = True

    @property
    def has_pdf_attachment(self) -> bool:
        """Check if email has PDF attachment."""
        return any(
            att.filename.lower().endswith(".pdf") or att.content_type == "application/pdf"
            for att in self.attachments
        )

    @property
    def pdf_attachments(self) -> list[EmailAttachment]:
        """Get PDF attachments only."""
        return [
            att
            for att in self.attachments
            if att.filename.lower().endswith(".pdf") or att.content_type == "application/pdf"
        ]


@dataclass
class EmailConnectionConfig:
    """Email connection configuration."""

    host: str
    port: int
    username: str
    password: str
    use_ssl: bool = True
    verify_ssl: bool = False  # Disable SSL verification for self-signed certs
    folder: str = "INBOX"
    timeout: int = 30


@dataclass
class EmailFetchResult:
    """Result of email fetch operation."""

    success: bool
    emails: list[EmailMessage] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    total_fetched: int = 0
    total_failed: int = 0


# =============================================================================
# Email Service
# =============================================================================


class EmailService:
    """
    IMAP email service for fetching and processing emails.

    Usage:
        config = EmailConnectionConfig(
            host="imap.gmail.com",
            port=993,
            username="booking@example.com",
            password="password"
        )

        service = EmailService(config)
        async for email in service.fetch_unread_emails():
            print(f"Subject: {email.subject}")
            await service.mark_as_read(email.uid)
    """

    def __init__(self, config: EmailConnectionConfig):
        """
        Initialize email service.

        Args:
            config: Email connection configuration
        """
        self.config = config
        self._connection: imaplib.IMAP4_SSL | imaplib.IMAP4 | None = None

    def _connect(self) -> imaplib.IMAP4_SSL | imaplib.IMAP4:
        """
        Establish IMAP connection.

        Returns:
            IMAP connection object
        """
        logger.info(
            "email_connecting",
            host=self.config.host,
            port=self.config.port,
            username=self.config.username,
        )

        try:
            if self.config.use_ssl:
                context = ssl.create_default_context()
                
                # Disable SSL verification if configured
                if not self.config.verify_ssl:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                
                connection = imaplib.IMAP4_SSL(
                    host=self.config.host,
                    port=self.config.port,
                    ssl_context=context,
                    timeout=self.config.timeout,
                )
            else:
                connection = imaplib.IMAP4(
                    host=self.config.host,
                    port=self.config.port,
                    timeout=self.config.timeout,
                )

            # Login
            connection.login(self.config.username, self.config.password)
            logger.info("email_connected", status="success")

            # Select folder
            connection.select(self.config.folder)

            return connection

        except imaplib.IMAP4.error as e:
            logger.error("email_connection_failed", error=str(e))
            raise EmailConnectionError(f"IMAP connection failed: {e}") from e
        except Exception as e:
            logger.error("email_connection_error", error=str(e))
            raise EmailConnectionError(f"Connection error: {e}") from e

    def _disconnect(self) -> None:
        """Close IMAP connection."""
        if self._connection:
            try:
                self._connection.close()
                self._connection.logout()
            except Exception as e:
                logger.warning("email_disconnect_error", error=str(e))
            finally:
                self._connection = None

    @property
    def connection(self) -> imaplib.IMAP4_SSL | imaplib.IMAP4:
        """Get or create IMAP connection."""
        if self._connection is None:
            self._connection = self._connect()
        return self._connection

    def reconnect(self) -> None:
        """Force reconnection."""
        self._disconnect()
        self._connection = self._connect()

    async def fetch_unread_emails(
        self,
        max_count: int = 50,
        search_criteria: str = "UNSEEN",
    ) -> AsyncIterator[EmailMessage]:
        """
        Fetch unread emails from the mailbox.

        Args:
            max_count: Maximum number of emails to fetch
            search_criteria: IMAP search criteria (default: UNSEEN)

        Yields:
            EmailMessage objects
        """
        logger.info(
            "email_fetch_start",
            criteria=search_criteria,
            max_count=max_count,
        )

        try:
            # Run IMAP operations in thread pool (blocking I/O)
            loop = asyncio.get_event_loop()
            
            # Search for emails
            _, message_numbers = await loop.run_in_executor(
                None,
                lambda: self.connection.search(None, search_criteria)
            )

            if not message_numbers[0]:
                logger.info("email_fetch_empty", message="No emails found")
                return

            email_ids = message_numbers[0].split()
            email_ids = email_ids[:max_count]  # Limit

            logger.info("email_fetch_found", count=len(email_ids))

            for email_id in email_ids:
                try:
                    email_msg = await self._fetch_single_email(email_id)
                    if email_msg:
                        yield email_msg
                except Exception as e:
                    logger.error(
                        "email_fetch_single_error",
                        email_id=email_id.decode(),
                        error=str(e),
                    )

        except Exception as e:
            logger.error("email_fetch_error", error=str(e))
            raise EmailFetchError(f"Failed to fetch emails: {e}") from e

    async def _fetch_single_email(self, email_id: bytes) -> EmailMessage | None:
        """
        Fetch and parse a single email.

        Args:
            email_id: IMAP email ID

        Returns:
            Parsed EmailMessage or None
        """
        loop = asyncio.get_event_loop()

        # Fetch email data
        _, msg_data = await loop.run_in_executor(
            None,
            lambda: self.connection.fetch(email_id, "(RFC822 UID)")
        )

        if not msg_data or not msg_data[0]:
            return None

        # Parse email
        raw_email = msg_data[0][1]
        if isinstance(raw_email, bytes):
            msg = email.message_from_bytes(raw_email, policy=email.policy.default)
        else:
            return None

        # Extract UID
        uid = ""
        if len(msg_data) > 1 and msg_data[1]:
            uid_data = msg_data[0][0].decode()
            if "UID" in uid_data:
                uid = uid_data.split("UID")[1].strip().rstrip(")")

        # Parse message
        return self._parse_email(msg, uid or email_id.decode())

    def _parse_email(self, msg: email.message.Message, uid: str) -> EmailMessage:
        """
        Parse email message into EmailMessage object.

        Args:
            msg: Raw email message
            uid: Email UID

        Returns:
            Parsed EmailMessage
        """
        # Extract headers
        message_id = msg.get("Message-ID", "")
        subject = msg.get("Subject", "")
        sender = msg.get("From", "")
        recipients = msg.get_all("To", [])
        date_str = msg.get("Date", "")

        # Parse date
        parsed_date = None
        if date_str:
            try:
                parsed_date = email.utils.parsedate_to_datetime(date_str)
            except Exception:
                pass

        # Extract body
        body_text = ""
        body_html = None

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" not in content_disposition:
                    if content_type == "text/plain":
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

        # Extract attachments
        attachments = self._extract_attachments(msg)

        # Build headers dict
        raw_headers = {key: str(value) for key, value in msg.items()}

        return EmailMessage(
            message_id=message_id,
            uid=uid,
            subject=subject,
            sender=sender,
            recipients=recipients if isinstance(recipients, list) else [recipients],
            date=parsed_date,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
            raw_headers=raw_headers,
        )

    def _extract_attachments(self, msg: email.message.Message) -> list[EmailAttachment]:
        """
        Extract attachments from email.

        Args:
            msg: Email message

        Returns:
            List of EmailAttachment objects
        """
        attachments = []

        if not msg.is_multipart():
            return attachments

        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))

            if "attachment" in content_disposition:
                filename = part.get_filename() or "unnamed"
                content_type = part.get_content_type()
                payload = part.get_payload(decode=True)

                if payload:
                    attachments.append(
                        EmailAttachment(
                            filename=filename,
                            content_type=content_type,
                            size=len(payload),
                            content=payload,
                        )
                    )

        return attachments

    async def mark_as_read(self, uid: str) -> bool:
        """
        Mark email as read (seen).

        Args:
            uid: Email UID

        Returns:
            True if successful
        """
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.connection.store(uid.encode(), "+FLAGS", "\\Seen")
            )
            logger.debug("email_marked_read", uid=uid)
            return True
        except Exception as e:
            logger.error("email_mark_read_error", uid=uid, error=str(e))
            return False

    async def mark_as_processed(self, uid: str, label: str = "Processed") -> bool:
        """
        Mark email with a custom label/flag.

        Args:
            uid: Email UID
            label: Label to add

        Returns:
            True if successful
        """
        try:
            loop = asyncio.get_event_loop()
            # Gmail uses X-GM-LABELS for labels
            await loop.run_in_executor(
                None,
                lambda: self.connection.store(uid.encode(), "+FLAGS", f"({label})")
            )
            logger.debug("email_labeled", uid=uid, label=label)
            return True
        except Exception as e:
            logger.warning("email_label_error", uid=uid, label=label, error=str(e))
            return False

    async def move_to_folder(self, uid: str, folder: str) -> bool:
        """
        Move email to another folder.

        Args:
            uid: Email UID
            folder: Target folder name

        Returns:
            True if successful
        """
        try:
            loop = asyncio.get_event_loop()

            # Copy to new folder
            await loop.run_in_executor(
                None,
                lambda: self.connection.copy(uid.encode(), folder)
            )

            # Delete from current folder
            await loop.run_in_executor(
                None,
                lambda: self.connection.store(uid.encode(), "+FLAGS", "\\Deleted")
            )

            # Expunge
            await loop.run_in_executor(
                None,
                lambda: self.connection.expunge()
            )

            logger.info("email_moved", uid=uid, folder=folder)
            return True
        except Exception as e:
            logger.error("email_move_error", uid=uid, folder=folder, error=str(e))
            return False

    async def save_attachment(
        self,
        attachment: EmailAttachment,
        save_path: str | Path,
    ) -> Path:
        """
        Save attachment to file.

        Args:
            attachment: EmailAttachment object
            save_path: Directory to save to

        Returns:
            Path to saved file
        """
        save_dir = Path(save_path)
        save_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{attachment.filename}"
        file_path = save_dir / filename

        # Write file
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: file_path.write_bytes(attachment.content)
        )

        logger.info(
            "attachment_saved",
            filename=filename,
            size=attachment.size,
            path=str(file_path),
        )

        return file_path

    def get_folder_list(self) -> list[str]:
        """Get list of available folders."""
        _, folders = self.connection.list()
        folder_names = []
        for folder in folders:
            if folder:
                # Parse folder response
                parts = folder.decode().split('"')
                if len(parts) >= 2:
                    folder_names.append(parts[-2])
        return folder_names

    def close(self) -> None:
        """Close the connection."""
        self._disconnect()


# =============================================================================
# Email Classifier
# =============================================================================


class EmailClassifier:
    """
    Classify emails as reservation or stop sale based on content.
    """

    # Keywords for classification
    RESERVATION_KEYWORDS = [
        "reservation",
        "booking",
        "confirmation",
        "voucher",
        "rezervasyon",
        "onay",
        "juniper",
        "travel",
        "hotel",
    ]

    STOP_SALE_KEYWORDS = [
        "stop sale",
        "stopsale",
        "stop-sale",
        "satış durdurma",
        "closed",
        "unavailable",
        "no availability",
        "sold out",
        "full",
        "close out",
        "blackout",
    ]

    @classmethod
    def classify(cls, email_msg: EmailMessage) -> str:
        """
        Classify email as 'reservation', 'stopsale', or 'unknown'.

        Args:
            email_msg: Email message to classify

        Returns:
            Classification string
        """
        # Combine subject and body for analysis
        text = f"{email_msg.subject} {email_msg.body_text}".lower()

        # Check for stop sale first (more specific)
        for keyword in cls.STOP_SALE_KEYWORDS:
            if keyword.lower() in text:
                logger.debug(
                    "email_classified",
                    subject=email_msg.subject[:50],
                    classification="stopsale",
                    keyword=keyword,
                )
                return "stopsale"

        # Check for reservation
        for keyword in cls.RESERVATION_KEYWORDS:
            if keyword.lower() in text:
                # Additional check: must have PDF for reservation
                if email_msg.has_pdf_attachment:
                    logger.debug(
                        "email_classified",
                        subject=email_msg.subject[:50],
                        classification="reservation",
                        keyword=keyword,
                    )
                    return "reservation"

        logger.debug(
            "email_classified",
            subject=email_msg.subject[:50],
            classification="unknown",
        )
        return "unknown"


# =============================================================================
# Exceptions
# =============================================================================


class EmailError(Exception):
    """Base exception for email operations."""

    pass


class EmailConnectionError(EmailError):
    """Connection error."""

    pass


class EmailFetchError(EmailError):
    """Fetch error."""

    pass


class EmailProcessingError(EmailError):
    """Processing error."""

    pass


# =============================================================================
# Email Processor
# =============================================================================


class EmailProcessor:
    """
    High-level email processor for batch operations.
    """

    def __init__(
        self,
        booking_config: EmailConnectionConfig,
        stopsale_config: EmailConnectionConfig,
        attachment_dir: str | Path = "/tmp/mindops-entegrasyon/attachments",
    ):
        """
        Initialize email processor.

        Args:
            booking_config: Configuration for booking email
            stopsale_config: Configuration for stop sale email
            attachment_dir: Directory to save attachments
        """
        self.booking_service = EmailService(booking_config)
        self.stopsale_service = EmailService(stopsale_config)
        self.attachment_dir = Path(attachment_dir)
        self.classifier = EmailClassifier()

    async def process_booking_emails(
        self,
        handler: Callable[[EmailMessage, Path | None], Awaitable[bool]],
        max_count: int = 50,
    ) -> EmailFetchResult:
        """
        Process booking emails.

        Args:
            handler: Async callback for each email (email, pdf_path) -> success
            max_count: Maximum emails to process

        Returns:
            EmailFetchResult with statistics
        """
        result = EmailFetchResult(success=True)

        try:
            async for email_msg in self.booking_service.fetch_unread_emails(max_count):
                try:
                    # Save PDF if present
                    pdf_path = None
                    if email_msg.has_pdf_attachment:
                        pdf = email_msg.pdf_attachments[0]
                        pdf_path = await self.booking_service.save_attachment(
                            pdf,
                            self.attachment_dir / "bookings",
                        )

                    # Call handler
                    success = await handler(email_msg, pdf_path)

                    if success:
                        await self.booking_service.mark_as_read(email_msg.uid)
                        result.total_fetched += 1
                        result.emails.append(email_msg)
                    else:
                        result.total_failed += 1
                        result.errors.append(f"Handler failed for {email_msg.subject}")

                except Exception as e:
                    result.total_failed += 1
                    result.errors.append(str(e))
                    logger.error("email_process_error", subject=email_msg.subject, error=str(e))

        except Exception as e:
            result.success = False
            result.errors.append(str(e))

        finally:
            self.booking_service.close()

        return result

    async def process_stopsale_emails(
        self,
        handler: Callable[[EmailMessage], Awaitable[bool]],
        max_count: int = 50,
    ) -> EmailFetchResult:
        """
        Process stop sale emails.

        Args:
            handler: Async callback for each email -> success
            max_count: Maximum emails to process

        Returns:
            EmailFetchResult with statistics
        """
        result = EmailFetchResult(success=True)

        try:
            async for email_msg in self.stopsale_service.fetch_unread_emails(max_count):
                try:
                    # Call handler
                    success = await handler(email_msg)

                    if success:
                        await self.stopsale_service.mark_as_read(email_msg.uid)
                        result.total_fetched += 1
                        result.emails.append(email_msg)
                    else:
                        result.total_failed += 1
                        result.errors.append(f"Handler failed for {email_msg.subject}")

                except Exception as e:
                    result.total_failed += 1
                    result.errors.append(str(e))
                    logger.error("email_process_error", subject=email_msg.subject, error=str(e))

        except Exception as e:
            result.success = False
            result.errors.append(str(e))

        finally:
            self.stopsale_service.close()

        return result

    def close_all(self) -> None:
        """Close all connections."""
        self.booking_service.close()
        self.stopsale_service.close()
