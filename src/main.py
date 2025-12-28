"""Main entry point for MindOpsOS Entegrasyon service."""

import asyncio
import signal
import sys
from datetime import datetime
from pathlib import Path

from src.config import get_settings
from src.services.email_service import EmailConnectionConfig
from src.services.reservation_service import (
    ReservationService,
    create_reservation_service,
    BatchProcessingResult,
)
from src.services.stopsale_service import (
    StopSaleService,
    create_stop_sale_service,
    StopSaleBatchResult,
)
from src.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


# =============================================================================
# Orchestrator
# =============================================================================


class IntegrationOrchestrator:
    """
    Main orchestrator for the integration service.

    Coordinates:
    - Reservation email processing
    - Stop sale email processing
    - Scheduling and monitoring
    """

    def __init__(self):
        """Initialize orchestrator."""
        self.settings = get_settings()
        self.reservation_service: ReservationService | None = None
        self.stopsale_service: StopSaleService | None = None
        self._running = False
        self._shutdown_event = asyncio.Event()

    async def initialize(self) -> None:
        """Initialize services."""
        logger.info("initializing_services")

        try:
            # Create reservation service
            self.reservation_service = await create_reservation_service()
            logger.info("reservation_service_initialized")

            # Create stop sale service
            self.stopsale_service = await create_stop_sale_service()
            logger.info("stopsale_service_initialized")

        except Exception as e:
            logger.error("service_initialization_error", error=str(e))
            raise

    async def process_all(self) -> dict:
        """
        Process both reservation and stop sale emails.

        Returns:
            Dict with processing results
        """
        results = {
            "reservations": None,
            "stop_sales": None,
            "timestamp": datetime.now().isoformat(),
        }

        if not self.reservation_service or not self.stopsale_service:
            await self.initialize()

        # Process reservations
        try:
            booking_config = EmailConnectionConfig(
                host=self.settings.booking_email_host,
                port=self.settings.booking_email_port,
                username=self.settings.booking_email_address,
                password=self.settings.booking_email_password,
            )

            res_result = await self.reservation_service.process_batch(
                email_config=booking_config,
                max_count=50,
            )

            results["reservations"] = {
                "processed": res_result.total_processed,
                "success": res_result.total_success,
                "failed": res_result.total_failed,
                "duration_s": res_result.duration_seconds,
                "success_rate": res_result.success_rate,
            }

        except Exception as e:
            logger.error("reservation_processing_failed", error=str(e))
            results["reservations"] = {"error": str(e)}

        # Process stop sales
        try:
            stopsale_config = EmailConnectionConfig(
                host=self.settings.stopsale_email_host,
                port=self.settings.stopsale_email_port,
                username=self.settings.stopsale_email_address,
                password=self.settings.stopsale_email_password,
            )

            ss_result = await self.stopsale_service.process_batch(
                email_config=stopsale_config,
                max_count=50,
            )

            results["stop_sales"] = {
                "processed": ss_result.total_processed,
                "success": ss_result.total_success,
                "failed": ss_result.total_failed,
                "duration_s": ss_result.duration_seconds,
            }

        except Exception as e:
            logger.error("stopsale_processing_failed", error=str(e))
            results["stop_sales"] = {"error": str(e)}

        return results

    async def run_scheduler(self, interval_seconds: int | None = None) -> None:
        """
        Run scheduled processing loop.

        Args:
            interval_seconds: Processing interval (from config if not provided)
        """
        interval = interval_seconds or self.settings.email_check_interval_seconds
        self._running = True

        logger.info(
            "scheduler_started",
            interval_seconds=interval,
        )

        print_banner()

        while self._running and not self._shutdown_event.is_set():
            try:
                logger.info("processing_cycle_start")

                results = await self.process_all()

                logger.info(
                    "processing_cycle_complete",
                    reservations=results.get("reservations", {}),
                    stop_sales=results.get("stop_sales", {}),
                )

                # Print summary
                self._print_summary(results)

            except Exception as e:
                logger.error("processing_cycle_error", error=str(e))

            # Wait for next cycle
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=interval,
                )
            except asyncio.TimeoutError:
                pass  # Normal timeout, continue loop

        logger.info("scheduler_stopped")

    def _print_summary(self, results: dict) -> None:
        """Print processing summary."""
        res = results.get("reservations", {})
        ss = results.get("stop_sales", {})

        print("\n" + "=" * 50)
        print(f"📊 Processing Summary - {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 50)

        if "error" not in res:
            print(f"📋 Reservations: {res.get('success', 0)}/{res.get('processed', 0)} success")
        else:
            print(f"📋 Reservations: ❌ Error - {res.get('error', 'Unknown')}")

        if "error" not in ss:
            print(f"🚫 Stop Sales: {ss.get('success', 0)}/{ss.get('processed', 0)} success")
        else:
            print(f"🚫 Stop Sales: ❌ Error - {ss.get('error', 'Unknown')}")

        print("=" * 50 + "\n")

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        self._shutdown_event.set()

    async def cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("cleaning_up")

        if self.reservation_service and self.reservation_service.sedna._client:
            await self.reservation_service.sedna._client.aclose()

        if self.stopsale_service and self.stopsale_service.sedna and self.stopsale_service.sedna._client:
            await self.stopsale_service.sedna._client.aclose()


# =============================================================================
# CLI Commands
# =============================================================================


async def cmd_process_once() -> None:
    """Process emails once and exit."""
    orchestrator = IntegrationOrchestrator()

    try:
        await orchestrator.initialize()
        results = await orchestrator.process_all()

        print("\n✅ Processing Complete")
        print(f"Reservations: {results.get('reservations', {})}")
        print(f"Stop Sales: {results.get('stop_sales', {})}")

    finally:
        await orchestrator.cleanup()


async def cmd_run_service() -> None:
    """Run as continuous service."""
    orchestrator = IntegrationOrchestrator()

    # Setup signal handlers
    def handle_signal(signum, frame):
        logger.info("shutdown_signal_received", signal=signum)
        orchestrator.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        await orchestrator.initialize()
        await orchestrator.run_scheduler()

    finally:
        await orchestrator.cleanup()


async def cmd_test_connection() -> None:
    """Test connections to email and Sedna."""
    from src.services.sedna_client import SednaClient
    from src.services.email_service import EmailService

    settings = get_settings()
    print("\n🔍 Testing Connections...\n")

    # Test Sedna
    print("1️⃣ Testing Sedna API...")
    try:
        async with SednaClient(
            base_url=settings.sedna_api_base_url,
            username=settings.sedna_username,
            password=settings.sedna_password,
        ) as client:
            hotels = await client.get_hotels()
            print(f"   ✅ Sedna connected! OperatorId: {client.operator_id}")
            print(f"   📋 Found {len(hotels)} hotels")
    except Exception as e:
        print(f"   ❌ Sedna failed: {e}")

    # Test Booking Email
    print("\n2️⃣ Testing Booking Email (IMAP)...")
    try:
        config = EmailConnectionConfig(
            host=settings.booking_email_host,
            port=settings.booking_email_port,
            username=settings.booking_email_address,
            password=settings.booking_email_password,
        )
        service = EmailService(config)
        folders = service.get_folder_list()
        print(f"   ✅ Booking email connected!")
        print(f"   📁 Folders: {folders[:5]}...")
        service.close()
    except Exception as e:
        print(f"   ❌ Booking email failed: {e}")

    # Test Stop Sale Email
    print("\n3️⃣ Testing Stop Sale Email (IMAP)...")
    try:
        config = EmailConnectionConfig(
            host=settings.stopsale_email_host,
            port=settings.stopsale_email_port,
            username=settings.stopsale_email_address,
            password=settings.stopsale_email_password,
        )
        service = EmailService(config)
        folders = service.get_folder_list()
        print(f"   ✅ Stop sale email connected!")
        print(f"   📁 Folders: {folders[:5]}...")
        service.close()
    except Exception as e:
        print(f"   ❌ Stop sale email failed: {e}")

    print("\n✅ Connection tests complete!\n")


# =============================================================================
# Banner & Main
# =============================================================================


def print_banner() -> None:
    """Print startup banner."""
    banner = """
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   🔄 MindOpsOS Entegrasyon Service                       ║
║   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                          ║
║   Juniper → Sedna Integration Pipeline                   ║
║                                                           ║
║   📧 Booking: booking@pointholiday.com                   ║
║   🚫 StopSale: stopsale@pointholiday.com                 ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
"""
    print(banner)


def main() -> None:
    """Main entry point."""
    setup_logging()

    # Parse command
    command = sys.argv[1] if len(sys.argv) > 1 else "service"

    if command == "once":
        asyncio.run(cmd_process_once())
    elif command == "test":
        asyncio.run(cmd_test_connection())
    elif command == "service":
        asyncio.run(cmd_run_service())
    else:
        print(f"Unknown command: {command}")
        print("Usage: python -m src.main [once|test|service]")
        sys.exit(1)


if __name__ == "__main__":
    main()
