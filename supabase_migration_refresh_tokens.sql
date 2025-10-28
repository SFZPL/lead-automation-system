-- Migration: Add refresh_tokens table for persistent authentication
-- This table stores long-lived refresh tokens that never expire (unless manually revoked)

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,
    device_info TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on token for fast lookups
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token ON refresh_tokens(token);

-- Create index on user_id for querying user's tokens
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);

-- Create index on is_active for filtering active tokens
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_active ON refresh_tokens(is_active);

-- Add trigger to update last_used_at when token is accessed
CREATE OR REPLACE FUNCTION update_refresh_token_last_used()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_used_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER refresh_token_last_used_trigger
    BEFORE UPDATE ON refresh_tokens
    FOR EACH ROW
    WHEN (OLD.is_active = TRUE AND NEW.is_active = TRUE)
    EXECUTE FUNCTION update_refresh_token_last_used();

COMMENT ON TABLE refresh_tokens IS 'Stores long-lived refresh tokens for persistent authentication across sessions, device restarts, and redeployments';
COMMENT ON COLUMN refresh_tokens.token IS 'Secure random token (64 bytes URL-safe)';
COMMENT ON COLUMN refresh_tokens.is_active IS 'FALSE when token is manually revoked';
COMMENT ON COLUMN refresh_tokens.device_info IS 'Optional device/app info for tracking where token is used';
