-- Migration 003: Create tenant_settings table
-- Purpose: Store tenant-specific integration credentials (encrypted)

CREATE TABLE IF NOT EXISTS tenant_settings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER UNIQUE NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Booking Email Configuration (POP3/IMAP)
    booking_email_host VARCHAR(255),
    booking_email_port INTEGER DEFAULT 995,
    booking_email_address VARCHAR(255),
    booking_email_password_encrypted BYTEA,  -- Fernet encrypted
    booking_email_protocol VARCHAR(10) DEFAULT 'pop3',  -- 'pop3' or 'imap'
    booking_email_use_ssl BOOLEAN DEFAULT TRUE,
    
    -- Stop Sale Email Configuration
    stopsale_email_host VARCHAR(255),
    stopsale_email_port INTEGER DEFAULT 995,
    stopsale_email_address VARCHAR(255),
    stopsale_email_password_encrypted BYTEA,
    stopsale_email_protocol VARCHAR(10) DEFAULT 'pop3',
    stopsale_email_use_ssl BOOLEAN DEFAULT TRUE,
    
    -- Sedna API Configuration
    sedna_api_url VARCHAR(500),
    sedna_username VARCHAR(255),
    sedna_password_encrypted BYTEA,
    sedna_operator_id INTEGER,
    
    -- Processing Settings
    email_check_interval_seconds INTEGER DEFAULT 60,
    auto_process_enabled BOOLEAN DEFAULT TRUE,
    delete_after_fetch BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trigger for updated_at
CREATE TRIGGER update_tenant_settings_updated_at
    BEFORE UPDATE ON tenant_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add constraint for valid protocols
ALTER TABLE tenant_settings 
ADD CONSTRAINT check_booking_protocol 
CHECK (booking_email_protocol IN ('pop3', 'imap'));

ALTER TABLE tenant_settings 
ADD CONSTRAINT check_stopsale_protocol 
CHECK (stopsale_email_protocol IN ('pop3', 'imap'));

COMMENT ON TABLE tenant_settings IS 'Tenant-specific integration credentials';
COMMENT ON COLUMN tenant_settings.booking_email_password_encrypted IS 'Fernet encrypted password';
COMMENT ON COLUMN tenant_settings.sedna_password_encrypted IS 'Fernet encrypted password';
