-- Create followup_favorites table for tracking favorited follow-up threads
CREATE TABLE IF NOT EXISTS followup_favorites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    favorited_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(thread_id)
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_followup_favorites_thread_id ON followup_favorites(thread_id);
CREATE INDEX IF NOT EXISTS idx_followup_favorites_conversation_id ON followup_favorites(conversation_id);

-- Add comment
COMMENT ON TABLE followup_favorites IS 'Stores favorited follow-up threads that appear at the top of the list for all users';
