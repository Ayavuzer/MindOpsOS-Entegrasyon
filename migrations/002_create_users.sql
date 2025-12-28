-- Migration 002: Create users table
-- Purpose: User accounts with tenant membership

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user',  -- 'user', 'admin', 'superadmin'
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Trigger for updated_at
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add constraint for valid roles
ALTER TABLE users 
ADD CONSTRAINT check_user_role 
CHECK (role IN ('user', 'admin', 'superadmin'));

COMMENT ON TABLE users IS 'User accounts with tenant membership';
COMMENT ON COLUMN users.role IS 'user: regular, admin: tenant admin, superadmin: platform admin';
COMMENT ON COLUMN users.password_hash IS 'bcrypt hashed password';
