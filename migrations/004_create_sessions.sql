-- Migration 004: Create sessions table
-- Purpose: JWT session tracking for logout/blacklist

CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_jti VARCHAR(255) UNIQUE NOT NULL,  -- JWT ID (jti claim)
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),  -- IPv6 support
    user_agent TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sessions_jti ON sessions(token_jti);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

-- Auto-cleanup of expired sessions (optional - can be run via cron)
-- DELETE FROM sessions WHERE expires_at < CURRENT_TIMESTAMP;

COMMENT ON TABLE sessions IS 'Active JWT sessions for logout/blacklist';
COMMENT ON COLUMN sessions.token_jti IS 'JWT ID claim for token identification';
