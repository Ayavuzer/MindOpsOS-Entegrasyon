"""AI module for email classification and extraction using Gemini."""

from .models import (
    EmailClassification,
    StopSaleExtraction,
    ReservationExtraction,
    Guest,
)
from .client import GeminiClient
from .parser import AIEmailParser
from .classifier import EmailClassifier, ClassificationResult
from .extractors import StopSaleExtractor, StopSaleExtractionResult

__all__ = [
    "EmailClassification",
    "StopSaleExtraction",
    "ReservationExtraction",
    "Guest",
    "GeminiClient",
    "AIEmailParser",
    "EmailClassifier",
    "ClassificationResult",
    "StopSaleExtractor",
    "StopSaleExtractionResult",
]
