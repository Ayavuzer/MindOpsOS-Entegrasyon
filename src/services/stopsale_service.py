"""Stop sale service - Process stop sale emails."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Callable, Awaitable

from src.config import get_settings
from src.models.stopsale import StopSale, SednaStopSaleRequest
from src.parsers.email_parser import StopSaleEmailParser, parse_stop_sale_email
from src.services.email_service import (
    EmailService,
    EmailConnectionConfig,
    EmailMessage,
    EmailClassifier,
)
from src.services.sedna_client import SednaClient, StopSaleFilter
from src.services.mapping_service import MappingService
from src.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class StopSaleProcessingResult:
    """Result of processing a stop sale."""

    success: bool
    hotel_name: str
    date_from: date | None = None
    date_to: date | None = None
    error_message: str | None = None
    source_email_subject: str | None = None
    sedna_synced: bool = False
    processing_time_ms: int = 0


@dataclass
class StopSaleBatchResult:
    """Result of processing a batch of stop sales."""

    success: bool
    total_processed: int = 0
    total_success: int = 0
    total_failed: int = 0
    results: list[StopSaleProcessingResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None

    @property
    def duration_seconds(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0


# =============================================================================
# Stop Sale Service
# =============================================================================


class StopSaleService:
    """
    Service for processing stop sale notifications.

    This service:
    1. Fetches stop sale emails
    2. Parses email content to extract stop sale info
    3. Stores/syncs with Sedna (when endpoint available)
    4. Logs for manual review
    """

    def __init__(
        self,
        sedna_client: SednaClient | None = None,
        mapping_service: MappingService | None = None,
        storage_path: str | Path = "/tmp/mindops-entegrasyon/stopsales",
    ):
        """
        Initialize stop sale service.

        Args:
            sedna_client: Optional Sedna client for syncing
            mapping_service: Mapping service for hotel lookups
            storage_path: Path to store stop sale records
        """
        self.sedna = sedna_client
        self.mapping = mapping_service or MappingService()
        self.storage_path = Path(storage_path)
        self.parser = StopSaleEmailParser()

        # Pending stop sales (in-memory queue)
        self._pending_stop_sales: list[StopSale] = []

        # Ensure storage directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def process_email(
        self,
        email: EmailMessage,
    ) -> StopSaleProcessingResult:
        """
        Process a stop sale email.

        Args:
            email: Email message to process

        Returns:
            StopSaleProcessingResult
        """
        start_time = datetime.now()
        hotel_name = "UNKNOWN"

        try:
            logger.info(
                "processing_stop_sale_email",
                subject=email.subject[:50],
            )

            # Parse email content
            stop_sale = self.parser.parse(
                subject=email.subject,
                body=email.body_text,
                sender=email.sender,
                email_date=email.date.date() if email.date else None,
            )

            if not stop_sale:
                return StopSaleProcessingResult(
                    success=False,
                    hotel_name=hotel_name,
                    error_message="Failed to parse stop sale from email",
                    source_email_subject=email.subject,
                    processing_time_ms=int(
                        (datetime.now() - start_time).total_seconds() * 1000
                    ),
                )

            hotel_name = stop_sale.hotel_name

            # Process the stop sale
            result = await self.process_stop_sale(stop_sale)
            result.source_email_subject = email.subject
            result.processing_time_ms = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )

            return result

        except Exception as e:
            logger.error(
                "stop_sale_email_error",
                subject=email.subject[:50],
                error=str(e),
            )
            return StopSaleProcessingResult(
                success=False,
                hotel_name=hotel_name,
                error_message=str(e),
                source_email_subject=email.subject,
                processing_time_ms=int(
                    (datetime.now() - start_time).total_seconds() * 1000
                ),
            )

    async def process_stop_sale(
        self,
        stop_sale: StopSale,
    ) -> StopSaleProcessingResult:
        """
        Process a parsed stop sale.

        Args:
            stop_sale: Parsed StopSale object

        Returns:
            StopSaleProcessingResult
        """
        logger.info(
            "processing_stop_sale",
            hotel=stop_sale.hotel_name,
            date_from=str(stop_sale.date_from),
            date_to=str(stop_sale.date_to),
            is_close=stop_sale.is_close,
        )

        try:
            # Get hotel ID from mapping
            hotel_id = self.mapping.get_hotel_id(stop_sale.hotel_name)

            if not hotel_id:
                logger.warning(
                    "stop_sale_hotel_not_mapped",
                    hotel_name=stop_sale.hotel_name,
                )

            # Save to local storage
            await self._save_stop_sale(stop_sale, hotel_id)

            # Add to pending queue
            self._pending_stop_sales.append(stop_sale)

            # Try to sync with Sedna (if API available)
            sedna_synced = False
            if self.sedna and hotel_id:
                sedna_synced = await self._sync_to_sedna(stop_sale, hotel_id)

            return StopSaleProcessingResult(
                success=True,
                hotel_name=stop_sale.hotel_name,
                date_from=stop_sale.date_from,
                date_to=stop_sale.date_to,
                sedna_synced=sedna_synced,
            )

        except Exception as e:
            logger.error(
                "stop_sale_processing_error",
                hotel=stop_sale.hotel_name,
                error=str(e),
            )
            return StopSaleProcessingResult(
                success=False,
                hotel_name=stop_sale.hotel_name,
                date_from=stop_sale.date_from,
                date_to=stop_sale.date_to,
                error_message=str(e),
            )

    async def _save_stop_sale(
        self,
        stop_sale: StopSale,
        hotel_id: int | None = None,
    ) -> Path:
        """
        Save stop sale to local storage.

        Args:
            stop_sale: StopSale object
            hotel_id: Mapped hotel ID

        Returns:
            Path to saved file
        """
        import json

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"stopsale_{timestamp}_{stop_sale.hotel_name[:20].replace(' ', '_')}.json"
        file_path = self.storage_path / filename

        data = {
            "hotel_name": stop_sale.hotel_name,
            "hotel_id": hotel_id,
            "date_from": stop_sale.date_from.isoformat() if stop_sale.date_from else None,
            "date_to": stop_sale.date_to.isoformat() if stop_sale.date_to else None,
            "room_types": stop_sale.room_types,
            "board_types": stop_sale.board_types,
            "is_close": stop_sale.is_close,
            "reason": stop_sale.reason,
            "processed_at": datetime.now().isoformat(),
        }

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False)),
        )

        logger.debug("stop_sale_saved", path=str(file_path))
        return file_path

    async def _sync_to_sedna(
        self,
        stop_sale: StopSale,
        hotel_id: int,
    ) -> bool:
        """
        Sync stop sale to Sedna.

        NOTE: This is a placeholder - the actual Sedna API endpoint
        for creating stop sales needs to be confirmed.

        Args:
            stop_sale: StopSale object
            hotel_id: Sedna hotel ID

        Returns:
            True if synced successfully
        """
        # TODO: Implement when Sedna provides InsertStopSale endpoint
        # For now, we just verify it exists in Sedna
        
        if not self.sedna:
            return False

        try:
            # Check if stop sale already exists
            existing = await self.sedna.get_stop_sales(
                StopSaleFilter(
                    hotelId=hotel_id,
                    stopDateBegin=stop_sale.date_from.isoformat() if stop_sale.date_from else None,
                    stopDateEnd=stop_sale.date_to.isoformat() if stop_sale.date_to else None,
                )
            )

            if existing:
                logger.info(
                    "stop_sale_already_exists_in_sedna",
                    hotel_id=hotel_id,
                    count=len(existing),
                )
                return True

            # TODO: Call InsertStopSale when available
            logger.warning(
                "stop_sale_sync_not_implemented",
                hotel_id=hotel_id,
                message="InsertStopSale endpoint not available",
            )
            return False

        except Exception as e:
            logger.error(
                "stop_sale_sync_error",
                hotel_id=hotel_id,
                error=str(e),
            )
            return False

    async def process_batch(
        self,
        email_config: EmailConnectionConfig,
        max_count: int = 50,
        on_processed: Callable[[StopSaleProcessingResult], Awaitable[None]] | None = None,
    ) -> StopSaleBatchResult:
        """
        Process a batch of stop sale emails.

        Args:
            email_config: Email connection configuration
            max_count: Maximum emails to process
            on_processed: Optional callback

        Returns:
            StopSaleBatchResult
        """
        result = StopSaleBatchResult(success=True)

        email_service = EmailService(email_config)

        try:
            logger.info("stop_sale_batch_start", max_count=max_count)

            async for email in email_service.fetch_unread_emails(max_count):
                # Check if it's a stop sale email
                classification = EmailClassifier.classify(email)
                if classification != "stopsale":
                    logger.debug(
                        "skipping_non_stopsale",
                        subject=email.subject[:50],
                        classification=classification,
                    )
                    continue

                # Process email
                processing_result = await self.process_email(email)
                result.results.append(processing_result)
                result.total_processed += 1

                if processing_result.success:
                    result.total_success += 1
                    # Mark email as read
                    await email_service.mark_as_read(email.uid)
                else:
                    result.total_failed += 1
                    result.errors.append(
                        f"{processing_result.hotel_name}: {processing_result.error_message}"
                    )

                # Call callback if provided
                if on_processed:
                    await on_processed(processing_result)

        except Exception as e:
            result.success = False
            result.errors.append(f"Batch processing error: {e}")
            logger.error("stop_sale_batch_error", error=str(e))

        finally:
            email_service.close()
            result.end_time = datetime.now()

        logger.info(
            "stop_sale_batch_complete",
            total=result.total_processed,
            success=result.total_success,
            failed=result.total_failed,
            duration_s=result.duration_seconds,
        )

        return result

    def get_pending_stop_sales(self) -> list[StopSale]:
        """Get list of pending stop sales."""
        return self._pending_stop_sales.copy()

    def clear_pending_stop_sales(self) -> int:
        """Clear pending stop sales queue."""
        count = len(self._pending_stop_sales)
        self._pending_stop_sales.clear()
        return count


# =============================================================================
# Factory Functions
# =============================================================================


async def create_stop_sale_service(
    sedna_base_url: str | None = None,
    sedna_username: str | None = None,
    sedna_password: str | None = None,
) -> StopSaleService:
    """
    Create and configure a StopSaleService.

    Args:
        sedna_base_url: Sedna API base URL
        sedna_username: Sedna username
        sedna_password: Sedna password

    Returns:
        Configured StopSaleService
    """
    settings = get_settings()

    # Create Sedna client (optional for stop sales)
    sedna = None
    try:
        sedna = SednaClient(
            base_url=sedna_base_url or settings.sedna_api_base_url,
            username=sedna_username or settings.sedna_username,
            password=sedna_password or settings.sedna_password,
        )
        await sedna.login()
    except Exception as e:
        logger.warning("sedna_connection_optional", error=str(e))

    # Create mapping service
    mapping = MappingService(cache_file=Path("config/mapping_cache.json"))

    if sedna and not mapping.cache.hotels:
        await mapping.populate_from_sedna(sedna)

    return StopSaleService(
        sedna_client=sedna,
        mapping_service=mapping,
    )


async def process_stop_sale_emails(
    email_host: str | None = None,
    email_username: str | None = None,
    email_password: str | None = None,
    max_count: int = 50,
) -> StopSaleBatchResult:
    """
    Convenience function to process stop sale emails.

    Args:
        email_host: IMAP host
        email_username: Email username
        email_password: Email password
        max_count: Maximum emails to process

    Returns:
        StopSaleBatchResult
    """
    settings = get_settings()

    # Create email config
    email_config = EmailConnectionConfig(
        host=email_host or settings.stopsale_email_host,
        port=settings.stopsale_email_port,
        username=email_username or settings.stopsale_email_address,
        password=email_password or settings.stopsale_email_password,
    )

    # Create service
    service = await create_stop_sale_service()

    try:
        return await service.process_batch(email_config, max_count)
    finally:
        if service.sedna and service.sedna._client:
            await service.sedna._client.aclose()
