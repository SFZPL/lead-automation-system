import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import toast from 'react-hot-toast';
import {
  DocumentTextIcon,
  ArrowUpTrayIcon,
  TrashIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  ShieldCheckIcon,
  ShieldExclamationIcon,
} from '@heroicons/react/24/outline';
import api from '../utils/api';

interface QuestionableClause {
  clause: string;
  concern: string;
  suggestion: string;
  severity: 'low' | 'medium' | 'high';
}

interface NDADocument {
  id: string;
  user_id: string;
  file_name: string;
  file_size: number;
  language: string;
  uploaded_at: string;
  analyzed_at?: string;
  risk_category?: string;
  risk_score?: number;
  summary?: string;
  questionable_clauses?: QuestionableClause[];
  status: 'pending' | 'analyzing' | 'completed' | 'failed';
  error_message?: string;
}

const NDAAnalysisPage: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [saveToDatabase, setSaveToDatabase] = useState(true);
  const [documentType, setDocumentType] = useState<'nda' | 'contract'>('nda');
  const [selectedDocument, setSelectedDocument] = useState<NDADocument | null>(null);
  const queryClient = useQueryClient();

  // Fetch NDA documents
  const { data: documentsData, isLoading: isLoadingDocuments } = useQuery(
    'nda-documents',
    () => api.getNDADocuments(),
    {
      refetchInterval: 5000, // Refetch every 5 seconds to check for analysis updates
    }
  );

  const documents: NDADocument[] = documentsData?.data?.documents || [];

  // Delete mutation
  const deleteMutation = useMutation(
    (ndaId: string) => api.deleteNDADocument(ndaId),
    {
      onSuccess: () => {
        toast.success('NDA document deleted');
        queryClient.invalidateQueries('nda-documents');
        if (selectedDocument) {
          setSelectedDocument(null);
        }
      },
      onError: () => {
        toast.error('Failed to delete document');
      },
    }
  );

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      toast.error('Please select a file');
      return;
    }

    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('save_to_database', saveToDatabase.toString());
      formData.append('document_type', documentType);

      const response = await api.uploadNDA(formData);

      if (saveToDatabase) {
        toast.success('NDA analyzed and saved successfully!');
        queryClient.invalidateQueries('nda-documents');
      } else {
        toast.success('NDA analyzed successfully (not saved)');
      }

      setSelectedFile(null);

      // Automatically select the newly analyzed document
      if (response.data?.nda) {
        setSelectedDocument(response.data.nda);
      }
    } catch (error: any) {
      console.error('Upload error:', error);
      toast.error(error.response?.data?.detail || 'Failed to upload NDA');
    } finally {
      setIsUploading(false);
    }
  };

  const getRiskBadge = (category?: string) => {
    switch (category) {
      case 'Safe':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'Needs Attention':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'Risky':
        return 'bg-red-100 text-red-800 border-red-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getRiskIcon = (category?: string) => {
    switch (category) {
      case 'Safe':
        return <ShieldCheckIcon className="w-6 h-6 text-green-600" />;
      case 'Needs Attention':
        return <ShieldExclamationIcon className="w-6 h-6 text-yellow-600" />;
      case 'Risky':
        return <ExclamationTriangleIcon className="w-6 h-6 text-red-600" />;
      default:
        return <ClockIcon className="w-6 h-6 text-gray-600" />;
    }
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'high':
        return 'bg-red-100 text-red-700 border-red-200';
      case 'medium':
        return 'bg-yellow-100 text-yellow-700 border-yellow-200';
      case 'low':
        return 'bg-blue-100 text-blue-700 border-blue-200';
      default:
        return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Document Analysis</h1>
        <p className="mt-2 text-sm text-gray-600">
          Upload NDAs and contracts (English or Arabic) for AI-powered risk assessment
        </p>
      </div>

      {/* Upload Section */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Upload Document</h2>

        {/* Document Type Selector */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Document Type
          </label>
          <select
            value={documentType}
            onChange={(e) => setDocumentType(e.target.value as 'nda' | 'contract')}
            className="block w-full px-3 py-2 border border-gray-300 rounded-lg bg-white text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="nda">NDA (Non-Disclosure Agreement)</option>
            <option value="contract">Contract</option>
          </select>
          <p className="mt-1 text-xs text-gray-500">
            {documentType === 'nda'
              ? 'Analysis will focus on confidentiality terms, permitted disclosures, and term length'
              : 'Analysis will focus on deliverables, payment terms, liability, and termination clauses'
            }
          </p>
        </div>

        <div className="flex items-center gap-4">
          <input
            type="file"
            accept=".txt,.doc,.docx,.pdf"
            onChange={handleFileSelect}
            className="block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none"
          />
          <button
            onClick={handleUpload}
            disabled={!selectedFile || isUploading}
            className="flex items-center gap-2 px-6 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed whitespace-nowrap"
          >
            {isUploading ? (
              <>
                <ClockIcon className="w-5 h-5 animate-spin" />
                Analyzing...
              </>
            ) : (
              <>
                <ArrowUpTrayIcon className="w-5 h-5" />
                Upload & Analyze
              </>
            )}
          </button>
        </div>
        <div className="mt-4 flex items-center gap-2">
          <input
            type="checkbox"
            id="saveToDatabase"
            checked={saveToDatabase}
            onChange={(e) => setSaveToDatabase(e.target.checked)}
            className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
          />
          <label htmlFor="saveToDatabase" className="text-sm text-gray-700 cursor-pointer">
            Save analysis to database (uncheck for quick one-time analysis)
          </label>
        </div>
        {selectedFile && (
          <p className="mt-2 text-sm text-gray-600">
            Selected: {selectedFile.name} ({formatFileSize(selectedFile.size)})
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Documents List */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Your Documents</h2>

            {isLoadingDocuments ? (
              <div className="text-center py-8 text-gray-500">Loading...</div>
            ) : documents.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <DocumentTextIcon className="w-12 h-12 mx-auto mb-2 text-gray-400" />
                <p>No documents uploaded yet</p>
              </div>
            ) : (
              <div className="space-y-2">
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    onClick={() => setSelectedDocument(doc)}
                    className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                      selectedDocument?.id === doc.id
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {doc.file_name}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          {formatDate(doc.uploaded_at)}
                        </p>
                        {doc.status === 'completed' && (
                          <div className="mt-2">
                            <span
                              className={`inline-block px-2 py-1 text-xs font-medium rounded border ${getRiskBadge(
                                doc.risk_category
                              )}`}
                            >
                              {doc.risk_category}
                            </span>
                          </div>
                        )}
                        {doc.status === 'analyzing' && (
                          <span className="inline-block px-2 py-1 text-xs font-medium text-blue-700 bg-blue-100 rounded mt-2">
                            Analyzing...
                          </span>
                        )}
                        {doc.status === 'failed' && (
                          <span className="inline-block px-2 py-1 text-xs font-medium text-red-700 bg-red-100 rounded mt-2">
                            Failed
                          </span>
                        )}
                      </div>
                      {getRiskIcon(doc.risk_category)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Analysis Details */}
        <div className="lg:col-span-2">
          {!selectedDocument ? (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
              <DocumentTextIcon className="w-16 h-16 mx-auto mb-4 text-gray-400" />
              <p className="text-gray-500">Select a document to view analysis</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Header */}
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <h2 className="text-xl font-bold text-gray-900">{selectedDocument.file_name}</h2>
                    <p className="text-sm text-gray-600 mt-1">
                      Uploaded: {formatDate(selectedDocument.uploaded_at)}
                      {selectedDocument.analyzed_at && ` • Analyzed: ${formatDate(selectedDocument.analyzed_at)}`}
                    </p>
                    <p className="text-sm text-gray-600">
                      Language: {selectedDocument.language === 'ar' ? 'Arabic' : 'English'} • Size:{' '}
                      {formatFileSize(selectedDocument.file_size)}
                    </p>
                  </div>
                  <button
                    onClick={() => deleteMutation.mutate(selectedDocument.id)}
                    className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="Delete document"
                  >
                    <TrashIcon className="w-5 h-5" />
                  </button>
                </div>

                {selectedDocument.status === 'completed' && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-600 mb-1">Risk Category</p>
                      <p
                        className={`text-lg font-bold px-3 py-1 rounded inline-block ${getRiskBadge(
                          selectedDocument.risk_category
                        )}`}
                      >
                        {selectedDocument.risk_category}
                      </p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-600 mb-1">Risk Score</p>
                      <p className="text-2xl font-bold text-gray-900">{selectedDocument.risk_score}/100</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-600 mb-1">Issues Found</p>
                      <p className="text-2xl font-bold text-gray-900">
                        {selectedDocument.questionable_clauses?.length || 0}
                      </p>
                    </div>
                  </div>
                )}

                {selectedDocument.status === 'analyzing' && (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
                    <ClockIcon className="w-8 h-8 mx-auto mb-2 text-blue-600 animate-spin" />
                    <p className="text-blue-700 font-medium">Analyzing document...</p>
                  </div>
                )}

                {selectedDocument.status === 'failed' && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <p className="text-red-700 font-medium">Analysis failed</p>
                    {selectedDocument.error_message && (
                      <p className="text-sm text-red-600 mt-1">{selectedDocument.error_message}</p>
                    )}
                  </div>
                )}
              </div>

              {/* Summary */}
              {selectedDocument.summary && (
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">Summary</h3>
                  <p className="text-gray-700 whitespace-pre-wrap">{selectedDocument.summary}</p>
                </div>
              )}

              {/* Questionable Clauses */}
              {selectedDocument.questionable_clauses && selectedDocument.questionable_clauses.length > 0 && (
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Questionable Clauses</h3>
                  <div className="space-y-4">
                    {selectedDocument.questionable_clauses.map((clause, index) => (
                      <div
                        key={index}
                        className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <h4 className="font-semibold text-gray-900">Clause {index + 1}</h4>
                          <span
                            className={`px-2 py-1 text-xs font-medium rounded border ${getSeverityBadge(
                              clause.severity
                            )}`}
                          >
                            {clause.severity.toUpperCase()}
                          </span>
                        </div>

                        <div className="space-y-3">
                          <div>
                            <p className="text-sm font-medium text-gray-700 mb-1">Clause:</p>
                            <p className="text-sm text-gray-600 bg-gray-50 p-2 rounded">{clause.clause}</p>
                          </div>

                          <div>
                            <p className="text-sm font-medium text-gray-700 mb-1">Concern:</p>
                            <p className="text-sm text-gray-600">{clause.concern}</p>
                          </div>

                          <div>
                            <p className="text-sm font-medium text-gray-700 mb-1">Suggestion:</p>
                            <p className="text-sm text-gray-600 bg-green-50 p-2 rounded">{clause.suggestion}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* No issues found */}
              {selectedDocument.status === 'completed' &&
                (!selectedDocument.questionable_clauses || selectedDocument.questionable_clauses.length === 0) && (
                  <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                    <div className="text-center py-8">
                      <CheckCircleIcon className="w-16 h-16 mx-auto mb-4 text-green-600" />
                      <h3 className="text-lg font-semibold text-gray-900 mb-2">No Issues Found</h3>
                      <p className="text-gray-600">This document appears to have standard, acceptable terms.</p>
                    </div>
                  </div>
                )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default NDAAnalysisPage;
