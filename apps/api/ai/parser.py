"""AI-powered email parser using Gemini."""

from dataclasses import dataclass
from typing import Optional

from src.utils.logger import get_logger

from .client import GeminiClient
from .models import EmailClassification, StopSaleExtraction, ReservationExtraction

logger = get_logger(__name__)


@dataclass
class AIParseResult:
    """Result of AI email parsing."""
    
    success: bool
    classification: Optional[EmailClassification] = None
    stop_sale: Optional[StopSaleExtraction] = None
    reservation: Optional[ReservationExtraction] = None
    error: Optional[str] = None
    
    @property
    def email_type(self) -> str | None:
        """Get classified email type."""
        if self.classification:
            return self.classification.email_type
        return None
    
    @property
    def confidence(self) -> float:
        """Get classification confidence."""
        if self.classification:
            return self.classification.confidence
        return 0.0


class AIEmailParser:
    """
    AI-powered email parser using Google Gemini.
    
    Classifies emails and extracts structured data for
    stop sales and reservations.
    """
    
    def __init__(
        self,
        api_key: str | None = None,
        confidence_threshold: float = 0.85,
    ):
        """
        Initialize AI parser.
        
        Args:
            api_key: Gemini API key
            confidence_threshold: Minimum confidence to accept result
        """
        self.client = GeminiClient(api_key=api_key)
        self.confidence_threshold = confidence_threshold
    
    @property
    def is_available(self) -> bool:
        """Check if AI parsing is available."""
        return self.client.is_available
    
    async def parse(
        self,
        subject: str,
        body: str,
        email_date: str | None = None,
    ) -> AIParseResult:
        """
        Parse email using AI.
        
        Args:
            subject: Email subject
            body: Email body text
            email_date: Optional email date for context
            
        Returns:
            AIParseResult with classification and extracted data
        """
        if not self.is_available:
            return AIParseResult(
                success=False,
                error="AI parser not available (API key not configured)",
            )
        
        try:
            # Step 1: Classify email
            logger.info("ai_classification_start", subject=subject[:50])
            
            classification = await self.client.classify_email(
                subject=subject,
                body=body,
            )
            
            if not classification:
                return AIParseResult(
                    success=False,
                    error="Classification failed",
                )
            
            logger.info(
                "ai_classification_complete",
                email_type=classification.email_type,
                confidence=classification.confidence,
                language=classification.language,
            )
            
            # Check confidence threshold
            if classification.confidence < self.confidence_threshold:
                logger.warning(
                    "ai_confidence_below_threshold",
                    confidence=classification.confidence,
                    threshold=self.confidence_threshold,
                )
                return AIParseResult(
                    success=False,
                    classification=classification,
                    error=f"Low confidence: {classification.confidence:.2f} < {self.confidence_threshold}",
                )
            
            # Step 2: Extract based on type
            stop_sale = None
            reservation = None
            
            if classification.email_type == "stop_sale":
                logger.info("ai_extraction_start", type="stop_sale")
                
                stop_sale = await self.client.extract_stop_sale(
                    subject=subject,
                    body=body,
                    email_date=email_date,
                )
                
                if stop_sale:
                    logger.info(
                        "ai_stop_sale_extracted",
                        hotel=stop_sale.hotel_name,
                        date_from=str(stop_sale.date_from),
                        date_to=str(stop_sale.date_to),
                        confidence=stop_sale.extraction_confidence,
                    )
                else:
                    return AIParseResult(
                        success=False,
                        classification=classification,
                        error="Stop sale extraction failed",
                    )
            
            elif classification.email_type == "reservation":
                logger.info("ai_extraction_start", type="reservation")
                
                reservation = await self.client.extract_reservation(
                    content=f"Subject: {subject}\n\n{body}",
                )
                
                if reservation:
                    logger.info(
                        "ai_reservation_extracted",
                        voucher=reservation.voucher_no,
                        hotel=reservation.hotel_name,
                        confidence=reservation.extraction_confidence,
                    )
                else:
                    return AIParseResult(
                        success=False,
                        classification=classification,
                        error="Reservation extraction failed",
                    )
            
            return AIParseResult(
                success=True,
                classification=classification,
                stop_sale=stop_sale,
                reservation=reservation,
            )
            
        except Exception as e:
            logger.error("ai_parse_error", error=str(e))
            return AIParseResult(
                success=False,
                error=str(e),
            )
    
    async def classify_only(
        self,
        subject: str,
        body: str,
    ) -> EmailClassification | None:
        """
        Only classify email without extraction.
        
        Useful for batch classification or pre-filtering.
        """
        if not self.is_available:
            return None
        
        return await self.client.classify_email(
            subject=subject,
            body=body,
        )
