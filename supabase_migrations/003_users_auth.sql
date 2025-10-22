-- Migration 003: User Authentication and Settings
-- This migration creates tables for user authentication and per-user Odoo credentials

-- Users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- User settings table for Odoo credentials and other settings
CREATE TABLE IF NOT EXISTS user_settings (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    odoo_url TEXT,
    odoo_db TEXT,
    odoo_username TEXT,
    odoo_encrypted_password TEXT, -- Encrypted password for security
    outlook_tokens JSONB, -- OAuth tokens for email
    user_identifier TEXT, -- Email token identifier
    settings_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON user_settings(user_id);

-- Enable Row Level Security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

-- Policies: Users can only read their own data
CREATE POLICY "Users can read own data"
    ON users
    FOR SELECT
    USING (true); -- Allow reading all users for now (can be restricted later)

CREATE POLICY "Users can update own data"
    ON users
    FOR UPDATE
    USING (id = (current_setting('app.current_user_id', TRUE))::bigint);

CREATE POLICY "Users can read own settings"
    ON user_settings
    FOR SELECT
    USING (user_id = (current_setting('app.current_user_id', TRUE))::bigint);

CREATE POLICY "Users can update own settings"
    ON user_settings
    FOR UPDATE
    USING (user_id = (current_setting('app.current_user_id', TRUE))::bigint);

CREATE POLICY "System can insert users"
    ON users
    FOR INSERT
    WITH CHECK (true); -- Backend handles user creation

CREATE POLICY "System can insert settings"
    ON user_settings
    FOR INSERT
    WITH CHECK (true); -- Backend handles settings creation

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers to auto-update updated_at
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_settings_updated_at
    BEFORE UPDATE ON user_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE users IS 'User accounts for authentication';
COMMENT ON TABLE user_settings IS 'Per-user settings including Odoo credentials';
COMMENT ON COLUMN user_settings.odoo_encrypted_password IS 'Encrypted Odoo password using Fernet encryption';
