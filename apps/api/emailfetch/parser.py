"""Email parsing service - parses emails and creates reservations/stop_sales."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import sys
import os

import asyncpg

# Add src to path for parsers
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.parsers.email_parser import StopSaleEmailParser
from src.parsers.pdf_parser import JuniperPdfParser


@dataclass
class ParseResult:
    """Result of parsing operation."""
    
    success: bool
    message: str
    record_id: Optional[int] = None  # reservation or stop_sale id
    record_type: Optional[str] = None  # "reservation" or "stop_sale"
    details: dict = field(default_factory=dict)


class EmailParserService:
    """Service for parsing emails and creating database records."""
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.pdf_parser = JuniperPdfParser()
        self.stopsale_parser = StopSaleEmailParser()
    
    async def parse_email(self, email_id: int, tenant_id: int) -> ParseResult:
        """
        Parse an email and create appropriate record.
        
        Args:
            email_id: Email ID to parse
            tenant_id: Tenant ID
            
        Returns:
            ParseResult with created record info
        """
        async with self.pool.acquire() as conn:
            # Get email
            email = await conn.fetchrow(
                "SELECT * FROM emails WHERE id = $1 AND tenant_id = $2",
                email_id,
                tenant_id,
            )
            
            if not email:
                return ParseResult(
                    success=False,
                    message="Email not found",
                )
            
            # Already processed?
            if email["status"] in ("processed", "synced"):
                return ParseResult(
                    success=True,
                    message="Already processed",
                )
            
            email_type = email["email_type"]
            
            try:
                if email_type == "booking" and email["has_pdf"] and email["pdf_content"]:
                    # Parse PDF for reservation
                    result = await self._parse_booking_pdf(conn, email, tenant_id)
                elif email_type == "stopsale":
                    # Parse email body for stop sale
                    result = await self._parse_stop_sale(conn, email, tenant_id)
                else:
                    # Try to parse based on content
                    result = await self._parse_unknown(conn, email, tenant_id)
                
                # Update email status
                if result.success:
                    await conn.execute(
                        """
                        UPDATE emails 
                        SET status = 'processed', processed_at = NOW()
                        WHERE id = $1 AND tenant_id = $2
                        """,
                        email_id,
                        tenant_id,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE emails 
                        SET status = 'failed', error_message = $3
                        WHERE id = $1 AND tenant_id = $2
                        """,
                        email_id,
                        tenant_id,
                        result.message,
                    )
                
                return result
                
            except Exception as e:
                await conn.execute(
                    """
                    UPDATE emails 
                    SET status = 'failed', error_message = $3
                    WHERE id = $1 AND tenant_id = $2
                    """,
                    email_id,
                    tenant_id,
                    str(e),
                )
                return ParseResult(
                    success=False,
                    message=str(e),
                )
    
    async def _parse_booking_pdf(
        self,
        conn: asyncpg.Connection,
        email: dict,
        tenant_id: int,
    ) -> ParseResult:
        """Parse PDF attachment for reservation data."""
        try:
            reservation = self.pdf_parser.parse_bytes(
                email["pdf_content"],
                source_name=email["pdf_filename"] or "attachment.pdf",
            )
            
            if not reservation:
                return ParseResult(
                    success=False,
                    message="Could not parse PDF",
                )
            
            # Check for duplicate voucher
            existing = await conn.fetchval(
                "SELECT id FROM reservations WHERE voucher_no = $1 AND tenant_id = $2",
                reservation.voucher_no,
                tenant_id,
            )
            
            if existing:
                return ParseResult(
                    success=True,
                    message="Reservation already exists",
                    record_id=existing,
                    record_type="reservation",
                )
            
            # Insert reservation
            record_id = await conn.fetchval(
                """
                INSERT INTO reservations (
                    tenant_id, voucher_no, hotel_name, check_in, check_out,
                    room_type, board_type, adults, children, 
                    total_price, currency, guests, source_email_id, 
                    status, created_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                    'pending', NOW()
                )
                RETURNING id
                """,
                tenant_id,
                reservation.voucher_no,
                reservation.hotel_name,
                reservation.check_in,
                reservation.check_out,
                reservation.room_type,
                reservation.board_type,
                reservation.adults,
                reservation.children,
                float(reservation.total_price) if reservation.total_price else None,
                reservation.currency,
                [g.__dict__ for g in reservation.guests] if reservation.guests else [],
                email["id"],
            )
            
            return ParseResult(
                success=True,
                message="Reservation created",
                record_id=record_id,
                record_type="reservation",
                details={
                    "voucher_no": reservation.voucher_no,
                    "hotel": reservation.hotel_name,
                    "dates": f"{reservation.check_in} - {reservation.check_out}",
                },
            )
            
        except Exception as e:
            return ParseResult(
                success=False,
                message=f"PDF parse error: {str(e)}",
            )
    
    async def _parse_stop_sale(
        self,
        conn: asyncpg.Connection,
        email: dict,
        tenant_id: int,
    ) -> ParseResult:
        """Parse email body for stop sale data."""
        try:
            stop_sale = self.stopsale_parser.parse(
                subject=email["subject"],
                body=email["body_text"] or "",
                sender=email["sender"],
                email_date=email["received_at"].date() if email["received_at"] else None,
            )
            
            if not stop_sale:
                return ParseResult(
                    success=False,
                    message="Could not parse stop sale",
                )
            
            # Insert stop sale
            record_id = await conn.fetchval(
                """
                INSERT INTO stop_sales (
                    tenant_id, hotel_name, date_from, date_to,
                    room_types, board_types, is_close, reason,
                    source_email_id, status, created_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, 'pending', NOW()
                )
                RETURNING id
                """,
                tenant_id,
                stop_sale.hotel_name,
                stop_sale.date_from,
                stop_sale.date_to,
                stop_sale.room_types or [],
                stop_sale.board_types or [],
                stop_sale.is_close,
                stop_sale.reason,
                email["id"],
            )
            
            return ParseResult(
                success=True,
                message="Stop sale created",
                record_id=record_id,
                record_type="stop_sale",
                details={
                    "hotel": stop_sale.hotel_name,
                    "dates": f"{stop_sale.date_from} - {stop_sale.date_to}",
                    "is_close": stop_sale.is_close,
                },
            )
            
        except Exception as e:
            return ParseResult(
                success=False,
                message=f"Stop sale parse error: {str(e)}",
            )
    
    async def _parse_unknown(
        self,
        conn: asyncpg.Connection,
        email: dict,
        tenant_id: int,
    ) -> ParseResult:
        """Try to parse unknown email type."""
        # First try PDF if present
        if email["has_pdf"] and email["pdf_content"]:
            result = await self._parse_booking_pdf(conn, email, tenant_id)
            if result.success:
                return result
        
        # Then try stop sale parsing
        result = await self._parse_stop_sale(conn, email, tenant_id)
        if result.success:
            return result
        
        return ParseResult(
            success=False,
            message="Could not determine email type or parse content",
        )
    
    async def parse_pending_emails(self, tenant_id: int, limit: int = 50) -> dict:
        """
        Parse all pending emails for a tenant.
        
        Returns:
            Summary of parse results
        """
        results = {
            "total": 0,
            "reservations_created": 0,
            "stop_sales_created": 0,
            "failed": 0,
            "errors": [],
        }
        
        async with self.pool.acquire() as conn:
            pending = await conn.fetch(
                """
                SELECT id FROM emails 
                WHERE tenant_id = $1 AND status = 'pending'
                ORDER BY received_at
                LIMIT $2
                """,
                tenant_id,
                limit,
            )
            
            for row in pending:
                results["total"] += 1
                result = await self.parse_email(row["id"], tenant_id)
                
                if result.success:
                    if result.record_type == "reservation":
                        results["reservations_created"] += 1
                    elif result.record_type == "stop_sale":
                        results["stop_sales_created"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append(f"Email {row['id']}: {result.message}")
        
        return results
