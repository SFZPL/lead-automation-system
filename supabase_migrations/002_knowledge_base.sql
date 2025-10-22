-- Supabase Migration: Knowledge Base for AI Context
-- This migration creates a table to store PDF documents that provide context to AI analyses

-- ============================================================================
-- Table: knowledge_base_documents
-- Stores PDF content to be injected into AI prompts
-- ============================================================================
CREATE TABLE IF NOT EXISTS knowledge_base_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    content TEXT NOT NULL,
    description TEXT,
    uploaded_by_user_id INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for active documents lookup
CREATE INDEX idx_knowledge_base_active ON knowledge_base_documents(is_active) WHERE is_active = true;
CREATE INDEX idx_knowledge_base_uploaded_by ON knowledge_base_documents(uploaded_by_user_id);

-- ============================================================================
-- Row Level Security (RLS) Policies
-- ============================================================================

-- Enable RLS
ALTER TABLE knowledge_base_documents ENABLE ROW LEVEL SECURITY;

-- All authenticated users can view active knowledge base documents
CREATE POLICY "All users can view active documents"
    ON knowledge_base_documents FOR SELECT
    USING (is_active = true);

-- Only authenticated users can upload documents
CREATE POLICY "Authenticated users can upload documents"
    ON knowledge_base_documents FOR INSERT
    WITH CHECK (uploaded_by_user_id = current_user_id());

-- Users can update their own uploaded documents
CREATE POLICY "Users can update own documents"
    ON knowledge_base_documents FOR UPDATE
    USING (uploaded_by_user_id = current_user_id());

-- Users can delete their own documents
CREATE POLICY "Users can delete own documents"
    ON knowledge_base_documents FOR DELETE
    USING (uploaded_by_user_id = current_user_id());

-- ============================================================================
-- Trigger: Auto-update timestamps
-- ============================================================================

CREATE TRIGGER update_knowledge_base_documents_updated_at
    BEFORE UPDATE ON knowledge_base_documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
