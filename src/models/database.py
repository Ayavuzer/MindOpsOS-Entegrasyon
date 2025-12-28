"""Database models for email storage using PostgreSQL."""

from datetime import datetime
from enum import Enum
from typing import Optional
import json

from pydantic import BaseModel


# =============================================================================
# Enums
# =============================================================================


class EmailStatus(str, Enum):
    """Email processing status."""
    
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EmailType(str, Enum):
    """Email type classification."""
    
    RESERVATION = "reservation"
    STOPSALE = "stopsale"
    UNKNOWN = "unknown"


# =============================================================================
# Database Models
# =============================================================================


class EmailRecord(BaseModel):
    """Email record stored in database."""
    
    id: int | None = None
    message_id: str
    uid: str | None = None
    subject: str
    sender: str
    recipients: list[str]
    received_at: datetime
    body_text: str
    body_html: str | None = None
    email_type: EmailType = EmailType.UNKNOWN
    status: EmailStatus = EmailStatus.PENDING
    
    # Processing info
    processed_at: datetime | None = None
    error_message: str | None = None
    retry_count: int = 0
    
    # Attachment info
    has_pdf: bool = False
    pdf_filename: str | None = None
    pdf_content: bytes | None = None  # Store PDF binary
    
    # Result tracking
    sedna_rec_id: int | None = None
    voucher_no: str | None = None
    
    # Metadata
    created_at: datetime | None = None
    updated_at: datetime | None = None
    raw_headers: dict | None = None
    
    class Config:
        arbitrary_types_allowed = True


class ProcessingLog(BaseModel):
    """Log entry for processing attempts."""
    
    id: int | None = None
    email_id: int
    action: str  # "fetch", "parse", "send_to_sedna", etc.
    status: str  # "success", "error"
    message: str | None = None
    details: dict | None = None
    created_at: datetime | None = None


# =============================================================================
# SQL Schema
# =============================================================================

CREATE_TABLES_SQL = """
-- Email records table
CREATE TABLE IF NOT EXISTS emails (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(255) UNIQUE NOT NULL,
    uid VARCHAR(100),
    subject TEXT,
    sender VARCHAR(255),
    recipients TEXT[], -- PostgreSQL array
    received_at TIMESTAMP,
    body_text TEXT,
    body_html TEXT,
    email_type VARCHAR(50) DEFAULT 'unknown',
    status VARCHAR(50) DEFAULT 'pending',
    
    -- Processing info
    processed_at TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    
    -- Attachment info
    has_pdf BOOLEAN DEFAULT FALSE,
    pdf_filename VARCHAR(255),
    pdf_content BYTEA, -- Binary data
    
    -- Result tracking
    sedna_rec_id INTEGER,
    voucher_no VARCHAR(100),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_headers JSONB,
    
    -- Indexes for common queries
    CONSTRAINT emails_message_id_key UNIQUE (message_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status);
CREATE INDEX IF NOT EXISTS idx_emails_email_type ON emails(email_type);
CREATE INDEX IF NOT EXISTS idx_emails_received_at ON emails(received_at);
CREATE INDEX IF NOT EXISTS idx_emails_voucher_no ON emails(voucher_no);

-- Processing logs table
CREATE TABLE IF NOT EXISTS processing_logs (
    id SERIAL PRIMARY KEY,
    email_id INTEGER REFERENCES emails(id) ON DELETE CASCADE,
    action VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    message TEXT,
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_processing_logs_email_id ON processing_logs(email_id);

-- Stop sales table for local tracking
CREATE TABLE IF NOT EXISTS stop_sales (
    id SERIAL PRIMARY KEY,
    hotel_name VARCHAR(255) NOT NULL,
    hotel_id INTEGER, -- Sedna hotel ID if mapped
    date_from DATE NOT NULL,
    date_to DATE NOT NULL,
    room_types TEXT[], -- Array of room type codes
    board_types TEXT[], -- Array of board codes
    is_close BOOLEAN DEFAULT TRUE, -- true = stop, false = open
    reason TEXT,
    
    -- Source tracking
    source_email_id INTEGER REFERENCES emails(id),
    
    -- Sedna sync
    sedna_synced BOOLEAN DEFAULT FALSE,
    sedna_synced_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stop_sales_hotel_name ON stop_sales(hotel_name);
CREATE INDEX IF NOT EXISTS idx_stop_sales_dates ON stop_sales(date_from, date_to);

-- Reservations table for local tracking
CREATE TABLE IF NOT EXISTS reservations (
    id SERIAL PRIMARY KEY,
    voucher_no VARCHAR(100) UNIQUE NOT NULL,
    hotel_name VARCHAR(255),
    hotel_id INTEGER, -- Sedna hotel ID
    
    check_in DATE,
    check_out DATE,
    room_type VARCHAR(50),
    room_type_id INTEGER,
    board_type VARCHAR(10),
    board_id INTEGER,
    
    adults INTEGER DEFAULT 2,
    children INTEGER DEFAULT 0,
    
    guests JSONB, -- Array of guest objects
    
    total_price DECIMAL(10, 2),
    currency VARCHAR(10),
    
    -- Source tracking
    source_email_id INTEGER REFERENCES emails(id),
    
    -- Sedna sync
    sedna_rec_id INTEGER,
    sedna_synced BOOLEAN DEFAULT FALSE,
    sedna_synced_at TIMESTAMP,
    
    status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reservations_voucher ON reservations(voucher_no);
CREATE INDEX IF NOT EXISTS idx_reservations_hotel ON reservations(hotel_name);
CREATE INDEX IF NOT EXISTS idx_reservations_status ON reservations(status);

-- Function to update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
DROP TRIGGER IF EXISTS update_emails_updated_at ON emails;
CREATE TRIGGER update_emails_updated_at
    BEFORE UPDATE ON emails
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_stop_sales_updated_at ON stop_sales;
CREATE TRIGGER update_stop_sales_updated_at
    BEFORE UPDATE ON stop_sales
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_reservations_updated_at ON reservations;
CREATE TRIGGER update_reservations_updated_at
    BEFORE UPDATE ON reservations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
"""
