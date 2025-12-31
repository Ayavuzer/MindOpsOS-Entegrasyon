"""Email classification service using Gemini AI."""

from dataclasses import dataclass
from typing import Optional

from src.utils.logger import get_logger

from .client import GeminiClient
from .models import EmailClassification

logger = get_logger(__name__)


@dataclass
class ClassificationResult:
    """Result of email classification."""
    
    success: bool
    classification: Optional[EmailClassification] = None
    used_ai: bool = False
    fallback_reason: Optional[str] = None
    
    @property
    def email_type(self) -> str:
        """Get email type, defaulting to 'other'."""
        if self.classification:
            return self.classification.email_type
        return "other"
    
    @property
    def confidence(self) -> float:
        """Get confidence score."""
        if self.classification:
            return self.classification.confidence
        return 0.0
    
    @property
    def language(self) -> str:
        """Get detected language."""
        if self.classification:
            return self.classification.language
        return "en"
    
    @property
    def is_stop_sale(self) -> bool:
        """Check if classified as stop sale."""
        return self.email_type == "stop_sale"
    
    @property
    def is_reservation(self) -> bool:
        """Check if classified as reservation."""
        return self.email_type == "reservation"


class EmailClassifier:
    """
    Email classification service using Gemini AI.
    
    Classifies emails into categories:
    - stop_sale: Hotel stop sale notifications
    - reservation: Booking confirmations/vouchers
    - other: Everything else
    
    Falls back to keyword-based classification when AI is unavailable
    or confidence is below threshold.
    """
    
    # Keywords for fallback classification (Turkish + English + Russian + German)
    STOP_SALE_KEYWORDS = [
        # English
        "stop sale", "stop-sale", "stopsale", "closed for sale",
        "not available", "rooms closed", "no availability",
        # Turkish
        "satış kapatma", "satış durdurma", "kapalı", "müsait değil",
        "oda kapalı", "satışa kapalı",
        # Russian
        "стоп-продажа", "стоп продажа", "закрыто для продаж",
        # German
        "verkaufsstopp", "nicht verfügbar", "geschlossen",
    ]
    
    RESERVATION_KEYWORDS = [
        # English
        "voucher", "booking", "reservation", "confirmation",
        "booking confirmed", "your reservation", "check-in",
        # Turkish
        "rezervasyon", "onay", "voucher", "giriş tarihi",
        # Russian
        "бронирование", "подтверждение", "ваучер",
        # German
        "buchung", "bestätigung", "reservierung",
    ]
    
    def __init__(
        self,
        api_key: str | None = None,
        confidence_threshold: float = 0.85,
    ):
        """
        Initialize classifier.
        
        Args:
            api_key: Gemini API key
            confidence_threshold: Minimum confidence to accept AI result
        """
        self.client = GeminiClient(api_key=api_key)
        self.confidence_threshold = confidence_threshold
    
    @property
    def ai_available(self) -> bool:
        """Check if AI classification is available."""
        return self.client.is_available
    
    async def classify(
        self,
        subject: str,
        body: str,
        use_fallback: bool = True,
    ) -> ClassificationResult:
        """
        Classify an email.
        
        Args:
            subject: Email subject
            body: Email body text
            use_fallback: Whether to use keyword fallback when AI fails
            
        Returns:
            ClassificationResult with classification details
        """
        logger.info(
            "classification_start",
            subject=subject[:50] if subject else "",
            body_length=len(body) if body else 0,
            ai_available=self.ai_available,
        )
        
        # Try AI classification first
        if self.ai_available:
            result = await self._classify_with_ai(subject, body)
            
            # Check if result is usable
            if result.success and result.confidence >= self.confidence_threshold:
                logger.info(
                    "classification_ai_success",
                    email_type=result.email_type,
                    confidence=result.confidence,
                    language=result.language,
                )
                return result
            
            # AI result below threshold
            if result.classification:
                logger.warning(
                    "classification_ai_low_confidence",
                    confidence=result.confidence,
                    threshold=self.confidence_threshold,
                )
        
        # Fallback to keyword-based classification
        if use_fallback:
            fallback_result = self._classify_with_keywords(subject, body)
            logger.info(
                "classification_fallback_used",
                email_type=fallback_result.email_type,
                reason=fallback_result.fallback_reason,
            )
            return fallback_result
        
        # No classification available
        return ClassificationResult(
            success=False,
            fallback_reason="AI unavailable and fallback disabled",
        )
    
    async def _classify_with_ai(
        self,
        subject: str,
        body: str,
    ) -> ClassificationResult:
        """Classify using Gemini AI."""
        try:
            classification = await self.client.classify_email(
                subject=subject,
                body=body,
            )
            
            if classification:
                return ClassificationResult(
                    success=True,
                    classification=classification,
                    used_ai=True,
                )
            
            return ClassificationResult(
                success=False,
                fallback_reason="AI returned no result",
            )
            
        except Exception as e:
            logger.error("classification_ai_error", error=str(e))
            return ClassificationResult(
                success=False,
                fallback_reason=f"AI error: {str(e)}",
            )
    
    def _classify_with_keywords(
        self,
        subject: str,
        body: str,
    ) -> ClassificationResult:
        """Fallback classification using keywords."""
        combined_text = f"{subject} {body}".lower()
        
        # Check for stop sale keywords
        stop_sale_score = sum(
            1 for kw in self.STOP_SALE_KEYWORDS
            if kw.lower() in combined_text
        )
        
        # Check for reservation keywords
        reservation_score = sum(
            1 for kw in self.RESERVATION_KEYWORDS
            if kw.lower() in combined_text
        )
        
        # Determine classification
        if stop_sale_score > reservation_score and stop_sale_score > 0:
            email_type = "stop_sale"
            confidence = min(0.7, 0.4 + (stop_sale_score * 0.1))
        elif reservation_score > stop_sale_score and reservation_score > 0:
            email_type = "reservation"
            confidence = min(0.7, 0.4 + (reservation_score * 0.1))
        else:
            email_type = "other"
            confidence = 0.5
        
        # Detect language
        language = self._detect_language(combined_text)
        
        classification = EmailClassification(
            email_type=email_type,
            confidence=confidence,
            language=language,
            reasoning=f"Keyword match: stop_sale={stop_sale_score}, reservation={reservation_score}",
        )
        
        return ClassificationResult(
            success=True,
            classification=classification,
            used_ai=False,
            fallback_reason="Keyword-based classification",
        )
    
    def _detect_language(self, text: str) -> str:
        """Simple language detection based on character patterns."""
        text_lower = text.lower()
        
        # Russian (Cyrillic)
        if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in text):
            return "ru"
        
        # Turkish specific characters
        turkish_chars = set("şğüöçıİ")
        if any(c in text for c in turkish_chars):
            return "tr"
        
        # German specific characters
        german_chars = set("äöüß")
        if any(c in text for c in german_chars):
            return "de"
        
        # Ukrainian
        if any(c in text for c in "іїєґ"):
            return "uk"
        
        # Default to English
        return "en"
    
    async def classify_batch(
        self,
        emails: list[tuple[str, str]],
    ) -> list[ClassificationResult]:
        """
        Classify multiple emails.
        
        Args:
            emails: List of (subject, body) tuples
            
        Returns:
            List of ClassificationResult
        """
        results = []
        for subject, body in emails:
            result = await self.classify(subject, body)
            results.append(result)
        return results
