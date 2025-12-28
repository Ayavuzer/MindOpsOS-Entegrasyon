-- Migration 001: Create tenants table
-- Purpose: Multi-tenant support - each agency/operator is a tenant

CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for slug lookup
CREATE INDEX IF NOT EXISTS idx_tenants_slug ON tenants(slug);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert default tenant (for existing data migration)
INSERT INTO tenants (name, slug) 
VALUES ('Point Holiday', 'point-holiday')
ON CONFLICT (slug) DO NOTHING;

COMMENT ON TABLE tenants IS 'Multi-tenant support: Each agency/operator is a tenant';
COMMENT ON COLUMN tenants.slug IS 'URL-safe unique identifier for tenant';
