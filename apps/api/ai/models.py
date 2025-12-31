"""Pydantic models for AI email classification and extraction."""

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


class EmailClassification(BaseModel):
    """Email classification result from AI."""
    
    email_type: Literal["stop_sale", "reservation", "other"] = Field(
        description="Type of email: stop_sale, reservation, or other"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score 0.0-1.0"
    )
    language: str = Field(
        description="ISO 639-1 language code: tr, en, ru, de, uk"
    )
    reasoning: str = Field(
        description="Brief explanation of classification decision"
    )


class StopSaleExtraction(BaseModel):
    """Stop sale data extracted from email by AI."""
    
    hotel_name: str = Field(
        description="Hotel name without suffixes like 'Hotel', 'Resort'"
    )
    date_from: date = Field(
        description="Stop sale period start date"
    )
    date_to: date = Field(
        description="Stop sale period end date"
    )
    room_types: list[str] = Field(
        default_factory=list,
        description="Room type codes (DBL, SGL, TRP). Empty = all rooms"
    )
    board_types: list[str] = Field(
        default_factory=list,
        description="Board type codes (AI, FB, HB). Empty = all boards"
    )
    is_close: bool = Field(
        default=True,
        description="True=stop sale (close), False=open sale (release)"
    )
    reason: Optional[str] = Field(
        default=None,
        description="Reason for stop sale if mentioned"
    )
    extraction_confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score for this extraction"
    )


class Guest(BaseModel):
    """Guest information extracted from reservation."""
    
    title: Literal["Mr", "Mrs", "Ms", "Chd", "Inf"] = Field(
        default="Mr",
        description="Guest title"
    )
    first_name: str = Field(
        description="Guest first name"
    )
    last_name: str = Field(
        description="Guest last name"
    )
    birth_date: Optional[date] = Field(
        default=None,
        description="Birth date if available"
    )
    nationality: Optional[str] = Field(
        default=None,
        description="Nationality code if available"
    )


class ReservationExtraction(BaseModel):
    """Reservation data extracted from email/PDF by AI."""
    
    voucher_no: str = Field(
        description="Voucher or booking reference number"
    )
    hotel_name: str = Field(
        description="Hotel name"
    )
    check_in: date = Field(
        description="Check-in date"
    )
    check_out: date = Field(
        description="Check-out date"
    )
    room_type: str = Field(
        default="DBL",
        description="Room type code: DBL, SGL, TRP, FAM, SUI"
    )
    room_type_name: Optional[str] = Field(
        default=None,
        description="Full room type name"
    )
    board_type: str = Field(
        default="AI",
        description="Board type code: AI, FB, HB, BB, RO"
    )
    adults: int = Field(
        default=2, ge=1,
        description="Number of adults"
    )
    children: int = Field(
        default=0, ge=0,
        description="Number of children"
    )
    guests: list[Guest] = Field(
        default_factory=list,
        description="List of guest information"
    )
    total_price: Optional[Decimal] = Field(
        default=None,
        description="Total price amount"
    )
    currency: str = Field(
        default="EUR",
        description="Currency code: EUR, USD, TRY"
    )
    extraction_confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score for this extraction"
    )
