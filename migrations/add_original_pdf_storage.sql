-- Add column to store original PDF file bytes (as base64)
ALTER TABLE nda_documents
ADD COLUMN IF NOT EXISTS original_pdf_base64 TEXT DEFAULT NULL;

-- Add comment
COMMENT ON COLUMN nda_documents.original_pdf_base64 IS 'Original uploaded PDF file stored as base64 for AI-powered filling';
