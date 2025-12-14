-- Create table for storing tool impact reports
CREATE TABLE IF NOT EXISTS tool_impact_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    before_days INTEGER NOT NULL DEFAULT 90,
    source_filter VARCHAR(255),
    report JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Index for faster user lookups
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create index for user_id lookups
CREATE INDEX IF NOT EXISTS idx_tool_impact_reports_user_id ON tool_impact_reports(user_id);

-- Create index for sorting by created_at
CREATE INDEX IF NOT EXISTS idx_tool_impact_reports_created_at ON tool_impact_reports(created_at DESC);

-- Add RLS policies
ALTER TABLE tool_impact_reports ENABLE ROW LEVEL SECURITY;

-- Users can only see their own reports
CREATE POLICY "Users can view own reports" ON tool_impact_reports
    FOR SELECT USING (user_id = current_setting('app.current_user_id')::INTEGER);

-- Users can only insert their own reports
CREATE POLICY "Users can insert own reports" ON tool_impact_reports
    FOR INSERT WITH CHECK (user_id = current_setting('app.current_user_id')::INTEGER);

-- Users can only delete their own reports
CREATE POLICY "Users can delete own reports" ON tool_impact_reports
    FOR DELETE USING (user_id = current_setting('app.current_user_id')::INTEGER);
