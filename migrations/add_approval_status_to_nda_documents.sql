-- Add approval workflow fields to nda_documents table
ALTER TABLE nda_documents
ADD COLUMN IF NOT EXISTS approval_status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
ADD COLUMN IF NOT EXISTS approved_by TEXT, -- Email of person who approved
ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS teams_message_id TEXT; -- ID of the Teams message for tracking approval responses

-- Create index for faster lookups by approval status
CREATE INDEX IF NOT EXISTS idx_nda_documents_approval_status ON nda_documents(approval_status);

-- Add comment
COMMENT ON COLUMN nda_documents.approval_status IS 'Approval status: pending, approved, or rejected';
COMMENT ON COLUMN nda_documents.approved_by IS 'Email of the person who approved/rejected the document';
COMMENT ON COLUMN nda_documents.approved_at IS 'Timestamp when the document was approved/rejected';
COMMENT ON COLUMN nda_documents.teams_message_id IS 'Teams message ID for tracking approval responses';
