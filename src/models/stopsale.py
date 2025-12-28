"""Pydantic models for stop sale data."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class StopSale(BaseModel):
    """Stop sale information extracted from email."""

    # Hotel
    hotel_name: str
    hotel_code: str | None = None

    # Date range
    date_from: date
    date_to: date

    # Scope
    room_types: list[str] = Field(default_factory=list)  # Empty = all rooms
    board_types: list[str] = Field(default_factory=list)  # Empty = all boards

    # Details
    reason: str | None = None
    is_close: bool = True  # True = stop sale, False = open sale

    # Source
    source_email_id: str | None = None
    source_email_date: date | None = None

    @property
    def days_affected(self) -> int:
        """Calculate number of days affected."""
        return (self.date_to - self.date_from).days + 1


class SednaStopSaleRequest(BaseModel):
    """Request payload for Sedna stop sale API (structure TBD)."""

    HotelId: int
    BeginDate: str  # ISO format
    EndDate: str  # ISO format
    RoomTypeId: int | None = None  # None = all rooms
    BoardId: int | None = None  # None = all boards
    IsClose: bool = True


class StopSaleResult(BaseModel):
    """Result of stop sale processing."""

    success: bool
    hotel_name: str
    date_range: str
    error_message: str | None = None
    processing_time_ms: int = 0
