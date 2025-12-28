"""PDF parser for extracting reservation data from Juniper PDFs."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from src.models.reservation import Guest, JuniperReservation
from src.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Extraction Patterns
# =============================================================================


@dataclass
class ExtractionPattern:
    """Pattern for extracting data from text."""

    name: str
    patterns: list[str]  # Regex patterns to try
    transform: callable = None  # Optional transform function


# Common patterns for travel industry PDFs
PATTERNS = {
    # Voucher/Booking Reference
    "voucher_no": ExtractionPattern(
        name="voucher_no",
        patterns=[
            r"(?:Voucher|Booking|Confirmation|Reference|Ref)[\s#:№]*([A-Z0-9]{4,20})",
            r"(?:Rezervasyon|Onay)[\s#:№]*([A-Z0-9]{4,20})",
            r"№\s*([A-Z0-9]{6,15})",
            r"Locator[:\s]+([A-Z0-9]{6,10})",
        ],
    ),
    # Hotel Name
    "hotel_name": ExtractionPattern(
        name="hotel_name",
        patterns=[
            r"(?:Hotel|Otel)[:\s]+(.+?)(?:\n|$|\|)",
            r"(?:Accommodation|Konaklama)[:\s]+(.+?)(?:\n|$)",
            r"(?:Property|Tesis)[:\s]+(.+?)(?:\n|$)",
        ],
    ),
    # Check-in Date
    "check_in": ExtractionPattern(
        name="check_in",
        patterns=[
            r"(?:Check[\s-]?in|Giriş|Arrival)[:\s]+(\d{1,2}[./]\d{1,2}[./]\d{2,4})",
            r"(?:Check[\s-]?in|Giriş)[:\s]+(\d{4}-\d{2}-\d{2})",
            r"(?:From|Başlangıç)[:\s]+(\d{1,2}[./]\d{1,2}[./]\d{2,4})",
        ],
    ),
    # Check-out Date
    "check_out": ExtractionPattern(
        name="check_out",
        patterns=[
            r"(?:Check[\s-]?out|Çıkış|Departure)[:\s]+(\d{1,2}[./]\d{1,2}[./]\d{2,4})",
            r"(?:Check[\s-]?out|Çıkış)[:\s]+(\d{4}-\d{2}-\d{2})",
            r"(?:To|Bitiş)[:\s]+(\d{1,2}[./]\d{1,2}[./]\d{2,4})",
        ],
    ),
    # Room Type
    "room_type": ExtractionPattern(
        name="room_type",
        patterns=[
            r"(?:Room[\s]?Type|Oda[\s]?Tipi|Category)[:\s]+(.+?)(?:\n|$|\|)",
            r"(?:DBL|SGL|TRP|FAM|SUI|STD)[\s\-]?(.+?)(?:\n|$)",
            r"(?:Double|Single|Triple|Family|Suite)[\s]?(?:Room)?(.+?)(?:\n|$)",
        ],
    ),
    # Board/Meal Plan
    "board_type": ExtractionPattern(
        name="board_type",
        patterns=[
            r"(?:Board|Meal[\s]?Plan|Pansiyon)[:\s]+(.+?)(?:\n|$|\|)",
            r"(?:AI|FB|HB|BB|RO|UAI)[\s\-]",
            r"(?:All[\s]?Inclusive|Full[\s]?Board|Half[\s]?Board|Bed[\s]?(?:&|and)[\s]?Breakfast|Room[\s]?Only)",
        ],
    ),
    # Adults
    "adults": ExtractionPattern(
        name="adults",
        patterns=[
            r"(?:Adults?|Yetişkin)[:\s]+(\d+)",
            r"(\d+)\s*(?:Adult|Yetişkin)",
            r"(?:Pax|Kişi)[:\s]+(\d+)",
        ],
    ),
    # Children
    "children": ExtractionPattern(
        name="children",
        patterns=[
            r"(?:Child(?:ren)?|Çocuk)[:\s]+(\d+)",
            r"(\d+)\s*(?:Child|Çocuk)",
        ],
    ),
    # Total Price
    "total_price": ExtractionPattern(
        name="total_price",
        patterns=[
            r"(?:Total|Toplam)[:\s]*([€$₺]?\s*[\d,.']+(?:\.\d{2})?)",
            r"(?:Amount|Tutar)[:\s]*([€$₺]?\s*[\d,.']+(?:\.\d{2})?)",
            r"(?:Price|Fiyat)[:\s]*([€$₺]?\s*[\d,.']+(?:\.\d{2})?)",
        ],
    ),
    # Currency
    "currency": ExtractionPattern(
        name="currency",
        patterns=[
            r"(?:Currency|Para\s*Birimi)[:\s]+(EUR|USD|TRY|GBP)",
            r"([€$₺£])",
            r"\b(EUR|USD|TRY|GBP|TL)\b",
        ],
    ),
}


# Guest name patterns
GUEST_PATTERNS = [
    # Mr/Mrs FIRSTNAME LASTNAME
    r"(?:Mr\.?|Mrs\.?|Ms\.?|Miss)\s+([A-Z][A-Za-z]+)\s+([A-Z][A-Za-z]+)",
    # LASTNAME, FIRSTNAME
    r"([A-Z][A-Z]+),\s*([A-Z][A-Za-z]+)",
    # FIRSTNAME LASTNAME (PAX 1, PAX 2, etc.)
    r"(?:PAX|Guest|Misafir)\s*\d*[:\s]+([A-Z][A-Za-z]+)\s+([A-Z][A-Za-z]+)",
    # Adult 1: FIRSTNAME LASTNAME
    r"(?:Adult|Yetişkin)\s*\d*[:\s]+([A-Z][A-Za-z]+)\s+([A-Z][A-Za-z]+)",
]


# =============================================================================
# PDF Parser
# =============================================================================


class JuniperPdfParser:
    """
    Parser for Juniper hotel reservation PDFs.

    This parser extracts reservation data from PDF documents using
    pattern matching and heuristics common in travel industry documents.
    """

    def __init__(self):
        """Initialize parser."""
        self.patterns = PATTERNS
        self.guest_patterns = GUEST_PATTERNS

    def parse(self, pdf_path: str | Path) -> JuniperReservation | None:
        """
        Parse a Juniper reservation PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            JuniperReservation object or None if parsing fails
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            logger.error("pdf_not_found", path=str(pdf_path))
            return None

        logger.info("parsing_pdf", path=str(pdf_path))

        try:
            # Extract text from PDF
            text = self._extract_text(pdf_path)

            if not text:
                logger.error("pdf_empty_text", path=str(pdf_path))
                return None

            # Parse the text
            return self._parse_text(text, source_file=str(pdf_path))

        except Exception as e:
            logger.error("pdf_parse_error", path=str(pdf_path), error=str(e))
            return None

    def parse_bytes(self, pdf_bytes: bytes, source_name: str = "memory") -> JuniperReservation | None:
        """
        Parse a PDF from bytes.

        Args:
            pdf_bytes: PDF file content as bytes
            source_name: Name for logging

        Returns:
            JuniperReservation object or None
        """
        logger.info("parsing_pdf_bytes", source=source_name, size=len(pdf_bytes))

        try:
            # Open PDF from bytes
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text = ""

            for page in doc:
                text += page.get_text()

            doc.close()

            if not text:
                logger.error("pdf_empty_text", source=source_name)
                return None

            return self._parse_text(text, source_file=source_name)

        except Exception as e:
            logger.error("pdf_parse_bytes_error", source=source_name, error=str(e))
            return None

    def _extract_text(self, pdf_path: Path) -> str:
        """
        Extract all text from PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Extracted text
        """
        doc = fitz.open(pdf_path)
        text = ""

        for page in doc:
            text += page.get_text()

        doc.close()

        logger.debug("pdf_text_extracted", chars=len(text))
        return text

    def _parse_text(self, text: str, source_file: str = "") -> JuniperReservation | None:
        """
        Parse extracted PDF text into JuniperReservation.

        Args:
            text: Extracted text from PDF
            source_file: Source file for reference

        Returns:
            JuniperReservation or None
        """
        # Extract each field
        voucher_no = self._extract_field("voucher_no", text)
        hotel_name = self._extract_field("hotel_name", text)
        check_in_str = self._extract_field("check_in", text)
        check_out_str = self._extract_field("check_out", text)
        room_type = self._extract_field("room_type", text) or "Standard"
        board_type = self._extract_field("board_type", text) or "AI"
        adults_str = self._extract_field("adults", text)
        children_str = self._extract_field("children", text)
        price_str = self._extract_field("total_price", text)
        currency = self._extract_field("currency", text) or "EUR"

        # Validate required fields
        if not voucher_no:
            logger.warning("pdf_missing_voucher", source=source_file)
            voucher_no = self._generate_voucher_from_text(text)

        if not hotel_name:
            logger.warning("pdf_missing_hotel", source=source_file)
            hotel_name = self._extract_hotel_name_heuristic(text)

        if not check_in_str or not check_out_str:
            logger.warning("pdf_missing_dates", source=source_file)
            check_in_str, check_out_str = self._extract_dates_heuristic(text)

        # Parse dates
        check_in = self._parse_date(check_in_str) if check_in_str else date.today()
        check_out = self._parse_date(check_out_str) if check_out_str else date.today()

        # Parse numbers
        adults = int(adults_str) if adults_str and adults_str.isdigit() else 2
        children = int(children_str) if children_str and children_str.isdigit() else 0

        # Parse price
        total_price = self._parse_price(price_str) if price_str else None

        # Normalize board type
        board_type = self._normalize_board_type(board_type)

        # Extract room type code
        room_type_code = self._extract_room_type_code(room_type)

        # Extract guests
        guests = self._extract_guests(text)

        # Build reservation
        reservation = JuniperReservation(
            voucher_no=voucher_no or f"AUTO-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            hotel_name=hotel_name or "Unknown Hotel",
            check_in=check_in,
            check_out=check_out,
            room_type=room_type_code,
            room_type_name=room_type,
            board_type=board_type,
            adults=adults,
            children=children,
            total_price=total_price,
            currency=self._normalize_currency(currency),
            guests=guests,
        )

        logger.info(
            "pdf_parsed_successfully",
            voucher=reservation.voucher_no,
            hotel=reservation.hotel_name,
            check_in=str(reservation.check_in),
            check_out=str(reservation.check_out),
            guests=len(reservation.guests),
        )

        return reservation

    def _extract_field(self, field_name: str, text: str) -> str | None:
        """
        Extract a field value using configured patterns.

        Args:
            field_name: Name of field to extract
            text: Text to search

        Returns:
            Extracted value or None
        """
        pattern_config = self.patterns.get(field_name)
        if not pattern_config:
            return None

        for pattern in pattern_config.patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1) if match.lastindex else match.group(0)
                value = value.strip()

                if pattern_config.transform:
                    value = pattern_config.transform(value)

                logger.debug(
                    "field_extracted",
                    field=field_name,
                    value=value[:50] if len(value) > 50 else value,
                )
                return value

        return None

    def _extract_guests(self, text: str) -> list[Guest]:
        """
        Extract guest information from text.

        Args:
            text: PDF text

        Returns:
            List of Guest objects
        """
        guests = []
        seen_names = set()

        for pattern in self.guest_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple) and len(match) >= 2:
                    first_name, last_name = match[0], match[1]
                    # Normalize
                    first_name = first_name.strip().upper()
                    last_name = last_name.strip().upper()

                    # Deduplicate
                    key = f"{first_name}|{last_name}"
                    if key in seen_names:
                        continue
                    seen_names.add(key)

                    # Determine title
                    title = "Mr"  # Default
                    if re.search(r"Mrs|Bayan|Female", text, re.IGNORECASE):
                        title = "Mrs"

                    guests.append(
                        Guest(
                            title=title,
                            first_name=first_name,
                            last_name=last_name,
                        )
                    )

        logger.debug("guests_extracted", count=len(guests))
        return guests

    def _parse_date(self, date_str: str) -> date | None:
        """
        Parse date string to date object.

        Args:
            date_str: Date string in various formats

        Returns:
            date object or None
        """
        if not date_str:
            return None

        date_str = date_str.strip()

        # Try various formats
        formats = [
            "%d/%m/%Y",
            "%d.%m.%Y",
            "%Y-%m-%d",
            "%d/%m/%y",
            "%d.%m.%y",
            "%d-%m-%Y",
            "%Y/%m/%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        logger.warning("date_parse_failed", date_str=date_str)
        return None

    def _parse_price(self, price_str: str) -> Decimal | None:
        """
        Parse price string to Decimal.

        Args:
            price_str: Price string

        Returns:
            Decimal or None
        """
        if not price_str:
            return None

        # Remove currency symbols and spaces
        price_str = re.sub(r"[€$₺£\s]", "", price_str)

        # Handle European format (1.234,56 -> 1234.56)
        if "," in price_str and "." in price_str:
            if price_str.index(",") > price_str.index("."):
                price_str = price_str.replace(".", "").replace(",", ".")
            else:
                price_str = price_str.replace(",", "")
        elif "," in price_str:
            price_str = price_str.replace(",", ".")

        try:
            return Decimal(price_str)
        except Exception:
            logger.warning("price_parse_failed", price_str=price_str)
            return None

    def _normalize_board_type(self, board: str) -> str:
        """Normalize board type to standard code."""
        if not board:
            return "AI"

        board_upper = board.upper()

        mappings = {
            "ALL INCLUSIVE": "AI",
            "ULTRA ALL INCLUSIVE": "UAI",
            "FULL BOARD": "FB",
            "HALF BOARD": "HB",
            "BED AND BREAKFAST": "BB",
            "BED & BREAKFAST": "BB",
            "ROOM ONLY": "RO",
            "BREAKFAST": "BB",
        }

        for key, value in mappings.items():
            if key in board_upper:
                return value

        # Check for codes
        for code in ["AI", "UAI", "FB", "HB", "BB", "RO"]:
            if code in board_upper:
                return code

        return "AI"  # Default

    def _normalize_currency(self, currency: str) -> str:
        """Normalize currency to ISO code."""
        if not currency:
            return "EUR"

        mappings = {
            "€": "EUR",
            "$": "USD",
            "₺": "TRY",
            "£": "GBP",
            "TL": "TRY",
        }

        return mappings.get(currency, currency.upper()[:3])

    def _extract_room_type_code(self, room_type: str) -> str:
        """Extract room type code from description."""
        if not room_type:
            return "DBL"

        room_upper = room_type.upper()

        codes = {
            "DOUBLE": "DBL",
            "SINGLE": "SGL",
            "TRIPLE": "TRP",
            "FAMILY": "FAM",
            "SUITE": "SUI",
            "STANDARD": "STD",
            "SUPERIOR": "SUP",
            "DELUXE": "DLX",
            "JUNIOR": "JNR",
            "VILLA": "VIL",
        }

        for key, value in codes.items():
            if key in room_upper:
                return value

        # Check for codes directly
        for code in ["DBL", "SGL", "TRP", "FAM", "SUI", "STD"]:
            if code in room_upper:
                return code

        return "DBL"  # Default

    def _generate_voucher_from_text(self, text: str) -> str | None:
        """Try to generate voucher from any number pattern."""
        # Look for any 6+ digit number sequence
        match = re.search(r"\b([A-Z]?\d{6,12})\b", text)
        if match:
            return match.group(1)
        return None

    def _extract_hotel_name_heuristic(self, text: str) -> str | None:
        """Extract hotel name using heuristics."""
        # Look for common hotel keywords followed by name
        patterns = [
            r"(?:Hotel|Otel|Resort|Palace|Beach)\s+([A-Za-z\s&'-]+?)(?:\n|$|,|\|)",
            r"([A-Za-z\s&'-]+?)\s+(?:Hotel|Otel|Resort|Palace|Beach)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if len(name) > 3 and len(name) < 50:
                    return name

        return None

    def _extract_dates_heuristic(self, text: str) -> tuple[str | None, str | None]:
        """Extract dates using heuristic patterns."""
        # Look for date range patterns
        range_pattern = r"(\d{1,2}[./]\d{1,2}[./]\d{2,4})\s*[-–to]+\s*(\d{1,2}[./]\d{1,2}[./]\d{2,4})"
        match = re.search(range_pattern, text)
        if match:
            return match.group(1), match.group(2)

        # Look for individual dates
        date_pattern = r"\d{1,2}[./]\d{1,2}[./]\d{2,4}"
        dates = re.findall(date_pattern, text)

        if len(dates) >= 2:
            return dates[0], dates[1]
        elif len(dates) == 1:
            return dates[0], None

        return None, None


# =============================================================================
# Parser Factory
# =============================================================================


def create_parser() -> JuniperPdfParser:
    """Create a configured PDF parser instance."""
    return JuniperPdfParser()


def parse_reservation_pdf(pdf_path: str | Path) -> JuniperReservation | None:
    """
    Convenience function to parse a reservation PDF.

    Args:
        pdf_path: Path to PDF file

    Returns:
        JuniperReservation or None
    """
    parser = create_parser()
    return parser.parse(pdf_path)


def parse_reservation_bytes(pdf_bytes: bytes, source_name: str = "memory") -> JuniperReservation | None:
    """
    Convenience function to parse PDF from bytes.

    Args:
        pdf_bytes: PDF content
        source_name: Name for logging

    Returns:
        JuniperReservation or None
    """
    parser = create_parser()
    return parser.parse_bytes(pdf_bytes, source_name)
