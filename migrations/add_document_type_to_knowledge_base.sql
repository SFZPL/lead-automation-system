-- Add document_type column to knowledge_base_documents table
ALTER TABLE knowledge_base_documents
ADD COLUMN IF NOT EXISTS document_type TEXT DEFAULT 'general';

-- Add comment
COMMENT ON COLUMN knowledge_base_documents.document_type IS 'Type of knowledge base document: general, reference_nda, reference_contract, or pre_discovery_guide';

-- Create index for document type filtering
CREATE INDEX IF NOT EXISTS idx_knowledge_base_documents_document_type ON knowledge_base_documents(document_type);
