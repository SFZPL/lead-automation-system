-- Add entity selection field to nda_documents table
ALTER TABLE nda_documents
ADD COLUMN IF NOT EXISTS selected_entity TEXT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS counterparty_name TEXT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS filled_pdf_url TEXT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS filled_pdf_generated_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;

-- Add comment
COMMENT ON COLUMN nda_documents.selected_entity IS 'Selected Prezlab entity: dubai, abu_dhabi, or riyadh';
COMMENT ON COLUMN nda_documents.counterparty_name IS 'Name of the counterparty/client for the contract';
COMMENT ON COLUMN nda_documents.filled_pdf_url IS 'URL to the auto-filled PDF after approval';
COMMENT ON COLUMN nda_documents.filled_pdf_generated_at IS 'Timestamp when the filled PDF was generated';
