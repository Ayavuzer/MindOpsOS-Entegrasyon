-- ============================================================================
-- Migration: 20251228_001_processing_logs
-- Description: Create processing_logs table for pipeline run history
-- Author: Antigravity Agent
-- Date: 2025-12-28
-- ============================================================================

-- Processing Logs Table
-- Stores history of all pipeline runs per tenant
CREATE TABLE IF NOT EXISTS processing_logs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Timing
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL,
    
    -- Fetch Stats
    booking_emails_fetched INTEGER DEFAULT 0,
    stopsale_emails_fetched INTEGER DEFAULT 0,
    
    -- Parse Stats (optional, for future)
    reservations_parsed INTEGER DEFAULT 0,
    stop_sales_parsed INTEGER DEFAULT 0,
    
    -- Sync Stats
    reservations_synced INTEGER DEFAULT 0,
    stop_sales_synced INTEGER DEFAULT 0,
    
    -- Result
    success BOOLEAN DEFAULT true,
    message TEXT,
    errors TEXT[] DEFAULT '{}',
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for tenant-based queries
CREATE INDEX IF NOT EXISTS idx_processing_logs_tenant_id 
ON processing_logs(tenant_id);

-- Index for time-based queries (recent runs)
CREATE INDEX IF NOT EXISTS idx_processing_logs_started_at 
ON processing_logs(started_at DESC);

-- Composite index for tenant + time (most common query)
CREATE INDEX IF NOT EXISTS idx_processing_logs_tenant_time 
ON processing_logs(tenant_id, started_at DESC);

-- ============================================================================
-- Rollback (run manually if needed)
-- ============================================================================
-- DROP TABLE IF EXISTS processing_logs;
