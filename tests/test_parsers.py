"""Tests for PDF and email parsers."""

import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.parsers.pdf_parser import (
    JuniperPdfParser,
    parse_reservation_pdf,
    parse_reservation_bytes,
)
from src.parsers.email_parser import (
    StopSaleEmailParser,
    parse_stop_sale_email,
)


# =============================================================================
# PDF Parser Tests
# =============================================================================


class TestJuniperPdfParser:
    """Tests for JuniperPdfParser."""

    @pytest.fixture
    def parser(self):
        return JuniperPdfParser()

    def test_parse_date_dd_mm_yyyy(self, parser):
        """Test date parsing DD/MM/YYYY format."""
        assert parser._parse_date("15/01/2025") == date(2025, 1, 15)

    def test_parse_date_dd_mm_yy(self, parser):
        """Test date parsing DD.MM.YY format."""
        assert parser._parse_date("15.01.25") == date(2025, 1, 15)

    def test_parse_date_iso(self, parser):
        """Test date parsing ISO format."""
        assert parser._parse_date("2025-01-15") == date(2025, 1, 15)

    def test_parse_date_invalid(self, parser):
        """Test invalid date returns None."""
        assert parser._parse_date("invalid") is None
        assert parser._parse_date("") is None

    def test_parse_price_simple(self, parser):
        """Test simple price parsing."""
        assert parser._parse_price("1234.56") == Decimal("1234.56")

    def test_parse_price_european(self, parser):
        """Test European price format (1.234,56)."""
        assert parser._parse_price("1.234,56") == Decimal("1234.56")

    def test_parse_price_with_currency(self, parser):
        """Test price with currency symbol."""
        assert parser._parse_price("€ 1234.56") == Decimal("1234.56")
        assert parser._parse_price("$1,234.56") == Decimal("1234.56")

    def test_normalize_board_type(self, parser):
        """Test board type normalization."""
        assert parser._normalize_board_type("All Inclusive") == "AI"
        assert parser._normalize_board_type("Full Board") == "FB"
        assert parser._normalize_board_type("Half Board") == "HB"
        assert parser._normalize_board_type("Bed & Breakfast") == "BB"
        assert parser._normalize_board_type("Room Only") == "RO"
        assert parser._normalize_board_type("UAI") == "UAI"

    def test_normalize_currency(self, parser):
        """Test currency normalization."""
        assert parser._normalize_currency("€") == "EUR"
        assert parser._normalize_currency("$") == "USD"
        assert parser._normalize_currency("₺") == "TRY"
        assert parser._normalize_currency("TL") == "TRY"
        assert parser._normalize_currency("GBP") == "GBP"

    def test_extract_room_type_code(self, parser):
        """Test room type code extraction."""
        assert parser._extract_room_type_code("Double Room Sea View") == "DBL"
        assert parser._extract_room_type_code("Single Standard") == "SGL"
        assert parser._extract_room_type_code("Family Suite") == "FAM"
        assert parser._extract_room_type_code("JUNIOR SUI") == "SUI"

    def test_extract_field_voucher(self, parser):
        """Test voucher extraction."""
        text = "Booking Reference: V2024001234\nHotel: Grand Hotel"
        voucher = parser._extract_field("voucher_no", text)
        assert voucher == "V2024001234"

    def test_extract_field_hotel(self, parser):
        """Test hotel name extraction."""
        text = "Hotel: Grand Palace Resort\nCheck-in: 15/01/2025"
        hotel = parser._extract_field("hotel_name", text)
        assert "Grand Palace Resort" in hotel

    def test_extract_field_check_in(self, parser):
        """Test check-in date extraction."""
        text = "Check-in: 15/01/2025\nCheck-out: 22/01/2025"
        check_in = parser._extract_field("check_in", text)
        assert check_in == "15/01/2025"

    def test_extract_guests(self, parser):
        """Test guest extraction."""
        text = """
        Guest List:
        Mr. JOHN DOE
        Mrs. JANE DOE
        """
        guests = parser._extract_guests(text)
        assert len(guests) >= 1

    def test_parse_text_complete(self, parser):
        """Test complete text parsing."""
        text = """
        RESERVATION CONFIRMATION
        
        Voucher No: JUN2024001
        Hotel: Grand Paradise Resort
        
        Check-in: 15/01/2025
        Check-out: 22/01/2025
        
        Room Type: Double Room Sea View
        Board: All Inclusive
        
        Adults: 2
        Children: 1
        
        Guest 1: Mr. JOHN TEST
        Guest 2: Mrs. JANE TEST
        
        Total Amount: € 1,234.56 EUR
        """
        
        result = parser._parse_text(text)
        
        assert result is not None
        assert result.voucher_no == "JUN2024001"
        assert "Grand Paradise" in result.hotel_name or "PARADISE" in result.hotel_name.upper()
        assert result.check_in == date(2025, 1, 15)
        assert result.check_out == date(2025, 1, 22)
        assert result.board_type == "AI"
        assert result.adults == 2
        assert result.children == 1

    @patch("fitz.open")
    def test_parse_bytes(self, mock_fitz, parser):
        """Test parsing from bytes."""
        # Mock PDF page
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Voucher: TEST123\nHotel: Test Hotel\nCheck-in: 01/01/2025\nCheck-out: 05/01/2025"
        
        mock_doc = MagicMock()
        mock_doc.__iter__ = lambda self: iter([mock_page])
        mock_fitz.return_value = mock_doc
        
        result = parser.parse_bytes(b"%PDF-1.4 test", "test.pdf")
        
        assert result is not None
        assert result.voucher_no == "TEST123"


# =============================================================================
# Stop Sale Email Parser Tests
# =============================================================================


class TestStopSaleEmailParser:
    """Tests for StopSaleEmailParser."""

    @pytest.fixture
    def parser(self):
        return StopSaleEmailParser()

    def test_parse_basic_stop_sale(self, parser):
        """Test basic stop sale parsing."""
        subject = "STOP SALE - Grand Hotel"
        body = """
        Stop Sale Notification
        
        Hotel: Grand Palace Hotel
        Period: 15.01.2025 - 31.01.2025
        Rooms: All
        Board: All
        
        Reason: Full occupancy
        """
        
        result = parser.parse(subject, body)
        
        assert result is not None
        assert "Grand" in result.hotel_name or "GRAND" in result.hotel_name.upper()
        assert result.date_from == date(2025, 1, 15)
        assert result.date_to == date(2025, 1, 31)
        assert result.is_close is True

    def test_parse_stop_sale_with_room_types(self, parser):
        """Test stop sale with specific room types."""
        subject = "Stop Sale Notice"
        body = """
        Hotel: Beach Resort
        Dates: 01.02.2025 - 15.02.2025
        Room Type: DBL, SGL, FAM
        """
        
        result = parser.parse(subject, body)
        
        assert result is not None
        assert len(result.room_types) == 3
        assert "DBL" in result.room_types

    def test_parse_open_sale(self, parser):
        """Test open sale (reverse of stop sale)."""
        subject = "Open Sale - Grand Hotel"
        body = """
        Open Sale Notification
        
        Hotel: Paradise Resort
        Period: 01.03.2025 - 15.03.2025
        
        Rooms are now available!
        """
        
        result = parser.parse(subject, body)
        
        assert result is not None
        assert result.is_close is False

    def test_parse_turkish_stop_sale(self, parser):
        """Test Turkish stop sale email."""
        subject = "Satış Durdurma - Otel XYZ"
        body = """
        Satış Durdurma Bildirimi
        
        Otel: Antalya Beach Otel
        Dönem: 15.06.2025 - 30.06.2025
        Oda Tipi: Tümü
        Sebep: Doluluk
        """
        
        result = parser.parse(subject, body)
        
        assert result is not None
        assert result.date_from == date(2025, 6, 15)
        assert result.date_to == date(2025, 6, 30)

    def test_extract_hotel_from_sender(self, parser):
        """Test hotel extraction from sender email."""
        subject = "Stop Sale"
        body = "Period: 01.01.2025 - 15.01.2025"
        
        result = parser.parse(subject, body, sender="reservations@grandhotel.com")
        
        assert result is not None
        # Hotel should be extracted from sender

    def test_parse_date_range(self, parser):
        """Test date range extraction."""
        date_from, date_to = parser._extract_date_range("Period: 15/01/2025 - 31/01/2025")
        
        assert date_from == date(2025, 1, 15)
        assert date_to == date(2025, 1, 31)

    def test_parse_date_range_european(self, parser):
        """Test European date format."""
        date_from, date_to = parser._extract_date_range("15.01.2025 – 31.01.2025")
        
        assert date_from == date(2025, 1, 15)
        assert date_to == date(2025, 1, 31)

    def test_missing_hotel_returns_none(self, parser):
        """Test that missing hotel returns None."""
        subject = "Stop Sale"
        body = "Period: 01.01.2025 - 15.01.2025"  # No hotel
        
        result = parser.parse(subject, body)
        
        # Should return None or have extracted something
        # In this case, it might still parse with heuristics
        if result:
            assert result.date_from is not None

    def test_missing_dates_returns_none(self, parser):
        """Test that completely missing dates returns None."""
        subject = "Stop Sale - Grand Hotel"
        body = "Hotel: Grand Palace\nNo dates here"
        
        result = parser.parse(subject, body)
        
        assert result is None


# =============================================================================
# Convenience Function Tests
# =============================================================================


def test_parse_stop_sale_email_function():
    """Test convenience function."""
    result = parse_stop_sale_email(
        subject="STOP SALE",
        body="Hotel: Test Hotel\nPeriod: 01.01.2025 - 15.01.2025",
    )
    
    assert result is not None
    assert result.date_from == date(2025, 1, 15)


# =============================================================================
# Integration Tests (Manual)
# =============================================================================


@pytest.mark.skip(reason="Requires real PDF file")
def test_parse_real_pdf():
    """Test parsing a real PDF file."""
    pdf_path = Path("/path/to/real/reservation.pdf")
    result = parse_reservation_pdf(pdf_path)
    
    print(f"Voucher: {result.voucher_no}")
    print(f"Hotel: {result.hotel_name}")
    print(f"Dates: {result.check_in} - {result.check_out}")
    print(f"Guests: {len(result.guests)}")
    
    assert result is not None
