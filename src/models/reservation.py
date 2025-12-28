"""Pydantic models for reservation data."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class Guest(BaseModel):
    """Guest information."""

    title: str = ""  # Mr, Mrs, Ms
    first_name: str
    last_name: str
    birth_date: date | None = None
    passport_no: str | None = None
    nationality: str | None = None


class JuniperReservation(BaseModel):
    """Reservation data extracted from Juniper PDF."""

    # Identifiers
    voucher_no: str = Field(..., description="Unique reservation number")
    confirmation_no: str | None = None

    # Hotel information
    hotel_name: str
    hotel_code: str | None = None

    # Dates
    check_in: date
    check_out: date

    # Room & Board
    room_type: str  # DBL, SGL, FAM, etc.
    room_type_name: str | None = None
    board_type: str  # AI, FB, HB, BB, RO
    board_type_name: str | None = None

    # Occupancy
    adults: int = Field(ge=1)
    children: int = Field(ge=0, default=0)
    infants: int = Field(ge=0, default=0)

    # Pricing
    total_price: Decimal | None = None
    currency: str = "EUR"
    
    # Guests
    guests: list[Guest] = []

    # Notes
    special_requests: str | None = None
    agency_notes: str | None = None

    # Source
    source_email_id: str | None = None
    source_email_date: date | None = None

    @property
    def nights(self) -> int:
        """Calculate number of nights."""
        return (self.check_out - self.check_in).days

    @property
    def total_pax(self) -> int:
        """Calculate total passengers."""
        return self.adults + self.children + self.infants


class SednaReservationRequest(BaseModel):
    """Request payload for Sedna InsertReservation API."""

    HotelId: int
    OperatorId: int
    CheckinDate: str  # ISO format
    CheckOutDate: str  # ISO format
    RoomTypeId: int
    BoardId: int
    Adult: int
    Child: int
    Customers: list[dict]
    VoucherNo: str
    NoteToHotel: str = ""
    NoteToAgency: str = ""


class SednaApiResponse(BaseModel):
    """Standard Sedna API response."""

    ErrorType: int  # 0 = Success
    Message: str | None = None
    RecId: int | None = None  # Record ID for successful operations


class ReservationResult(BaseModel):
    """Result of reservation processing."""

    success: bool
    voucher_no: str
    sedna_reservation_id: int | None = None
    error_message: str | None = None
    processing_time_ms: int = 0
