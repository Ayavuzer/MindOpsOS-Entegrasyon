"""Email body parser for stop sale and simple text reservations."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from src.models.stopsale import StopSale
from src.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Stop Sale Parser
# =============================================================================


class StopSaleEmailParser:
    """
    Parser for extracting stop sale information from email content.

    Handles various email formats from hotels announcing stop sales.
    """

    # Patterns for hotel name
    HOTEL_PATTERNS = [
        r"(?:Hotel|Otel)[:\s]+([A-Za-z0-9\s&'-]+?)(?:\n|$|,|\|)",
        r"(?:Property|Tesis)[:\s]+([A-Za-z0-9\s&'-]+?)(?:\n|$)",
        r"(?:From|Gönderen)[:\s]+.+?([A-Za-z\s]+?)(?:Hotel|Otel|Resort)",
        r"([A-Za-z\s&'-]+?)\s+(?:Hotel|Otel|Resort)",
    ]

    # Patterns for date ranges
    DATE_RANGE_PATTERNS = [
        # "15.01.2025 - 31.01.2025"
        r"(\d{1,2}[./]\d{1,2}[./]\d{2,4})\s*[-–to]+\s*(\d{1,2}[./]\d{1,2}[./]\d{2,4})",
        # "Period: 15.01.2025 - 31.01.2025"
        r"(?:Period|Dönem|Dates)[:\s]+(\d{1,2}[./]\d{1,2}[./]\d{2,4})\s*[-–to]+\s*(\d{1,2}[./]\d{1,2}[./]\d{2,4})",
        # "From 15.01.2025 to 31.01.2025"
        r"(?:From|Başlangıç)[:\s]+(\d{1,2}[./]\d{1,2}[./]\d{2,4}).*?(?:To|Bitiş)[:\s]+(\d{1,2}[./]\d{1,2}[./]\d{2,4})",
    ]

    # Patterns for room types
    ROOM_TYPE_PATTERNS = [
        r"(?:Room[\s]?Type|Oda[\s]?Tipi|Rooms)[:\s]+([A-Za-z0-9\s,/]+?)(?:\n|$)",
        r"(?:Category|Kategori)[:\s]+([A-Za-z0-9\s,/]+?)(?:\n|$)",
    ]

    # Patterns for board types
    BOARD_PATTERNS = [
        r"(?:Board|Pansiyon|Meal)[:\s]+([A-Za-z\s,/&]+?)(?:\n|$)",
    ]

    # Keywords indicating "all" rooms or boards
    ALL_KEYWORDS = ["all", "tümü", "hepsi", "tüm", "all rooms", "tüm odalar"]

    def parse(
        self,
        subject: str,
        body: str,
        sender: str | None = None,
        email_date: date | None = None,
    ) -> StopSale | None:
        """
        Parse stop sale information from email.

        Args:
            subject: Email subject
            body: Email body text
            sender: Email sender
            email_date: Email date

        Returns:
            StopSale object or None if parsing fails
        """
        combined_text = f"{subject}\n{body}"

        logger.debug(
            "parsing_stop_sale_email",
            subject=subject[:50] if subject else "",
            body_length=len(body) if body else 0,
        )

        # Extract hotel name
        hotel_name = self._extract_hotel_name(combined_text, sender)
        if not hotel_name:
            logger.warning("stop_sale_missing_hotel", subject=subject[:50])
            return None

        # Extract date range
        date_from, date_to = self._extract_date_range(combined_text)
        if not date_from or not date_to:
            logger.warning("stop_sale_missing_dates", subject=subject[:50])
            return None

        # Extract room types (optional)
        room_types = self._extract_room_types(combined_text)

        # Extract board types (optional)
        board_types = self._extract_board_types(combined_text)

        # Check if it's an open sale (reverse stop sale)
        is_close = self._is_close_sale(combined_text)

        # Extract reason (optional)
        reason = self._extract_reason(combined_text)

        stop_sale = StopSale(
            hotel_name=hotel_name,
            date_from=date_from,
            date_to=date_to,
            room_types=room_types,
            board_types=board_types,
            is_close=is_close,
            reason=reason,
            source_email_date=email_date,
        )

        logger.info(
            "stop_sale_parsed",
            hotel=hotel_name,
            date_from=str(date_from),
            date_to=str(date_to),
            rooms=len(room_types),
            boards=len(board_types),
            is_close=is_close,
        )

        return stop_sale

    def _extract_hotel_name(self, text: str, sender: str | None = None) -> str | None:
        """Extract hotel name from text or sender."""
        # Try patterns first
        for pattern in self.HOTEL_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                name = match.group(1).strip()
                if len(name) > 3 and len(name) < 80:
                    return self._clean_hotel_name(name)

        # Try to extract from sender email
        if sender:
            # reservations@grandhotel.com -> Grand Hotel
            sender_match = re.search(r"@([a-z]+)(?:hotel|resort|palace)?", sender.lower())
            if sender_match:
                name = sender_match.group(1).title()
                if len(name) > 2:
                    return name

        return None

    def _clean_hotel_name(self, name: str) -> str:
        """Clean hotel name."""
        # Remove common suffixes
        name = re.sub(r"\s*(Hotel|Otel|Resort|Palace|Beach)\s*$", "", name, flags=re.IGNORECASE)
        # Remove special characters at end
        name = name.rstrip(".,;:-")
        return name.strip()

    def _extract_date_range(self, text: str) -> tuple[date | None, date | None]:
        """Extract date range from text."""
        for pattern in self.DATE_RANGE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                date_from = self._parse_date(match.group(1))
                date_to = self._parse_date(match.group(2))
                if date_from and date_to:
                    return date_from, date_to

        # Fallback: find any two dates
        date_pattern = r"\d{1,2}[./]\d{1,2}[./]\d{2,4}"
        dates = re.findall(date_pattern, text)

        parsed_dates = []
        for d in dates:
            parsed = self._parse_date(d)
            if parsed:
                parsed_dates.append(parsed)

        if len(parsed_dates) >= 2:
            parsed_dates.sort()
            return parsed_dates[0], parsed_dates[-1]

        return None, None

    def _parse_date(self, date_str: str) -> date | None:
        """Parse date string."""
        if not date_str:
            return None

        date_str = date_str.strip()
        formats = [
            "%d/%m/%Y",
            "%d.%m.%Y",
            "%Y-%m-%d",
            "%d/%m/%y",
            "%d.%m.%y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        return None

    def _extract_room_types(self, text: str) -> list[str]:
        """Extract room types from text."""
        for pattern in self.ROOM_TYPE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1).strip().lower()

                # Check for "all" keywords
                if any(kw in value for kw in self.ALL_KEYWORDS):
                    return []  # Empty = all rooms

                # Split by comma or /
                types = re.split(r"[,/]", value)
                return [t.strip().upper() for t in types if t.strip()]

        return []  # Empty = all rooms

    def _extract_board_types(self, text: str) -> list[str]:
        """Extract board types from text."""
        for pattern in self.BOARD_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1).strip().lower()

                # Check for "all" keywords
                if any(kw in value for kw in self.ALL_KEYWORDS):
                    return []  # Empty = all boards

                # Split by comma or /
                types = re.split(r"[,/]", value)
                return [self._normalize_board(t.strip()) for t in types if t.strip()]

        return []  # Empty = all boards

    def _normalize_board(self, board: str) -> str:
        """Normalize board type to code."""
        board_upper = board.upper()
        mappings = {
            "ALL INCLUSIVE": "AI",
            "FULL BOARD": "FB",
            "HALF BOARD": "HB",
            "BED AND BREAKFAST": "BB",
            "ROOM ONLY": "RO",
        }

        for key, value in mappings.items():
            if key in board_upper:
                return value

        return board_upper[:3]

    def _is_close_sale(self, text: str) -> bool:
        """Determine if this is a close (stop) or open sale."""
        text_lower = text.lower()

        # Keywords for open sale
        open_keywords = ["open sale", "satış açıldı", "available", "müsait", "released"]

        for keyword in open_keywords:
            if keyword in text_lower:
                return False  # Open sale

        return True  # Default: stop (close) sale

    def _extract_reason(self, text: str) -> str | None:
        """Extract reason for stop sale."""
        patterns = [
            r"(?:Reason|Sebep|Neden)[:\s]+(.+?)(?:\n|$)",
            r"(?:Note|Not)[:\s]+(.+?)(?:\n|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                reason = match.group(1).strip()
                if len(reason) > 2:
                    return reason[:200]

        return None


# =============================================================================
# Convenience Functions
# =============================================================================


def parse_stop_sale_email(
    subject: str,
    body: str,
    sender: str | None = None,
    email_date: date | None = None,
) -> StopSale | None:
    """
    Convenience function to parse stop sale from email.

    Args:
        subject: Email subject
        body: Email body
        sender: Optional sender address
        email_date: Optional email date

    Returns:
        StopSale or None
    """
    parser = StopSaleEmailParser()
    return parser.parse(subject, body, sender, email_date)
