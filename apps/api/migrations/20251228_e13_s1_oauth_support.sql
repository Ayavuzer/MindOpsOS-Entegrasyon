-- E13-S1: OAuth 2.0 Support Migration
-- Date: 2025-12-28
-- Story: E13-S1 - OAuth Data Model

-- ============================================================================
-- Booking Email OAuth columns
-- ============================================================================
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_oauth_provider VARCHAR(50);
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_oauth_client_id VARCHAR(255);
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_oauth_client_secret_encrypted TEXT;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_oauth_access_token_encrypted TEXT;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_oauth_refresh_token_encrypted TEXT;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_oauth_token_expiry TIMESTAMPTZ;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_oauth_scopes TEXT[];
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_oauth_connected_email VARCHAR(255);

-- ============================================================================
-- Stopsale Email OAuth columns
-- ============================================================================
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_oauth_provider VARCHAR(50);
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_oauth_client_id VARCHAR(255);
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_oauth_client_secret_encrypted TEXT;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_oauth_access_token_encrypted TEXT;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_oauth_refresh_token_encrypted TEXT;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_oauth_token_expiry TIMESTAMPTZ;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_oauth_scopes TEXT[];
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_oauth_connected_email VARCHAR(255);

-- ============================================================================
-- Auth method columns (password, oauth2, app_password)
-- ============================================================================
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_auth_method VARCHAR(20) DEFAULT 'password';
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_auth_method VARCHAR(20) DEFAULT 'password';

-- ============================================================================
-- Health tracking columns
-- ============================================================================
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_email_last_success_at TIMESTAMPTZ;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_email_last_error TEXT;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_email_error_count_24h INTEGER DEFAULT 0;

ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_email_last_success_at TIMESTAMPTZ;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_email_last_error TEXT;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_email_error_count_24h INTEGER DEFAULT 0;

-- ============================================================================
-- Real-time settings (IMAP IDLE)
-- ============================================================================
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_use_idle BOOLEAN DEFAULT TRUE;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_use_idle BOOLEAN DEFAULT TRUE;

-- ============================================================================
-- Indexes
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_tenant_settings_oauth_expiry 
    ON tenant_settings(booking_oauth_token_expiry, stopsale_oauth_token_expiry);

CREATE INDEX IF NOT EXISTS idx_tenant_settings_email_health 
    ON tenant_settings(booking_email_last_success_at, stopsale_email_last_success_at);

-- ============================================================================
-- Rollback (manual, if needed)
-- ============================================================================
-- DROP INDEX IF EXISTS idx_tenant_settings_oauth_expiry;
-- DROP INDEX IF EXISTS idx_tenant_settings_email_health;
-- ALTER TABLE tenant_settings DROP COLUMN IF EXISTS booking_oauth_provider;
-- ... (repeat for all added columns)
