"""Reservation service - Full pipeline from email to Sedna."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Awaitable, Any

from src.config import get_settings
from src.models.reservation import JuniperReservation, Guest
from src.parsers.pdf_parser import JuniperPdfParser, parse_reservation_bytes
from src.services.email_service import (
    EmailService,
    EmailProcessor,
    EmailConnectionConfig,
    EmailMessage,
    EmailClassifier,
)
from src.services.sedna_client import (
    SednaClient,
    ReservationRequest,
    CustomerRequest,
    SednaApiResponse,
    SednaValidationError,
)
from src.services.mapping_service import MappingService
from src.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class ProcessingResult:
    """Result of processing a single reservation."""

    success: bool
    voucher_no: str
    sedna_rec_id: int | None = None
    error_message: str | None = None
    source_email_subject: str | None = None
    source_pdf_path: str | None = None
    processing_time_ms: int = 0


@dataclass
class BatchProcessingResult:
    """Result of processing a batch of reservations."""

    success: bool
    total_processed: int = 0
    total_success: int = 0
    total_failed: int = 0
    results: list[ProcessingResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None

    @property
    def duration_seconds(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0

    @property
    def success_rate(self) -> float:
        if self.total_processed == 0:
            return 0
        return (self.total_success / self.total_processed) * 100


# =============================================================================
# Reservation Service
# =============================================================================


class ReservationService:
    """
    Service for processing Juniper reservations into Sedna.

    This service orchestrates the full pipeline:
    1. Fetch emails with PDF attachments
    2. Parse PDF to extract reservation data
    3. Map Juniper data to Sedna IDs
    4. Create reservation in Sedna
    5. Mark email as processed
    """

    def __init__(
        self,
        sedna_client: SednaClient,
        mapping_service: MappingService,
        attachment_dir: str | Path = "/tmp/mindops-entegrasyon/reservations",
    ):
        """
        Initialize reservation service.

        Args:
            sedna_client: Configured Sedna API client
            mapping_service: Mapping service for ID lookups
            attachment_dir: Directory to save PDF attachments
        """
        self.sedna = sedna_client
        self.mapping = mapping_service
        self.attachment_dir = Path(attachment_dir)
        self.parser = JuniperPdfParser()

        # Ensure attachment directory exists
        self.attachment_dir.mkdir(parents=True, exist_ok=True)

    async def process_email(
        self,
        email: EmailMessage,
        pdf_path: Path | None = None,
    ) -> ProcessingResult:
        """
        Process a single email with reservation PDF.

        Args:
            email: Email message with PDF attachment
            pdf_path: Optional path to saved PDF

        Returns:
            ProcessingResult
        """
        start_time = datetime.now()
        voucher_no = "UNKNOWN"

        try:
            logger.info(
                "processing_reservation_email",
                subject=email.subject[:50],
                has_pdf=email.has_pdf_attachment,
            )

            # Get PDF content
            if not email.has_pdf_attachment:
                return ProcessingResult(
                    success=False,
                    voucher_no=voucher_no,
                    error_message="No PDF attachment found",
                    source_email_subject=email.subject,
                )

            pdf_attachment = email.pdf_attachments[0]
            pdf_bytes = pdf_attachment.content

            # Parse PDF
            reservation = parse_reservation_bytes(pdf_bytes, pdf_attachment.filename)

            if not reservation:
                return ProcessingResult(
                    success=False,
                    voucher_no=voucher_no,
                    error_message="Failed to parse PDF",
                    source_email_subject=email.subject,
                    source_pdf_path=str(pdf_path) if pdf_path else None,
                )

            voucher_no = reservation.voucher_no

            # Process the parsed reservation
            result = await self.process_reservation(reservation)
            result.source_email_subject = email.subject
            result.source_pdf_path = str(pdf_path) if pdf_path else None
            result.processing_time_ms = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )

            return result

        except Exception as e:
            logger.error(
                "reservation_email_error",
                subject=email.subject[:50],
                error=str(e),
            )
            return ProcessingResult(
                success=False,
                voucher_no=voucher_no,
                error_message=str(e),
                source_email_subject=email.subject,
                processing_time_ms=int(
                    (datetime.now() - start_time).total_seconds() * 1000
                ),
            )

    async def process_reservation(
        self,
        reservation: JuniperReservation,
    ) -> ProcessingResult:
        """
        Process a parsed reservation and send to Sedna.

        Args:
            reservation: Parsed JuniperReservation

        Returns:
            ProcessingResult
        """
        logger.info(
            "processing_reservation",
            voucher=reservation.voucher_no,
            hotel=reservation.hotel_name,
            check_in=str(reservation.check_in),
        )

        try:
            # Map to Sedna IDs
            hotel_id = self.mapping.get_hotel_id(reservation.hotel_name)
            if not hotel_id:
                # Try fuzzy match or return error
                logger.warning(
                    "hotel_not_mapped",
                    hotel_name=reservation.hotel_name,
                )
                return ProcessingResult(
                    success=False,
                    voucher_no=reservation.voucher_no,
                    error_message=f"Hotel not found in mapping: {reservation.hotel_name}",
                )

            room_type_id = self.mapping.get_room_type_id(
                reservation.hotel_name,
                reservation.room_type,
            )
            if not room_type_id:
                # Use default or first available
                logger.warning(
                    "room_type_not_mapped",
                    hotel=reservation.hotel_name,
                    room_type=reservation.room_type,
                )
                room_type_id = 1  # Fallback to default

            board_id = self.mapping.get_board_id(reservation.board_type)
            if not board_id:
                board_id = 1  # Default to AI

            # Build Sedna request
            sedna_request = self._build_sedna_request(
                reservation=reservation,
                operator_id=self.sedna.operator_id or 0,
                hotel_id=hotel_id,
                room_type_id=room_type_id,
                board_id=board_id,
            )

            # Send to Sedna
            response = await self.sedna.insert_reservation(
                reservation=sedna_request,
                voucher_no=reservation.voucher_no,
            )

            logger.info(
                "reservation_created",
                voucher=reservation.voucher_no,
                sedna_rec_id=response.RecId,
            )

            return ProcessingResult(
                success=True,
                voucher_no=reservation.voucher_no,
                sedna_rec_id=response.RecId,
            )

        except SednaValidationError as e:
            logger.error(
                "sedna_validation_error",
                voucher=reservation.voucher_no,
                error=str(e),
            )
            return ProcessingResult(
                success=False,
                voucher_no=reservation.voucher_no,
                error_message=f"Sedna validation error: {e}",
            )
        except Exception as e:
            logger.error(
                "reservation_processing_error",
                voucher=reservation.voucher_no,
                error=str(e),
            )
            return ProcessingResult(
                success=False,
                voucher_no=reservation.voucher_no,
                error_message=str(e),
            )

    def _build_sedna_request(
        self,
        reservation: JuniperReservation,
        operator_id: int,
        hotel_id: int,
        room_type_id: int,
        board_id: int,
    ) -> ReservationRequest:
        """
        Build Sedna reservation request from parsed data.

        Args:
            reservation: Parsed reservation
            operator_id: Sedna operator ID
            hotel_id: Sedna hotel ID
            room_type_id: Sedna room type ID
            board_id: Sedna board ID

        Returns:
            ReservationRequest for Sedna API
        """
        # Build customer list
        customers = []

        for guest in reservation.guests:
            customer = CustomerRequest(
                Title=guest.title,
                FirstName=guest.first_name,
                LastName=guest.last_name,
                Age=guest.age,
                BirthDate=guest.birth_date.isoformat() if guest.birth_date else None,
                PassNo=guest.passport_no,
                Nationality=guest.nationality,
                NationalityId=self.mapping.get_country_id(guest.nationality)
                if guest.nationality
                else None,
            )
            customers.append(customer)

        # If no guests extracted, create placeholder
        if not customers:
            customers.append(
                CustomerRequest(
                    Title="Mr",
                    FirstName="GUEST",
                    LastName="NAME",
                )
            )

        # Build request
        return ReservationRequest(
            HotelId=hotel_id,
            OperatorId=operator_id,
            CheckinDate=reservation.check_in.isoformat(),
            CheckOutDate=reservation.check_out.isoformat(),
            Adult=reservation.adults,
            Child=reservation.children,
            BoardId=board_id,
            RoomTypeId=room_type_id,
            Customers=customers,
            SourceId=reservation.voucher_no,
            Amount=reservation.total_price,
            SaleDate=datetime.now().strftime("%Y-%m-%d"),
            ReservationRemark=f"Imported from Juniper: {reservation.voucher_no}",
        )

    async def process_batch(
        self,
        email_config: EmailConnectionConfig,
        max_count: int = 50,
        on_processed: Callable[[ProcessingResult], Awaitable[None]] | None = None,
    ) -> BatchProcessingResult:
        """
        Process a batch of reservation emails.

        Args:
            email_config: Email connection configuration
            max_count: Maximum emails to process
            on_processed: Optional callback for each processed reservation

        Returns:
            BatchProcessingResult with statistics
        """
        result = BatchProcessingResult(success=True)

        email_service = EmailService(email_config)

        try:
            logger.info("batch_processing_start", max_count=max_count)

            async for email in email_service.fetch_unread_emails(max_count):
                # Check if it's a reservation email
                classification = EmailClassifier.classify(email)
                if classification != "reservation":
                    logger.debug(
                        "skipping_non_reservation",
                        subject=email.subject[:50],
                        classification=classification,
                    )
                    continue

                # Save PDF attachment
                pdf_path = None
                if email.has_pdf_attachment:
                    pdf = email.pdf_attachments[0]
                    pdf_path = await email_service.save_attachment(
                        pdf,
                        self.attachment_dir,
                    )

                # Process email
                processing_result = await self.process_email(email, pdf_path)
                result.results.append(processing_result)
                result.total_processed += 1

                if processing_result.success:
                    result.total_success += 1
                    # Mark email as read
                    await email_service.mark_as_read(email.uid)
                else:
                    result.total_failed += 1
                    result.errors.append(
                        f"{processing_result.voucher_no}: {processing_result.error_message}"
                    )

                # Call callback if provided
                if on_processed:
                    await on_processed(processing_result)

        except Exception as e:
            result.success = False
            result.errors.append(f"Batch processing error: {e}")
            logger.error("batch_processing_error", error=str(e))

        finally:
            email_service.close()
            result.end_time = datetime.now()

        logger.info(
            "batch_processing_complete",
            total=result.total_processed,
            success=result.total_success,
            failed=result.total_failed,
            duration_s=result.duration_seconds,
        )

        return result


# =============================================================================
# Factory Functions
# =============================================================================


async def create_reservation_service(
    sedna_base_url: str | None = None,
    sedna_username: str | None = None,
    sedna_password: str | None = None,
    mapping_cache_file: str | Path | None = None,
) -> ReservationService:
    """
    Create and configure a ReservationService.

    Args:
        sedna_base_url: Sedna API base URL (from config if not provided)
        sedna_username: Sedna username (from config if not provided)
        sedna_password: Sedna password (from config if not provided)
        mapping_cache_file: Path to mapping cache file

    Returns:
        Configured ReservationService
    """
    settings = get_settings()

    # Create Sedna client
    sedna = SednaClient(
        base_url=sedna_base_url or settings.sedna_api_base_url,
        username=sedna_username or settings.sedna_username,
        password=sedna_password or settings.sedna_password,
    )

    # Login
    await sedna.login()

    # Create mapping service
    cache_file = mapping_cache_file or Path("config/mapping_cache.json")
    mapping = MappingService(cache_file=cache_file)

    # Populate mappings from Sedna if cache is empty
    if not mapping.cache.hotels:
        logger.info("populating_mapping_cache")
        await mapping.populate_from_sedna(sedna)

    return ReservationService(
        sedna_client=sedna,
        mapping_service=mapping,
    )


async def process_reservation_emails(
    email_host: str | None = None,
    email_username: str | None = None,
    email_password: str | None = None,
    max_count: int = 50,
) -> BatchProcessingResult:
    """
    Convenience function to process reservation emails.

    Args:
        email_host: IMAP host (from config if not provided)
        email_username: Email username (from config if not provided)
        email_password: Email password (from config if not provided)
        max_count: Maximum emails to process

    Returns:
        BatchProcessingResult
    """
    settings = get_settings()

    # Create email config
    email_config = EmailConnectionConfig(
        host=email_host or settings.booking_email_host,
        port=settings.booking_email_port,
        username=email_username or settings.booking_email_address,
        password=email_password or settings.booking_email_password,
    )

    # Create service
    service = await create_reservation_service()

    try:
        return await service.process_batch(email_config, max_count)
    finally:
        # Cleanup
        if service.sedna._client:
            await service.sedna._client.aclose()
