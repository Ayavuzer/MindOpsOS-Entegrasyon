-- Migration 005: Add tenant_id to existing tables
-- Purpose: Associate existing data with tenants

-- Get default tenant ID
DO $$
DECLARE
    default_tenant_id INTEGER;
BEGIN
    SELECT id INTO default_tenant_id FROM tenants WHERE slug = 'point-holiday';
    
    -- Add tenant_id to emails table
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'emails' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE emails ADD COLUMN tenant_id INTEGER REFERENCES tenants(id);
        UPDATE emails SET tenant_id = default_tenant_id WHERE tenant_id IS NULL;
        ALTER TABLE emails ALTER COLUMN tenant_id SET NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_emails_tenant ON emails(tenant_id);
    END IF;
    
    -- Add tenant_id to reservations table
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'reservations' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE reservations ADD COLUMN tenant_id INTEGER REFERENCES tenants(id);
        UPDATE reservations SET tenant_id = default_tenant_id WHERE tenant_id IS NULL;
        ALTER TABLE reservations ALTER COLUMN tenant_id SET NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_reservations_tenant ON reservations(tenant_id);
    END IF;
    
    -- Add tenant_id to stop_sales table
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'stop_sales' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE stop_sales ADD COLUMN tenant_id INTEGER REFERENCES tenants(id);
        UPDATE stop_sales SET tenant_id = default_tenant_id WHERE tenant_id IS NULL;
        ALTER TABLE stop_sales ALTER COLUMN tenant_id SET NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_stop_sales_tenant ON stop_sales(tenant_id);
    END IF;
    
    -- Add tenant_id to processing_logs table
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'processing_logs' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE processing_logs ADD COLUMN tenant_id INTEGER REFERENCES tenants(id);
        UPDATE processing_logs SET tenant_id = default_tenant_id WHERE tenant_id IS NULL;
        ALTER TABLE processing_logs ALTER COLUMN tenant_id SET NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_processing_logs_tenant ON processing_logs(tenant_id);
    END IF;
    
    RAISE NOTICE 'Tenant ID added to all existing tables with default: %', default_tenant_id;
END $$;

COMMENT ON COLUMN emails.tenant_id IS 'Tenant ownership for data isolation';
COMMENT ON COLUMN reservations.tenant_id IS 'Tenant ownership for data isolation';
COMMENT ON COLUMN stop_sales.tenant_id IS 'Tenant ownership for data isolation';
