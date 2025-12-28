"""Tests for email service."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from src.services.email_service import (
    EmailService,
    EmailProcessor,
    EmailClassifier,
    EmailMessage,
    EmailAttachment,
    EmailConnectionConfig,
    EmailConnectionError,
    EmailFetchError,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def email_config():
    """Create test email configuration."""
    return EmailConnectionConfig(
        host="imap.gmail.com",
        port=993,
        username="test@example.com",
        password="testpass",
        use_ssl=True,
        folder="INBOX",
    )


@pytest.fixture
def sample_email():
    """Create a sample email message."""
    return EmailMessage(
        message_id="<test123@example.com>",
        uid="12345",
        subject="Reservation Confirmation - Grand Hotel",
        sender="bookings@juniper.com",
        recipients=["booking@pointholiday.com"],
        date=datetime(2024, 9, 15, 10, 30),
        body_text="Your reservation is confirmed.\nVoucher: V2024001",
        body_html=None,
        attachments=[
            EmailAttachment(
                filename="reservation.pdf",
                content_type="application/pdf",
                size=12345,
                content=b"%PDF-1.4 test content",
            )
        ],
        raw_headers={"Subject": "Reservation Confirmation"},
    )


@pytest.fixture
def stopsale_email():
    """Create a sample stop sale email."""
    return EmailMessage(
        message_id="<stopsale456@hotel.com>",
        uid="67890",
        subject="STOP SALE - Grand Hotel - January 2025",
        sender="reservations@grandhotel.com",
        recipients=["stopsale@pointholiday.com"],
        date=datetime(2024, 12, 27, 14, 0),
        body_text="Stop Sale Notification\nHotel: Grand Hotel\nPeriod: 2025-01-15 to 2025-01-31\nRooms: All",
        body_html=None,
        attachments=[],
        raw_headers={"Subject": "STOP SALE"},
    )


# =============================================================================
# EmailMessage Tests
# =============================================================================


def test_email_has_pdf_attachment(sample_email):
    """Test PDF attachment detection."""
    assert sample_email.has_pdf_attachment is True


def test_email_without_pdf(stopsale_email):
    """Test email without PDF."""
    assert stopsale_email.has_pdf_attachment is False


def test_email_pdf_attachments(sample_email):
    """Test getting PDF attachments."""
    pdfs = sample_email.pdf_attachments
    assert len(pdfs) == 1
    assert pdfs[0].filename == "reservation.pdf"


# =============================================================================
# EmailClassifier Tests
# =============================================================================


def test_classify_reservation_email(sample_email):
    """Test classification of reservation email."""
    classification = EmailClassifier.classify(sample_email)
    assert classification == "reservation"


def test_classify_stopsale_email(stopsale_email):
    """Test classification of stop sale email."""
    classification = EmailClassifier.classify(stopsale_email)
    assert classification == "stopsale"


def test_classify_unknown_email():
    """Test classification of unknown email type."""
    email = EmailMessage(
        message_id="<random@test.com>",
        uid="99999",
        subject="Hello World",
        sender="test@test.com",
        recipients=["me@test.com"],
        date=datetime.now(),
        body_text="Just a regular email with no keywords.",
        body_html=None,
        attachments=[],
        raw_headers={},
    )
    
    classification = EmailClassifier.classify(email)
    assert classification == "unknown"


def test_classify_reservation_without_pdf():
    """Test reservation email without PDF is classified as unknown."""
    email = EmailMessage(
        message_id="<booking@test.com>",
        uid="11111",
        subject="Reservation Confirmation",
        sender="juniper@travel.com",
        recipients=["booking@test.com"],
        date=datetime.now(),
        body_text="Your reservation is confirmed",
        body_html=None,
        attachments=[],  # No PDF
        raw_headers={},
    )
    
    classification = EmailClassifier.classify(email)
    # Without PDF, shouldn't be classified as reservation
    assert classification == "unknown"


def test_classify_turkish_stop_sale():
    """Test Turkish stop sale keywords."""
    email = EmailMessage(
        message_id="<tr@test.com>",
        uid="22222",
        subject="Satış Durdurma Bildirimi",
        sender="hotel@tr.com",
        recipients=["stopsale@test.com"],
        date=datetime.now(),
        body_text="Otelde satış durdurma yapılmıştır.",
        body_html=None,
        attachments=[],
        raw_headers={},
    )
    
    classification = EmailClassifier.classify(email)
    assert classification == "stopsale"


# =============================================================================
# EmailConnectionConfig Tests
# =============================================================================


def test_email_config_defaults(email_config):
    """Test email config default values."""
    assert email_config.use_ssl is True
    assert email_config.folder == "INBOX"
    assert email_config.timeout == 30


def test_email_config_custom():
    """Test custom email config."""
    config = EmailConnectionConfig(
        host="mail.example.com",
        port=143,
        username="user",
        password="pass",
        use_ssl=False,
        folder="Reservations",
        timeout=60,
    )
    
    assert config.use_ssl is False
    assert config.folder == "Reservations"
    assert config.timeout == 60


# =============================================================================
# EmailService Tests
# =============================================================================


def test_service_initialization(email_config):
    """Test service initialization."""
    service = EmailService(email_config)
    
    assert service.config == email_config
    assert service._connection is None


@pytest.mark.asyncio
async def test_service_connection_error(email_config):
    """Test connection error handling."""
    service = EmailService(email_config)
    
    with patch("imaplib.IMAP4_SSL") as mock_imap:
        mock_imap.side_effect = Exception("Connection refused")
        
        with pytest.raises(EmailConnectionError):
            service._connect()


# =============================================================================
# EmailAttachment Tests
# =============================================================================


def test_attachment_model():
    """Test attachment model."""
    attachment = EmailAttachment(
        filename="test.pdf",
        content_type="application/pdf",
        size=1024,
        content=b"test content",
    )
    
    assert attachment.filename == "test.pdf"
    assert attachment.size == 1024
    assert len(attachment.content) == 12


def test_pdf_detection_by_extension():
    """Test PDF detection by file extension."""
    attachment = EmailAttachment(
        filename="document.PDF",  # Uppercase
        content_type="application/octet-stream",
        size=100,
        content=b"data",
    )
    
    email = EmailMessage(
        message_id="<test@test.com>",
        uid="1",
        subject="Test",
        sender="a@b.com",
        recipients=["c@d.com"],
        date=None,
        body_text="",
        body_html=None,
        attachments=[attachment],
        raw_headers={},
    )
    
    assert email.has_pdf_attachment is True


# =============================================================================
# Integration Test (requires actual IMAP - skipped by default)
# =============================================================================


@pytest.mark.skip(reason="Requires actual IMAP server")
@pytest.mark.asyncio
async def test_real_email_connection():
    """Test real email connection (manual test)."""
    config = EmailConnectionConfig(
        host="imap.gmail.com",
        port=993,
        username="booking@pointholiday.com",
        password="YOUR_PASSWORD",
    )
    
    service = EmailService(config)
    
    try:
        # List folders
        folders = service.get_folder_list()
        print(f"Folders: {folders}")
        
        # Fetch emails
        count = 0
        async for email in service.fetch_unread_emails(max_count=5):
            print(f"Subject: {email.subject}")
            print(f"From: {email.sender}")
            print(f"Has PDF: {email.has_pdf_attachment}")
            count += 1
        
        print(f"✅ Fetched {count} emails")
        
    finally:
        service.close()
