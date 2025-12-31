"""Gemini API client wrapper with structured output support."""

import os
from typing import Type, TypeVar

from pydantic import BaseModel

from src.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class GeminiClient:
    """
    Wrapper for Google Gemini API with structured output support.
    
    Uses Pydantic models to enforce response schema.
    """
    
    def __init__(self, api_key: str | None = None):
        """
        Initialize Gemini client.
        
        Args:
            api_key: Gemini API key. Falls back to GEMINI_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        
        if not self.api_key:
            logger.warning("gemini_api_key_not_configured")
            self._client = None
            return
        
        try:
            from google import genai
            from google.genai import types
            
            self._genai = genai
            self._types = types
            self._client = genai.Client(api_key=self.api_key)
            self.model = "gemini-2.0-flash"  # Fast, cheap, good for structured output
            
            logger.info("gemini_client_initialized", model=self.model)
            
        except ImportError:
            logger.error("google_genai_not_installed")
            self._client = None
    
    @property
    def is_available(self) -> bool:
        """Check if Gemini client is available and configured."""
        return self._client is not None
    
    async def extract(
        self,
        prompt: str,
        response_model: Type[T],
        temperature: float = 0.1,
    ) -> T | None:
        """
        Generate structured output using Gemini.
        
        Args:
            prompt: The prompt text
            response_model: Pydantic model class for response schema
            temperature: Creativity level (0.0-1.0, lower = more deterministic)
            
        Returns:
            Validated Pydantic model instance, or None if failed
        """
        if not self.is_available:
            logger.warning("gemini_not_available")
            return None
        
        try:
            logger.debug(
                "gemini_extract_start",
                model=self.model,
                response_model=response_model.__name__,
                temperature=temperature,
            )
            
            response = await self._client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=self._types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_model,
                    temperature=temperature,
                ),
            )
            
            # Parse and validate response
            result = response_model.model_validate_json(response.text)
            
            logger.info(
                "gemini_extract_success",
                response_model=response_model.__name__,
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "gemini_extract_error",
                error=str(e),
                response_model=response_model.__name__,
            )
            return None
    
    async def classify_email(
        self,
        subject: str,
        body: str,
    ):
        """
        Classify an email using AI.
        
        Args:
            subject: Email subject
            body: Email body text
            
        Returns:
            EmailClassification or None
        """
        from .models import EmailClassification
        from .prompts import CLASSIFICATION_PROMPT
        
        prompt = CLASSIFICATION_PROMPT.format(
            subject=subject,
            body=body[:3000],  # Limit body length
        )
        
        return await self.extract(
            prompt=prompt,
            response_model=EmailClassification,
            temperature=0.1,
        )
    
    async def extract_stop_sale(
        self,
        subject: str,
        body: str,
        email_date: str | None = None,
    ):
        """
        Extract stop sale data from email.
        
        Args:
            subject: Email subject
            body: Email body text
            email_date: Email date for context
            
        Returns:
            StopSaleExtraction or None
        """
        from .models import StopSaleExtraction
        from .prompts import STOP_SALE_EXTRACTION_PROMPT
        
        prompt = STOP_SALE_EXTRACTION_PROMPT.format(
            subject=subject,
            body=body,
            email_date=email_date or "unknown",
        )
        
        return await self.extract(
            prompt=prompt,
            response_model=StopSaleExtraction,
            temperature=0.1,
        )
    
    async def extract_reservation(
        self,
        content: str,
    ):
        """
        Extract reservation data from email/PDF content.
        
        Args:
            content: Email body or PDF text content
            
        Returns:
            ReservationExtraction or None
        """
        from .models import ReservationExtraction
        from .prompts import RESERVATION_EXTRACTION_PROMPT
        
        prompt = RESERVATION_EXTRACTION_PROMPT.format(
            content=content,
        )
        
        return await self.extract(
            prompt=prompt,
            response_model=ReservationExtraction,
            temperature=0.1,
        )
