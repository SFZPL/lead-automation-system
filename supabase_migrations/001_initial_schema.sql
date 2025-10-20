-- Supabase Initial Schema for PrezLab Leads Analysis
-- This migration creates tables for caching analyses and managing lead assignments

-- ============================================================================
-- Table: analysis_cache
-- Stores cached analysis results with long-term persistence
-- ============================================================================
CREATE TABLE IF NOT EXISTS analysis_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL,
    analysis_type TEXT NOT NULL CHECK (analysis_type IN ('proposal_followups', 'apollo_followups', 'lost_leads')),
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    results JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_shared BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast lookups by user and analysis type
CREATE INDEX idx_analysis_cache_user_type ON analysis_cache(user_id, analysis_type);
CREATE INDEX idx_analysis_cache_expires ON analysis_cache(expires_at) WHERE expires_at IS NOT NULL;

-- ============================================================================
-- Table: analysis_schedules
-- Track scheduled recurring analyses (weekly, monthly, quarterly)
-- ============================================================================
CREATE TABLE IF NOT EXISTS analysis_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL,
    analysis_type TEXT NOT NULL CHECK (analysis_type IN ('proposal_followups', 'apollo_followups', 'lost_leads')),
    schedule_type TEXT NOT NULL CHECK (schedule_type IN ('weekly', 'monthly', 'quarterly')),
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    next_run_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_run_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for finding schedules that need to run
CREATE INDEX idx_analysis_schedules_next_run ON analysis_schedules(next_run_at) WHERE is_active = true;
CREATE INDEX idx_analysis_schedules_user ON analysis_schedules(user_id);

-- ============================================================================
-- Table: lead_assignments
-- Track forwarded/assigned leads between users
-- ============================================================================
CREATE TABLE IF NOT EXISTS lead_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_cache_id UUID REFERENCES analysis_cache(id) ON DELETE SET NULL,
    conversation_id TEXT NOT NULL,
    external_email TEXT NOT NULL,
    subject TEXT,
    assigned_from_user_id INTEGER NOT NULL,
    assigned_to_user_id INTEGER NOT NULL,
    lead_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'completed', 'rejected')),
    notes TEXT,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for assignment queries
CREATE INDEX idx_lead_assignments_from_user ON lead_assignments(assigned_from_user_id);
CREATE INDEX idx_lead_assignments_to_user ON lead_assignments(assigned_to_user_id);
CREATE INDEX idx_lead_assignments_status ON lead_assignments(status);
CREATE INDEX idx_lead_assignments_conversation ON lead_assignments(conversation_id);

-- ============================================================================
-- Table: user_preferences
-- User-specific settings and preferences
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id INTEGER PRIMARY KEY,
    default_days_back INTEGER DEFAULT 7,
    default_no_response_days INTEGER DEFAULT 3,
    email_notifications BOOLEAN DEFAULT true,
    preferences JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- Row Level Security (RLS) Policies
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE analysis_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE lead_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;

-- Helper function to get current user ID from JWT
CREATE OR REPLACE FUNCTION current_user_id() RETURNS INTEGER AS $$
    SELECT NULLIF(current_setting('request.jwt.claims', true)::json->>'user_id', '')::INTEGER;
$$ LANGUAGE SQL STABLE;

-- ============================================================================
-- RLS Policies: analysis_cache
-- ============================================================================

-- Users can view their own analyses or shared analyses
CREATE POLICY "Users can view own or shared analyses"
    ON analysis_cache FOR SELECT
    USING (user_id = current_user_id() OR is_shared = true);

-- Users can insert their own analyses
CREATE POLICY "Users can insert own analyses"
    ON analysis_cache FOR INSERT
    WITH CHECK (user_id = current_user_id());

-- Users can update their own analyses
CREATE POLICY "Users can update own analyses"
    ON analysis_cache FOR UPDATE
    USING (user_id = current_user_id());

-- Users can delete their own analyses
CREATE POLICY "Users can delete own analyses"
    ON analysis_cache FOR DELETE
    USING (user_id = current_user_id());

-- ============================================================================
-- RLS Policies: analysis_schedules
-- ============================================================================

-- Users can only manage their own schedules
CREATE POLICY "Users manage own schedules"
    ON analysis_schedules FOR ALL
    USING (user_id = current_user_id())
    WITH CHECK (user_id = current_user_id());

-- ============================================================================
-- RLS Policies: lead_assignments
-- ============================================================================

-- Users can view assignments they sent or received
CREATE POLICY "Users view relevant assignments"
    ON lead_assignments FOR SELECT
    USING (
        assigned_from_user_id = current_user_id()
        OR assigned_to_user_id = current_user_id()
    );

-- Users can create assignments from themselves
CREATE POLICY "Users create own assignments"
    ON lead_assignments FOR INSERT
    WITH CHECK (assigned_from_user_id = current_user_id());

-- Users can update assignments they received (status changes)
CREATE POLICY "Recipients update assignment status"
    ON lead_assignments FOR UPDATE
    USING (assigned_to_user_id = current_user_id());

-- Users can delete assignments they created
CREATE POLICY "Senders delete own assignments"
    ON lead_assignments FOR DELETE
    USING (assigned_from_user_id = current_user_id());

-- ============================================================================
-- RLS Policies: user_preferences
-- ============================================================================

-- Users can only manage their own preferences
CREATE POLICY "Users manage own preferences"
    ON user_preferences FOR ALL
    USING (user_id = current_user_id())
    WITH CHECK (user_id = current_user_id());

-- ============================================================================
-- Triggers: Auto-update timestamps
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_analysis_cache_updated_at
    BEFORE UPDATE ON analysis_cache
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_analysis_schedules_updated_at
    BEFORE UPDATE ON analysis_schedules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_lead_assignments_updated_at
    BEFORE UPDATE ON lead_assignments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Trigger: Auto-set completed_at when status changes to completed
-- ============================================================================

CREATE OR REPLACE FUNCTION set_completed_at()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'completed' AND OLD.status != 'completed' THEN
        NEW.completed_at = NOW();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_lead_assignment_completed_at
    BEFORE UPDATE ON lead_assignments
    FOR EACH ROW EXECUTE FUNCTION set_completed_at();

-- ============================================================================
-- Function: Clean up expired cache entries
-- ============================================================================

CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM analysis_cache
    WHERE expires_at IS NOT NULL AND expires_at < NOW();

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- You can schedule this to run periodically using pg_cron or call it from your app
-- SELECT cleanup_expired_cache();
