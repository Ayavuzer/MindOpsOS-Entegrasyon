"""Stop sale extraction service using Gemini AI."""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional
import re

from src.utils.logger import get_logger

from ..client import GeminiClient
from ..models import StopSaleExtraction

logger = get_logger(__name__)


@dataclass
class StopSaleExtractionResult:
    """Result of stop sale extraction."""
    
    success: bool
    extraction: Optional[StopSaleExtraction] = None
    used_ai: bool = False
    fallback_reason: Optional[str] = None
    error: Optional[str] = None
    
    # Extracted fields (convenience accessors)
    @property
    def hotel_name(self) -> str | None:
        return self.extraction.hotel_name if self.extraction else None
    
    @property
    def date_from(self) -> date | None:
        return self.extraction.date_from if self.extraction else None
    
    @property
    def date_to(self) -> date | None:
        return self.extraction.date_to if self.extraction else None
    
    @property
    def room_types(self) -> list[str]:
        return self.extraction.room_types if self.extraction else []
    
    @property
    def is_close(self) -> bool:
        return self.extraction.is_close if self.extraction else True
    
    @property
    def confidence(self) -> float:
        return self.extraction.extraction_confidence if self.extraction else 0.0


class StopSaleExtractor:
    """
    Stop sale extraction service using Gemini AI.
    
    Extracts structured data from stop sale emails:
    - Hotel name
    - Date range (from/to)
    - Room types (if specified)
    - Board types (if specified)
    - Close/Open status
    - Reason (if mentioned)
    
    Falls back to regex-based extraction when AI is unavailable.
    """
    
    # Common room type patterns
    ROOM_TYPE_PATTERNS = {
        r"\b(DBL|DOUBLE)\b": "DBL",
        r"\b(SGL|SINGLE)\b": "SGL",
        r"\b(TRP|TRIPLE)\b": "TRP",
        r"\b(FAM|FAMILY)\b": "FAM",
        r"\b(SUI|SUITE)\b": "SUI",
        r"\b(STD|STANDARD)\b": "STD",
        r"\b(SUP|SUPERIOR)\b": "SUP",
        r"\b(DLX|DELUXE)\b": "DLX",
    }
    
    # Date patterns for various formats
    DATE_PATTERNS = [
        # DD.MM.YYYY or DD.MM.YY
        r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})",
        # DD/MM/YYYY or DD/MM/YY
        r"(\d{1,2})/(\d{1,2})/(\d{2,4})",
        # YYYY-MM-DD
        r"(\d{4})-(\d{1,2})-(\d{1,2})",
        # DD-MM-YYYY
        r"(\d{1,2})-(\d{1,2})-(\d{4})",
    ]
    
    # Hotel name extraction patterns
    HOTEL_PATTERNS = [
        # "Hotel Name Hotel" or "Hotel Name Resort"
        r"([A-Za-z\s\-']+(?:Hotel|Resort|Palace|Beach|Suites))",
        # After "Hotel:" or "Otel:"
        r"(?:Hotel|Otel|Property)[:\s]+([A-Za-z\s\-']+)",
        # In subject line before "stop sale"
        r"^([A-Za-z\s\-']+?)[\s\-–]+(?:stop|STOP)",
    ]
    
    def __init__(
        self,
        api_key: str | None = None,
        confidence_threshold: float = 0.80,
    ):
        """
        Initialize extractor.
        
        Args:
            api_key: Gemini API key
            confidence_threshold: Minimum confidence to accept AI result
        """
        self.client = GeminiClient(api_key=api_key)
        self.confidence_threshold = confidence_threshold
    
    @property
    def ai_available(self) -> bool:
        """Check if AI extraction is available."""
        return self.client.is_available
    
    async def extract(
        self,
        subject: str,
        body: str,
        email_date: str | None = None,
        use_fallback: bool = True,
    ) -> StopSaleExtractionResult:
        """
        Extract stop sale data from email.
        
        Args:
            subject: Email subject
            body: Email body text
            email_date: Email date for context
            use_fallback: Whether to use regex fallback when AI fails
            
        Returns:
            StopSaleExtractionResult with extracted data
        """
        logger.info(
            "stop_sale_extraction_start",
            subject=subject[:50] if subject else "",
            ai_available=self.ai_available,
        )
        
        # Try AI extraction first
        if self.ai_available:
            result = await self._extract_with_ai(subject, body, email_date)
            
            # Check if result is usable
            if result.success and result.confidence >= self.confidence_threshold:
                # Post-process to normalize data
                result = self._post_process(result)
                
                logger.info(
                    "stop_sale_extraction_ai_success",
                    hotel=result.hotel_name,
                    date_from=str(result.date_from),
                    date_to=str(result.date_to),
                    confidence=result.confidence,
                )
                return result
            
            # AI result below threshold
            if result.extraction:
                logger.warning(
                    "stop_sale_extraction_ai_low_confidence",
                    confidence=result.confidence,
                    threshold=self.confidence_threshold,
                )
        
        # Fallback to regex-based extraction
        if use_fallback:
            fallback_result = self._extract_with_regex(subject, body, email_date)
            logger.info(
                "stop_sale_extraction_fallback_used",
                hotel=fallback_result.hotel_name,
                reason=fallback_result.fallback_reason,
            )
            return fallback_result
        
        # No extraction available
        return StopSaleExtractionResult(
            success=False,
            error="AI unavailable and fallback disabled",
        )
    
    async def _extract_with_ai(
        self,
        subject: str,
        body: str,
        email_date: str | None,
    ) -> StopSaleExtractionResult:
        """Extract using Gemini AI."""
        try:
            extraction = await self.client.extract_stop_sale(
                subject=subject,
                body=body,
                email_date=email_date,
            )
            
            if extraction:
                return StopSaleExtractionResult(
                    success=True,
                    extraction=extraction,
                    used_ai=True,
                )
            
            return StopSaleExtractionResult(
                success=False,
                error="AI returned no result",
            )
            
        except Exception as e:
            logger.error("stop_sale_extraction_ai_error", error=str(e))
            return StopSaleExtractionResult(
                success=False,
                error=f"AI error: {str(e)}",
            )
    
    def _extract_with_regex(
        self,
        subject: str,
        body: str,
        email_date: str | None,
    ) -> StopSaleExtractionResult:
        """Fallback extraction using regex patterns."""
        combined_text = f"{subject}\n{body}"
        
        # Extract hotel name
        hotel_name = self._extract_hotel_name(subject, body)
        
        # Extract dates
        date_from, date_to = self._extract_dates(combined_text, email_date)
        
        # Extract room types
        room_types = self._extract_room_types(combined_text)
        
        # Detect if it's a close or open sale
        is_close = self._detect_close_status(combined_text)
        
        # Extract reason if mentioned
        reason = self._extract_reason(combined_text)
        
        # Calculate confidence based on what was extracted
        confidence = self._calculate_confidence(hotel_name, date_from, date_to)
        
        if not hotel_name or not date_from or not date_to:
            return StopSaleExtractionResult(
                success=False,
                fallback_reason="Could not extract required fields",
                error=f"Missing: hotel={not hotel_name}, from={not date_from}, to={not date_to}",
            )
        
        extraction = StopSaleExtraction(
            hotel_name=hotel_name,
            date_from=date_from,
            date_to=date_to,
            room_types=room_types,
            board_types=[],
            is_close=is_close,
            reason=reason,
            extraction_confidence=confidence,
        )
        
        return StopSaleExtractionResult(
            success=True,
            extraction=extraction,
            used_ai=False,
            fallback_reason="Regex-based extraction",
        )
    
    def _extract_hotel_name(self, subject: str, body: str) -> str | None:
        """Extract hotel name from email."""
        # Try subject first
        for pattern in self.HOTEL_PATTERNS:
            match = re.search(pattern, subject, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Clean up common suffixes
                name = re.sub(r"\s*(Hotel|Resort|Palace|Otel)$", "", name, flags=re.IGNORECASE)
                if len(name) > 3:
                    return name.strip()
        
        # Try body
        for pattern in self.HOTEL_PATTERNS:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                name = re.sub(r"\s*(Hotel|Resort|Palace|Otel)$", "", name, flags=re.IGNORECASE)
                if len(name) > 3:
                    return name.strip()
        
        # Last resort: extract from subject
        # Remove common keywords and take remaining words
        cleaned = re.sub(
            r"(stop\s*sale|stopsale|satış\s*kapatma|стоп.?продажа)",
            "", subject, flags=re.IGNORECASE
        )
        cleaned = re.sub(r"[-–:|\[\]()]", " ", cleaned)
        words = [w for w in cleaned.split() if len(w) > 2]
        if words:
            return " ".join(words[:3]).strip()
        
        return None
    
    def _extract_dates(
        self,
        text: str,
        email_date: str | None,
    ) -> tuple[date | None, date | None]:
        """Extract date range from text."""
        dates = []
        
        for pattern in self.DATE_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    parsed_date = self._parse_date_tuple(match, pattern)
                    if parsed_date:
                        dates.append(parsed_date)
                except ValueError:
                    continue
        
        # Sort and deduplicate
        dates = sorted(set(dates))
        
        if len(dates) >= 2:
            return dates[0], dates[-1]
        elif len(dates) == 1:
            # Single date found, assume it's the start date
            # End date could be same day or we need to look for "till" patterns
            return dates[0], dates[0]
        
        return None, None
    
    def _parse_date_tuple(
        self,
        match: tuple,
        pattern: str,
    ) -> date | None:
        """Parse date from regex match tuple."""
        try:
            if "YYYY" in pattern or pattern.startswith(r"(\d{4})"):
                # YYYY-MM-DD format
                year, month, day = int(match[0]), int(match[1]), int(match[2])
            else:
                # DD.MM.YYYY or DD/MM/YYYY format
                day, month, year = int(match[0]), int(match[1]), int(match[2])
                # Handle 2-digit year
                if year < 100:
                    year += 2000
            
            return date(year, month, day)
        except (ValueError, IndexError):
            return None
    
    def _extract_room_types(self, text: str) -> list[str]:
        """Extract room type codes from text."""
        room_types = set()
        
        for pattern, code in self.ROOM_TYPE_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                room_types.add(code)
        
        # Check for "all rooms" indicator
        if re.search(r"all\s*rooms|tüm\s*oda|все\s*номера", text, re.IGNORECASE):
            return []  # Empty means all rooms
        
        return list(room_types)
    
    def _detect_close_status(self, text: str) -> bool:
        """Detect if this is a close (stop) or open (release) sale."""
        text_lower = text.lower()
        
        # Open sale indicators
        open_patterns = ["open sale", "release", "açıldı", "открыто", "available again"]
        for pattern in open_patterns:
            if pattern in text_lower:
                return False
        
        # Default to close (stop sale)
        return True
    
    def _extract_reason(self, text: str) -> str | None:
        """Extract stop sale reason if mentioned."""
        reason_patterns = [
            r"(?:reason|sebep|причина)[:\s]+([^\n]+)",
            r"(?:due to|nedeniyle|из-за)[:\s]+([^\n]+)",
            r"(?:because|çünkü)[:\s]+([^\n]+)",
        ]
        
        for pattern in reason_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                reason = match.group(1).strip()
                if len(reason) > 3:
                    return reason[:100]  # Limit length
        
        # Common reasons in text
        common_reasons = [
            ("renovation", "renovation"),
            ("tadilat", "renovation"),
            ("ремонт", "renovation"),
            ("full", "fully booked"),
            ("dolu", "fully booked"),
            ("event", "special event"),
            ("etkinlik", "special event"),
        ]
        
        text_lower = text.lower()
        for keyword, reason in common_reasons:
            if keyword in text_lower:
                return reason
        
        return None
    
    def _calculate_confidence(
        self,
        hotel_name: str | None,
        date_from: date | None,
        date_to: date | None,
    ) -> float:
        """Calculate extraction confidence score."""
        score = 0.0
        
        if hotel_name:
            score += 0.3
            if len(hotel_name) > 5:
                score += 0.1
        
        if date_from:
            score += 0.25
        
        if date_to:
            score += 0.25
            if date_from and date_to > date_from:
                score += 0.1  # Bonus for valid date range
        
        return min(score, 1.0)
    
    def _post_process(
        self,
        result: StopSaleExtractionResult,
    ) -> StopSaleExtractionResult:
        """Post-process AI extraction result to normalize data."""
        if not result.extraction:
            return result
        
        extraction = result.extraction
        
        # Normalize hotel name
        hotel_name = extraction.hotel_name
        hotel_name = re.sub(r"\s*(Hotel|Resort|Palace|Otel)$", "", hotel_name, flags=re.IGNORECASE)
        hotel_name = hotel_name.strip()
        
        # Normalize room types
        room_types = []
        for rt in extraction.room_types:
            rt_upper = rt.upper()
            # Map common variations
            if rt_upper in ["DOUBLE", "TWIN"]:
                rt_upper = "DBL"
            elif rt_upper in ["SINGLE"]:
                rt_upper = "SGL"
            elif rt_upper in ["TRIPLE"]:
                rt_upper = "TRP"
            room_types.append(rt_upper)
        
        # Create updated extraction
        updated = StopSaleExtraction(
            hotel_name=hotel_name,
            date_from=extraction.date_from,
            date_to=extraction.date_to,
            room_types=room_types,
            board_types=extraction.board_types,
            is_close=extraction.is_close,
            reason=extraction.reason,
            extraction_confidence=extraction.extraction_confidence,
        )
        
        return StopSaleExtractionResult(
            success=True,
            extraction=updated,
            used_ai=result.used_ai,
            fallback_reason=result.fallback_reason,
        )
