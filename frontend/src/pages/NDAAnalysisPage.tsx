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
  ChatBubbleLeftRightIcon,
  PaperAirplaneIcon,
  XMarkIcon,
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
  approval_status?: 'pending' | 'approved' | 'rejected';
  approved_by?: string;
  approved_at?: string;
  teams_message_id?: string;
  selected_entity?: string;
  counterparty_name?: string;
  filled_pdf_url?: string;
}

interface PrezlabEntity {
  name: string;
  company_name: string;
  company_address: string;
  authorised_signatory: string;
}

const NDAAnalysisPage: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [saveToDatabase, setSaveToDatabase] = useState(true);
  const [documentType, setDocumentType] = useState<'nda' | 'contract'>('nda');
  const [selectedDocument, setSelectedDocument] = useState<NDADocument | null>(null);
  const [showChatbot, setShowChatbot] = useState(false);
  const [chatMessages, setChatMessages] = useState<Array<{role: 'user' | 'assistant', content: string}>>([]);
  const [chatInput, setChatInput] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [showFillPDFModal, setShowFillPDFModal] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState<string>('');
  const [counterpartyName, setCounterpartyName] = useState<string>('');
  const [isGeneratingPDF, setIsGeneratingPDF] = useState(false);
  const [isAIFilling, setIsAIFilling] = useState(false);
  const [aiFillReport, setAIFillReport] = useState<any>(null);
  const queryClient = useQueryClient();

  // Fetch NDA documents
  const { data: documentsData, isLoading: isLoadingDocuments } = useQuery(
    'nda-documents',
    () => api.getNDADocuments(),
    {
      refetchInterval: 5000, // Refetch every 5 seconds to check for analysis updates
    }
  );

  // Fetch Prezlab entities
  const { data: entitiesData } = useQuery(
    'prezlab-entities',
    () => api.get('/nda/entities'),
    { staleTime: Infinity }
  );

  const entities: Record<string, PrezlabEntity> = entitiesData?.data?.entities || {};

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

  // Forward to Teams mutation
  const forwardToTeamsMutation = useMutation(
    async ({ documentId, entity, counterparty }: { documentId: string; entity: string; counterparty: string }) => {
      const doc = documents.find(d => d.id === documentId);
      if (!doc) throw new Error('Document not found');

      const reportText = `
<h2>📄 Document Analysis Report</h2>
<hr/>

<p><strong>File:</strong> ${doc.file_name}</p>
<p><strong>Risk Score:</strong> ${doc.risk_score}/100</p>
<p><strong>Risk Category:</strong> ${doc.risk_category}</p>

<h3>Summary</h3>
<p>${doc.summary}</p>

${doc.questionable_clauses && doc.questionable_clauses.length > 0 ? `
<h3>⚠️ Issues Found (${doc.questionable_clauses.length})</h3>
<table border='1' cellpadding='8' cellspacing='0' style='border-collapse: collapse; width: 100%;'>
<tr style='background-color: #f0f0f0;'>
<th>#</th>
<th>Severity</th>
<th>Issue</th>
<th>Concern</th>
<th>Suggestion</th>
</tr>
${doc.questionable_clauses.map((clause, i) => `
<tr style='background-color: ${clause.severity === 'high' ? '#ffebee' : clause.severity === 'medium' ? '#fff3e0' : '#f1f8e9'};'>
<td>${i + 1}</td>
<td><strong style='color: ${clause.severity === 'high' ? 'red' : clause.severity === 'medium' ? 'orange' : 'green'};'>${clause.severity.toUpperCase()}</strong></td>
<td>${clause.clause}</td>
<td>${clause.concern}</td>
<td>${clause.suggestion}</td>
</tr>
`).join('')}
</table>
` : '<p><strong>✅ No issues found</strong></p>'}

<hr/>
<p style='text-align: center; color: gray; font-size: 12px;'>
🤖 Generated with PrezLab Lead Automation System
</p>
      `.trim();

      // Send to Teams via API with entity info
      return api.post('/nda/forward-to-teams', {
        document_id: documentId,
        recipient_email: 'mohammad.arabyat@prezlab.com',
        message: reportText,
        selected_entity: entity || null,
        counterparty_name: counterparty || null
      });
    },
    {
      onSuccess: () => {
        toast.success('Report forwarded to Teams for approval');
        queryClient.invalidateQueries('nda-documents');
      },
      onError: (error: any) => {
        toast.error(error?.response?.data?.detail || 'Failed to forward report');
      },
    }
  );

  const handleGenerateAndDownloadPDF = async () => {
    if (!selectedDocument || !selectedEntity) return;

    setIsGeneratingPDF(true);
    try {
      const response = await api.post('/nda/generate-pdf', {
        document_id: selectedDocument.id,
        selected_entity: selectedEntity,
        counterparty_name: counterpartyName || ''
      }, {
        responseType: 'blob'
      });

      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const fileName = selectedDocument.file_name.replace(/\.(pdf|docx?)$/i, '');
      link.download = `${fileName}_contract_info.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      toast.success('PDF generated and downloaded!');
      setShowFillPDFModal(false);
      setSelectedEntity('');
      setCounterpartyName('');
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || 'Failed to generate PDF');
    } finally {
      setIsGeneratingPDF(false);
    }
  };

  const handleAIFillPDF = async () => {
    if (!selectedDocument || !selectedEntity) return;

    setIsAIFilling(true);
    setAIFillReport(null);
    try {
      const response = await api.post('/nda/ai-fill-pdf', {
        document_id: selectedDocument.id,
        entity_key: selectedEntity,
        counterparty_name: counterpartyName || undefined
      });

      if (response.data.success) {
        setAIFillReport(response.data);
        toast.success(`AI filled ${response.data.fields_filled} fields in the PDF!`);
        queryClient.invalidateQueries('nda-documents');
      }
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || 'Failed to AI-fill PDF');
    } finally {
      setIsAIFilling(false);
    }
  };

  const handleDownloadFilledPDF = async () => {
    if (!selectedDocument) return;

    try {
      const response = await api.get(`/nda/documents/${selectedDocument.id}/download-pdf`, {
        responseType: 'blob'
      });

      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const fileName = selectedDocument.file_name.replace(/\.(pdf|docx?)$/i, '');
      link.download = `${fileName}_filled.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      toast.success('Filled PDF downloaded!');
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || 'Failed to download filled PDF');
    }
  };

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

  const getApprovalBadge = (status?: string) => {
    switch (status) {
      case 'approved':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'rejected':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'pending':
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getApprovalIcon = (status?: string) => {
    switch (status) {
      case 'approved':
        return '✅';
      case 'rejected':
        return '❌';
      case 'pending':
      default:
        return '⏳';
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

      {/* Documents List - Full Width */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Your Documents</h2>

        {isLoadingDocuments ? (
          <div className="text-center py-8 text-gray-500">Loading...</div>
        ) : documents.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <DocumentTextIcon className="w-12 h-12 mx-auto mb-2 text-gray-400" />
            <p>No documents uploaded yet</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {documents.map((doc) => (
              <div
                key={doc.id}
                onClick={() => setSelectedDocument(doc)}
                className={`p-4 rounded-lg border cursor-pointer transition-all hover:shadow-md ${
                  selectedDocument?.id === doc.id
                    ? 'border-blue-500 bg-blue-50 shadow-md'
                    : 'border-gray-200 hover:border-gray-300 bg-white'
                }`}
              >
                <div className="flex items-start justify-between mb-3">
                  {getRiskIcon(doc.risk_category)}
                  {doc.status === 'completed' && doc.risk_score !== undefined && (
                    <div className="text-right">
                      <div className="text-2xl font-bold text-gray-900">{doc.risk_score}</div>
                      <div className="text-xs text-gray-500">/ 100</div>
                    </div>
                  )}
                </div>
                <p className="text-sm font-medium text-gray-900 truncate mb-1">
                  {doc.file_name}
                </p>
                <p className="text-xs text-gray-500 mb-3">
                  {formatDate(doc.uploaded_at)}
                </p>
                <div className="flex flex-wrap gap-2">
                  {doc.status === 'completed' && (
                    <span
                      className={`inline-block px-2 py-1 text-xs font-medium rounded border ${getRiskBadge(
                        doc.risk_category
                      )}`}
                    >
                      {doc.risk_category}
                    </span>
                  )}
                  {doc.status === 'analyzing' && (
                    <span className="inline-block px-2 py-1 text-xs font-medium text-blue-700 bg-blue-100 rounded">
                      Analyzing...
                    </span>
                  )}
                  {doc.status === 'failed' && (
                    <span className="inline-block px-2 py-1 text-xs font-medium text-red-700 bg-red-100 rounded">
                      Failed
                    </span>
                  )}
                  {doc.approval_status && (
                    <span
                      className={`inline-block px-2 py-1 text-xs font-medium rounded border ${getApprovalBadge(
                        doc.approval_status
                      )}`}
                    >
                      {getApprovalIcon(doc.approval_status)} {doc.approval_status.charAt(0).toUpperCase() + doc.approval_status.slice(1)}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Analysis Details - Full Width */}
      {selectedDocument && (
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
                    {selectedDocument.approval_status && selectedDocument.approval_status !== 'pending' && (
                      <div className="mt-2">
                        <span
                          className={`inline-block px-3 py-1 text-sm font-medium rounded border ${getApprovalBadge(
                            selectedDocument.approval_status
                          )}`}
                        >
                          {getApprovalIcon(selectedDocument.approval_status)}{' '}
                          {selectedDocument.approval_status.charAt(0).toUpperCase() + selectedDocument.approval_status.slice(1)}
                          {selectedDocument.approved_by && ` by ${selectedDocument.approved_by}`}
                          {selectedDocument.approved_at && ` on ${formatDate(selectedDocument.approved_at)}`}
                        </span>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {selectedDocument.status === 'completed' && (
                      <>
                        <button
                          onClick={() => {
                            setShowChatbot(true);
                            setChatMessages([]);
                          }}
                          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
                          title="Ask questions about this document"
                        >
                          <ChatBubbleLeftRightIcon className="w-5 h-5" />
                          Ask AI
                        </button>
                        <button
                          onClick={() => setShowFillPDFModal(true)}
                          className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium"
                          title="Generate contract info PDF with entity details"
                        >
                          <DocumentTextIcon className="w-5 h-5" />
                          Fill PDF
                        </button>
                        <button
                          onClick={() => forwardToTeamsMutation.mutate({ documentId: selectedDocument.id, entity: '', counterparty: '' })}
                          disabled={forwardToTeamsMutation.isLoading}
                          className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors text-sm font-medium disabled:opacity-50"
                          title="Forward report to Teams for approval"
                        >
                          <PaperAirplaneIcon className="w-5 h-5" />
                          {forwardToTeamsMutation.isLoading ? 'Sending...' : 'Send for Approval'}
                        </button>
                      </>
                    )}
                    <button
                      onClick={() => deleteMutation.mutate(selectedDocument.id)}
                      className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      title="Delete document"
                    >
                      <TrashIcon className="w-5 h-5" />
                    </button>
                  </div>
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

      {/* Chatbot Modal */}
      {showChatbot && selectedDocument && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b">
              <div className="flex items-center gap-2">
                <ChatBubbleLeftRightIcon className="w-6 h-6 text-blue-600" />
                <h3 className="text-lg font-semibold text-gray-900">Ask About This Document</h3>
              </div>
              <button
                onClick={() => setShowChatbot(false)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {chatMessages.length === 0 && (
                <div className="text-center py-8 text-gray-500">
                  <p className="mb-2">Ask me anything about {selectedDocument.file_name}</p>
                  <p className="text-sm">Example: "What are the main risks in this document?"</p>
                </div>
              )}
              {chatMessages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg p-3 ${
                      msg.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-900'
                    }`}
                  >
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  </div>
                </div>
              ))}
              {isChatLoading && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 rounded-lg p-3">
                    <div className="flex gap-2">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Input */}
            <div className="p-4 border-t">
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (!chatInput.trim() || isChatLoading) return;

                  const userMessage = chatInput.trim();
                  setChatInput('');
                  setChatMessages(prev => [...prev, { role: 'user', content: userMessage }]);
                  setIsChatLoading(true);

                  try {
                    // Get API base URL
                    const apiBaseUrl = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

                    // Get auth token
                    const token = localStorage.getItem('prezlab_auth_token') || sessionStorage.getItem('prezlab_auth_token');

                    // Use fetch for streaming
                    const response = await fetch(`${apiBaseUrl}/nda/chat`, {
                      method: 'POST',
                      headers: {
                        'Content-Type': 'application/json',
                        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                      },
                      body: JSON.stringify({
                        document_id: selectedDocument.id,
                        question: userMessage
                      })
                    });

                    if (!response.ok) {
                      throw new Error('Failed to get response');
                    }

                    // Add empty assistant message that we'll update with streaming content
                    const assistantMessageIndex = chatMessages.length + 1;
                    setChatMessages(prev => [...prev, {
                      role: 'assistant',
                      content: ''
                    }]);

                    const reader = response.body?.getReader();
                    const decoder = new TextDecoder();
                    let buffer = '';

                    if (reader) {
                      while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;

                        buffer += decoder.decode(value, { stream: true });
                        const lines = buffer.split('\n');
                        buffer = lines.pop() || '';

                        for (const line of lines) {
                          if (line.startsWith('data: ')) {
                            const data = JSON.parse(line.slice(6));

                            if (data.content) {
                              // Append content to the assistant message
                              setChatMessages(prev => {
                                const newMessages = [...prev];
                                newMessages[assistantMessageIndex] = {
                                  ...newMessages[assistantMessageIndex],
                                  content: newMessages[assistantMessageIndex].content + data.content
                                };
                                return newMessages;
                              });
                            }

                            if (data.error) {
                              toast.error(data.error);
                              break;
                            }

                            if (data.done) {
                              break;
                            }
                          }
                        }
                      }
                    }

                    setIsChatLoading(false);
                  } catch (error: any) {
                    toast.error(error?.message || 'Failed to get response');
                    setChatMessages(prev => [...prev, {
                      role: 'assistant',
                      content: 'Sorry, I encountered an error. Please try again.'
                    }]);
                    setIsChatLoading(false);
                  }
                }}
                className="flex gap-2"
              >
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Ask a question..."
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={isChatLoading}
                />
                <button
                  type="submit"
                  disabled={!chatInput.trim() || isChatLoading}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <PaperAirplaneIcon className="w-5 h-5" />
                </button>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Fill PDF Modal */}
      {showFillPDFModal && selectedDocument && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="text-lg font-semibold text-gray-900">Fill PDF with Entity Info</h3>
              <button
                onClick={() => {
                  setShowFillPDFModal(false);
                  setSelectedEntity('');
                  setCounterpartyName('');
                  setAIFillReport(null);
                }}
                className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <XMarkIcon className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            <div className="p-4 space-y-4">
              <p className="text-sm text-gray-600">
                Fill <strong>{selectedDocument.file_name}</strong> with Prezlab entity information.
              </p>

              {/* Entity Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Prezlab Entity <span className="text-red-500">*</span>
                </label>
                <select
                  value={selectedEntity}
                  onChange={(e) => setSelectedEntity(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                >
                  <option value="">Select entity...</option>
                  {Object.entries(entities).map(([key, entity]) => (
                    <option key={key} value={key}>
                      {entity.name} - {entity.company_name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Show selected entity details */}
              {selectedEntity && entities[selectedEntity] && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                  <p className="text-sm font-medium text-green-900 mb-2">Entity Details:</p>
                  <div className="text-sm text-green-700 space-y-1">
                    <p><strong>Company:</strong> {entities[selectedEntity].company_name}</p>
                    <p><strong>Address:</strong> {entities[selectedEntity].company_address}</p>
                    <p><strong>Signatory:</strong> {entities[selectedEntity].authorised_signatory}</p>
                  </div>
                </div>
              )}

              {/* Counterparty Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Counterparty/Client Name (Optional)
                </label>
                <input
                  type="text"
                  value={counterpartyName}
                  onChange={(e) => setCounterpartyName(e.target.value)}
                  placeholder="Enter client company name"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                />
              </div>

              {/* AI Fill Report */}
              {aiFillReport && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                  <p className="text-sm font-medium text-blue-900 mb-2">
                    AI Fill Complete - {aiFillReport.fields_filled} fields filled
                  </p>
                  {aiFillReport.fill_report && aiFillReport.fill_report.length > 0 && (
                    <div className="text-sm text-blue-700 space-y-1 max-h-32 overflow-y-auto">
                      {aiFillReport.fill_report.map((field: any, idx: number) => (
                        <p key={idx}>
                          <strong>Page {field.page}:</strong> {field.field} = "{field.value.substring(0, 40)}..."
                        </p>
                      ))}
                    </div>
                  )}
                  <button
                    onClick={handleDownloadFilledPDF}
                    className="mt-3 w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center gap-2"
                  >
                    <DocumentTextIcon className="w-4 h-4" />
                    Download Filled PDF
                  </button>
                </div>
              )}

              {/* Info about AI vs Info Sheet */}
              {selectedDocument.file_name?.toLowerCase().endsWith('.pdf') && !aiFillReport && (
                <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
                  <p className="text-sm text-purple-800">
                    <strong>AI Fill:</strong> Uses AI to identify blank fields in the original PDF and fills them with entity info.
                  </p>
                </div>
              )}
            </div>

            <div className="flex flex-col gap-3 p-4 border-t bg-gray-50">
              {/* AI Fill Button - only for PDFs */}
              {selectedDocument.file_name?.toLowerCase().endsWith('.pdf') && (
                <button
                  onClick={handleAIFillPDF}
                  disabled={!selectedEntity || isAIFilling || isGeneratingPDF}
                  className="w-full px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {isAIFilling ? (
                    <>
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      AI Analyzing & Filling...
                    </>
                  ) : (
                    <>
                      <span className="text-lg">AI</span>
                      Fill Original PDF with AI
                    </>
                  )}
                </button>
              )}

              <div className="flex gap-3">
                <button
                  onClick={() => {
                    setShowFillPDFModal(false);
                    setSelectedEntity('');
                    setCounterpartyName('');
                    setAIFillReport(null);
                  }}
                  className="flex-1 px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors border border-gray-300"
                >
                  Cancel
                </button>
                <button
                  onClick={handleGenerateAndDownloadPDF}
                  disabled={!selectedEntity || isGeneratingPDF || isAIFilling}
                  className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  <DocumentTextIcon className="w-4 h-4" />
                  {isGeneratingPDF ? 'Generating...' : 'Info Sheet'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default NDAAnalysisPage;
