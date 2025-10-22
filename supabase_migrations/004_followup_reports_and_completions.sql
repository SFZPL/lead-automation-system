-- Migration: Add follow-up reports and completion tracking
-- Version: 004
-- Description: Adds support for saved reports (90-day, monthly, weekly) and follow-up completion tracking

-- Add report metadata columns to analysis_cache
ALTER TABLE analysis_cache
ADD COLUMN IF NOT EXISTS report_type TEXT,
ADD COLUMN IF NOT EXISTS report_period TEXT;

-- Add index for querying reports
CREATE INDEX IF NOT EXISTS idx_analysis_cache_reports
ON analysis_cache(analysis_type, report_type, report_period)
WHERE report_type IS NOT NULL;

-- Create followup_completions table
CREATE TABLE IF NOT EXISTS followup_completions (
    id BIGSERIAL PRIMARY KEY,
    thread_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    completed_by_user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completion_method TEXT NOT NULL CHECK (completion_method IN ('tool_sent', 'manual_marked', 'external_detected')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(thread_id, conversation_id)
);

-- Enable Row Level Security
ALTER TABLE followup_completions ENABLE ROW LEVEL SECURITY;

-- Policy: Users can read all completions (shared state)
CREATE POLICY "Users can read all completions"
    ON followup_completions
    FOR SELECT
    USING (true);

-- Policy: Users can insert their own completions
CREATE POLICY "Users can insert own completions"
    ON followup_completions
    FOR INSERT
    WITH CHECK (completed_by_user_id = (current_setting('app.current_user_id', TRUE))::bigint);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_followup_completions_thread
ON followup_completions(thread_id);

CREATE INDEX IF NOT EXISTS idx_followup_completions_conversation
ON followup_completions(conversation_id);

CREATE INDEX IF NOT EXISTS idx_followup_completions_user
ON followup_completions(completed_by_user_id);

-- Add trigger to update updated_at on analysis_cache
CREATE OR REPLACE FUNCTION update_analysis_cache_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_analysis_cache_updated_at
    BEFORE UPDATE ON analysis_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_analysis_cache_updated_at();

-- Comment the tables
COMMENT ON TABLE followup_completions IS 'Tracks completed follow-up actions across all users';
COMMENT ON COLUMN analysis_cache.report_type IS 'Type of scheduled report: 90day, monthly, weekly';
COMMENT ON COLUMN analysis_cache.report_period IS 'Period identifier: YYYY-MM for monthly, YYYY-Wnn for weekly';
