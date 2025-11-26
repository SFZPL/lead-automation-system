import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import toast from 'react-hot-toast';
import {
  DocumentTextIcon,
  TrashIcon,
  CloudArrowUpIcon,
  InformationCircleIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import api from '../utils/api';

interface KnowledgeBaseDocument {
  id: string;
  filename: string;
  file_size: number;
  description?: string;
  document_type?: string;
  uploaded_by_user_id: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

const KnowledgeBasePage: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [description, setDescription] = useState<string>('');
  const [documentType, setDocumentType] = useState<string>('general');
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const queryClient = useQueryClient();

  // Fetch documents
  const { data: documents = [], isLoading, refetch } = useQuery<KnowledgeBaseDocument[]>(
    'knowledge-base-documents',
    async () => {
      const response = await api.get('/knowledge-base/documents');
      return response.data;
    }
  );

  // Upload mutation
  const uploadMutation = useMutation(
    async () => {
      if (!selectedFile) throw new Error('No file selected');

      const formData = new FormData();
      formData.append('file', selectedFile);
      if (description.trim()) {
        formData.append('description', description.trim());
      }
      formData.append('document_type', documentType);

      setIsUploading(true);
      const response = await api.post('/knowledge-base/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return response.data;
    },
    {
      onSuccess: () => {
        toast.success('Document uploaded successfully');
        setSelectedFile(null);
        setDescription('');
        setDocumentType('general');
        setIsUploading(false);
        queryClient.invalidateQueries('knowledge-base-documents');
      },
      onError: (error: any) => {
        setIsUploading(false);
        toast.error(error?.response?.data?.detail || 'Failed to upload document');
      },
    }
  );

  // Delete mutation
  const deleteMutation = useMutation(
    async (documentId: string) => {
      await api.delete(`/knowledge-base/documents/${documentId}`);
    },
    {
      onSuccess: () => {
        toast.success('Document deleted successfully');
        queryClient.invalidateQueries('knowledge-base-documents');
      },
      onError: (error: any) => {
        toast.error(error?.response?.data?.detail || 'Failed to delete document');
      },
    }
  );

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        toast.error('Only PDF files are supported');
        return;
      }
      setSelectedFile(file);
    }
  };

  const handleUpload = () => {
    if (!selectedFile) {
      toast.error('Please select a PDF file first');
      return;
    }
    uploadMutation.mutate();
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateString: string): string => {
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return dateString;
    }
  };

  return (
    <div className="space-y-6 px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <header>
        <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.2em] text-primary-600">
          <DocumentTextIcon className="h-4 w-4" />
          Knowledge Base
        </div>
        <h1 className="mt-2 text-2xl font-semibold text-gray-900">AI Knowledge Base</h1>
        <p className="mt-2 max-w-3xl text-sm text-gray-600">
          Upload PDF documents containing information about your company, services, and processes. This content
          will be automatically included as context when the AI generates analyses for lost leads and other features.
        </p>
      </header>

      {/* Info Banner */}
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
        <div className="flex gap-3">
          <InformationCircleIcon className="h-5 w-5 flex-shrink-0 text-blue-600" />
          <div className="text-sm text-blue-800">
            <p className="font-medium">How it works:</p>
            <ul className="mt-1 list-disc space-y-1 pl-5">
              <li>Upload PDFs containing company info, service descriptions, case studies, etc.</li>
              <li>Text is automatically extracted and stored</li>
              <li>AI uses this context when analyzing lost leads to make more informed recommendations</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Upload Section */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900">Upload Document</h2>
        <p className="mt-1 text-sm text-gray-600">Add a new PDF to the knowledge base</p>

        <div className="mt-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">PDF File</label>
            <div className="mt-1">
              <input
                type="file"
                accept=".pdf"
                onChange={handleFileChange}
                className="block w-full text-sm text-gray-500 file:mr-4 file:rounded-md file:border-0 file:bg-primary-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-primary-700"
              />
            </div>
            {selectedFile && (
              <p className="mt-1 text-sm text-gray-500">
                Selected: {selectedFile.name} ({formatFileSize(selectedFile.size)})
              </p>
            )}
          </div>

          <div>
            <label htmlFor="description" className="block text-sm font-medium text-gray-700">
              Description (Optional)
            </label>
            <input
              id="description"
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of this document..."
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </div>

          <div>
            <label htmlFor="document_type" className="block text-sm font-medium text-gray-700">
              Document Type
            </label>
            <select
              id="document_type"
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value)}
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            >
              <option value="general">General Knowledge</option>
              <option value="reference_nda">Reference NDA Template</option>
              <option value="reference_contract">Reference Contract Template</option>
              <option value="pre_discovery_guide">Pre-Discovery Call Guide</option>
            </select>
            <p className="mt-1 text-xs text-gray-500">
              {documentType === 'reference_nda' && 'Used as a comparison template when analyzing uploaded NDAs'}
              {documentType === 'reference_contract' && 'Used as a comparison template when analyzing uploaded contracts'}
              {documentType === 'pre_discovery_guide' && 'Used when generating pre-discovery call documents'}
              {documentType === 'general' && 'General knowledge base content for AI context'}
            </p>
          </div>

          <button
            onClick={handleUpload}
            disabled={!selectedFile || isUploading}
            className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50"
          >
            {isUploading ? (
              <>
                <ArrowPathIcon className="h-5 w-5 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <CloudArrowUpIcon className="h-5 w-5" />
                Upload Document
              </>
            )}
          </button>
        </div>
      </div>

      {/* Documents List */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Uploaded Documents</h2>
            <p className="mt-1 text-sm text-gray-600">
              {documents.length} {documents.length === 1 ? 'document' : 'documents'} in knowledge base
            </p>
          </div>
          <button
            onClick={() => refetch()}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <ArrowPathIcon className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        <div className="mt-4 space-y-3">
          {isLoading && (
            <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-6 text-center text-sm text-gray-500">
              Loading documents...
            </div>
          )}

          {!isLoading && documents.length === 0 && (
            <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-6 text-center text-sm text-gray-500">
              No documents uploaded yet. Upload your first PDF above to get started.
            </div>
          )}

          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-start justify-between rounded-lg border border-gray-200 bg-gray-50 p-4"
            >
              <div className="flex gap-3">
                <DocumentTextIcon className="h-6 w-6 flex-shrink-0 text-gray-400" />
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-medium text-gray-900">{doc.filename}</h3>
                    {doc.document_type && doc.document_type !== 'general' && (
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        doc.document_type === 'reference_nda' ? 'bg-blue-100 text-blue-800' :
                        doc.document_type === 'reference_contract' ? 'bg-green-100 text-green-800' :
                        doc.document_type === 'pre_discovery_guide' ? 'bg-purple-100 text-purple-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {doc.document_type === 'reference_nda' ? 'NDA Template' :
                         doc.document_type === 'reference_contract' ? 'Contract Template' :
                         doc.document_type === 'pre_discovery_guide' ? 'Pre-Discovery Guide' :
                         doc.document_type}
                      </span>
                    )}
                  </div>
                  {doc.description && (
                    <p className="mt-1 text-sm text-gray-600">{doc.description}</p>
                  )}
                  <div className="mt-1 flex gap-4 text-xs text-gray-500">
                    <span>{formatFileSize(doc.file_size)}</span>
                    <span>Uploaded {formatDate(doc.created_at)}</span>
                  </div>
                </div>
              </div>

              <button
                onClick={() => {
                  if (window.confirm(`Are you sure you want to delete "${doc.filename}"?`)) {
                    deleteMutation.mutate(doc.id);
                  }
                }}
                disabled={deleteMutation.isLoading}
                className="inline-flex items-center gap-1 rounded-md border border-red-300 bg-white px-3 py-1 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
              >
                <TrashIcon className="h-4 w-4" />
                Delete
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBasePage;
