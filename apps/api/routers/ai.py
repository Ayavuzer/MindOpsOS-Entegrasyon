"""AI endpoints for email classification and extraction."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from src.utils.logger import get_logger
from ai.classifier import EmailClassifier

logger = get_logger(__name__)

router = APIRouter(prefix="/ai", tags=["AI"])


class ClassifyEmailRequest(BaseModel):
    """Request to classify an email."""
    
    subject: str
    body: str


class ClassifyEmailResponse(BaseModel):
    """Response from email classification."""
    
    success: bool
    email_type: str
    confidence: float
    language: str
    reasoning: Optional[str] = None
    used_ai: bool
    fallback_reason: Optional[str] = None


class ExtractStopSaleRequest(BaseModel):
    """Request to extract stop sale data."""
    
    subject: str
    body: str
    email_date: Optional[str] = None


class ExtractStopSaleResponse(BaseModel):
    """Response from stop sale extraction."""
    
    success: bool
    hotel_name: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    room_types: list[str] = []
    is_close: bool = True
    reason: Optional[str] = None
    confidence: float = 0.0
    error: Optional[str] = None


@router.post("/classify", response_model=ClassifyEmailResponse)
async def classify_email(request: ClassifyEmailRequest):
    """
    Classify an email using AI.
    
    Returns the email type (stop_sale, reservation, other),
    confidence score, and detected language.
    """
    try:
        classifier = EmailClassifier()
        
        result = await classifier.classify(
            subject=request.subject,
            body=request.body,
        )
        
        return ClassifyEmailResponse(
            success=result.success,
            email_type=result.email_type,
            confidence=result.confidence,
            language=result.language,
            reasoning=result.classification.reasoning if result.classification else None,
            used_ai=result.used_ai,
            fallback_reason=result.fallback_reason,
        )
        
    except Exception as e:
        logger.error("classify_email_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-stop-sale", response_model=ExtractStopSaleResponse)
async def extract_stop_sale(request: ExtractStopSaleRequest):
    """
    Extract stop sale data from an email.
    
    Uses AI to parse hotel name, dates, room types, etc.
    Falls back to regex-based extraction if AI is unavailable.
    """
    try:
        from ai.extractors import StopSaleExtractor
        
        extractor = StopSaleExtractor()
        
        result = await extractor.extract(
            subject=request.subject,
            body=request.body,
            email_date=request.email_date,
        )
        
        if not result.success:
            return ExtractStopSaleResponse(
                success=False,
                error=result.error or result.fallback_reason,
            )
        
        return ExtractStopSaleResponse(
            success=True,
            hotel_name=result.hotel_name,
            date_from=str(result.date_from) if result.date_from else None,
            date_to=str(result.date_to) if result.date_to else None,
            room_types=result.room_types,
            is_close=result.is_close,
            reason=result.extraction.reason if result.extraction else None,
            confidence=result.confidence,
        )
        
    except Exception as e:
        logger.error("extract_stop_sale_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def ai_status():
    """
    Check AI service availability.
    """
    try:
        from ai.client import GeminiClient
        
        client = GeminiClient()
        
        return {
            "available": client.is_available,
            "model": client.model if client.is_available else None,
        }
        
    except Exception as e:
        return {
            "available": False,
            "error": str(e),
        }
