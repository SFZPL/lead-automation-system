-- Create nda_documents table for storing uploaded NDAs and their analysis
CREATE TABLE IF NOT EXISTS nda_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_content TEXT NOT NULL, -- Base64 encoded or extracted text
    language TEXT, -- 'en' or 'ar'
    uploaded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    analyzed_at TIMESTAMP WITH TIME ZONE,

    -- Analysis results
    risk_category TEXT, -- 'Risky', 'Safe', 'Needs Attention'
    risk_score INTEGER, -- 0-100
    summary TEXT,
    questionable_clauses JSONB, -- Array of {clause, concern, suggestion}
    analysis_details JSONB, -- Full analysis from OpenAI

    -- Metadata
    status TEXT DEFAULT 'pending', -- 'pending', 'analyzing', 'completed', 'failed'
    error_message TEXT
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_nda_documents_user_id ON nda_documents(user_id);
CREATE INDEX IF NOT EXISTS idx_nda_documents_uploaded_at ON nda_documents(uploaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_nda_documents_risk_category ON nda_documents(risk_category);
CREATE INDEX IF NOT EXISTS idx_nda_documents_status ON nda_documents(status);

-- Add comment
COMMENT ON TABLE nda_documents IS 'Stores uploaded NDA documents and their AI-powered risk analysis for both English and Arabic documents';
