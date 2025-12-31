-- E7.S2: AI Metadata Migration
-- Add AI metadata columns to stop_sales table
-- Date: 2025-12-31

-- Add AI metadata columns to stop_sales
ALTER TABLE stop_sales 
    ADD COLUMN IF NOT EXISTS ai_parsed BOOLEAN DEFAULT FALSE;

ALTER TABLE stop_sales 
    ADD COLUMN IF NOT EXISTS ai_confidence DECIMAL(3,2) DEFAULT NULL;

ALTER TABLE stop_sales 
    ADD COLUMN IF NOT EXISTS parse_method VARCHAR(20) DEFAULT 'regex';

-- Update existing records to have default values
UPDATE stop_sales 
SET parse_method = 'regex', ai_parsed = FALSE 
WHERE ai_parsed IS NULL;

-- Create index for filtering by AI parsed status
CREATE INDEX IF NOT EXISTS idx_stop_sales_ai_parsed 
ON stop_sales(ai_parsed);

-- Verify the changes
-- SELECT column_name, data_type, column_default 
-- FROM information_schema.columns 
-- WHERE table_name = 'stop_sales' 
-- AND column_name IN ('ai_parsed', 'ai_confidence', 'parse_method');
