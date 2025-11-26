import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import toast from 'react-hot-toast';
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  CogIcon,
  KeyIcon,
  CloudIcon,
  UserIcon,
  EnvelopeIcon,
  XCircleIcon,
  ArrowPathIcon,
  TrashIcon,
  DocumentTextIcon,
  ArrowTopRightOnSquareIcon,
  CloudArrowUpIcon,
} from '@heroicons/react/24/outline';
import { apiClient } from '../utils/api';
import api from '../utils/api';

interface ConfigData {
  odoo_url: string;
  odoo_db: string;
  odoo_username: string;
  salesperson_name: string;
  batch_size: number;
  max_concurrent_requests: number;
  google_service_account_configured: boolean;
  apify_token_configured: boolean;
}

interface EmailAuthStatus {
  authorized: boolean;
  user_email?: string;
  user_name?: string;
  expires_soon?: boolean;
}

interface SystemEmailAuthStatus {
  authorized: boolean;
  user_email?: string;
  user_name?: string;
  expires_soon?: boolean;
}

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

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [isAuthenticatingSystem, setIsAuthenticatingSystem] = useState(false);

  // Knowledge Base state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [kbDescription, setKbDescription] = useState<string>('');
  const [documentType, setDocumentType] = useState<string>('general');
  const [isUploading, setIsUploading] = useState<boolean>(false);

  // Fetch configuration
  const { data: config, isLoading } = useQuery<ConfigData>('config',
    () => apiClient.get('/api/config').then(res => res.data)
  );

  // Check email authorization status (now uses authenticated user)
  const authStatusQuery = useQuery(
    ['email-auth-status'],
    async () => {
      const response = await apiClient.get('/auth/outlook/status');
      return response.data as EmailAuthStatus;
    },
    {
      refetchInterval: 30000,
    }
  );

  // Check system email authorization status (engage monitoring account)
  const systemAuthStatusQuery = useQuery(
    ['system-email-auth-status'],
    async () => {
      const response = await apiClient.get('/auth/outlook/system/status');
      return response.data as SystemEmailAuthStatus;
    },
    {
      refetchInterval: 30000,
    }
  );

  // Fetch Knowledge Base documents
  const { data: kbDocuments = [], isLoading: isLoadingKB, refetch: refetchKB } = useQuery<KnowledgeBaseDocument[]>(
    'knowledge-base-documents',
    async () => {
      const response = await api.get('/knowledge-base/documents');
      return response.data;
    }
  );

  // Upload Knowledge Base document mutation
  const uploadKBMutation = useMutation(
    async () => {
      if (!selectedFile) throw new Error('No file selected');

      const formData = new FormData();
      formData.append('file', selectedFile);
      if (kbDescription.trim()) {
        formData.append('description', kbDescription.trim());
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
        setKbDescription('');
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

  // Delete Knowledge Base document mutation
  const deleteKBMutation = useMutation(
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

  // Validate configuration mutation
  const validateMutation = useMutation(
    () => apiClient.post('/api/validate-config').then(res => res.data),
    {
      onSuccess: (data) => {
        if (data.valid) {
          toast.success('Configuration is valid!');
        } else {
          toast.error('Configuration has errors');
        }
      },
      onError: () => {
        toast.error('Failed to validate configuration');
      }
    }
  );

  // Start OAuth flow
  const startAuthMutation = useMutation(
    async () => {
      const response = await apiClient.get('/auth/outlook/start');
      const data = response.data;

      localStorage.setItem('oauth_state', data.state);

      setIsAuthenticating(true);

      const authWindow = window.open(
        data.authorization_url,
        '_blank',
        'width=600,height=700'
      );

      if (!authWindow) {
        throw new Error('Popup blocked. Please allow popups for this site.');
      }

      const checkClosed = setInterval(() => {
        if (authWindow.closed) {
          clearInterval(checkClosed);
          setIsAuthenticating(false);
          authStatusQuery.refetch();
        }
      }, 1000);
    },
    {
      onError: (error: any) => {
        setIsAuthenticating(false);
        toast.error(error.message || 'Failed to start authorization');
      },
    }
  );

  // Start System OAuth flow (for automated.response@prezlab.com)
  // Helper functions for Knowledge Base
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

  const handleKBUpload = () => {
    if (!selectedFile) {
      toast.error('Please select a PDF file first');
      return;
    }
    uploadKBMutation.mutate();
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
      return 'Unknown date';
    }
  };

  const startSystemAuthMutation = useMutation(
    async () => {
      const response = await apiClient.get('/auth/outlook/system/start');
      const data = response.data;

      localStorage.setItem('oauth_system_state', data.state);

      setIsAuthenticatingSystem(true);

      const authWindow = window.open(
        data.authorization_url,
        '_blank',
        'width=600,height=700'
      );

      if (!authWindow) {
        throw new Error('Popup blocked. Please allow popups for this site.');
      }

      const checkClosed = setInterval(() => {
        if (authWindow.closed) {
          clearInterval(checkClosed);
          setIsAuthenticatingSystem(false);
          systemAuthStatusQuery.refetch();
        }
      }, 1000);
    },
    {
      onError: (error: any) => {
        setIsAuthenticatingSystem(false);
        toast.error(error.message || 'Failed to start system authorization');
      },
    }
  );

  // Revoke access mutation
  const revokeMutation = useMutation(
    async () => {
      await apiClient.delete('/auth/outlook');
    },
    {
      onSuccess: () => {
        toast.success('Email access revoked successfully');
        authStatusQuery.refetch();
      },
      onError: () => {
        toast.error('Failed to revoke access');
      },
    }
  );

  // Revoke system access mutation
  const revokeSystemMutation = useMutation(
    async () => {
      await apiClient.delete('/auth/outlook/system');
    },
    {
      onSuccess: () => {
        toast.success('System email access revoked successfully');
        systemAuthStatusQuery.refetch();
      },
      onError: () => {
        toast.error('Failed to revoke system access');
      },
    }
  );

  const handleValidateConfig = () => {
    validateMutation.mutate();
  };

  const authStatus = authStatusQuery.data;
  const isAuthorized = authStatus?.authorized ?? false;
  const systemAuthStatus = systemAuthStatusQuery.data;
  const isSystemAuthorized = systemAuthStatus?.authorized ?? false;

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded mb-4"></div>
          <div className="h-96 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
        <p className="mt-2 text-gray-600">
          Manage your system configuration, integrations, and email connections
        </p>
      </div>

      {/* System Email Configuration (Admin Only) */}
      <div className="card mb-6">
        <div className="card-header">
          <div className="flex items-center">
            <div className="flex items-center justify-center h-8 w-8 rounded-md bg-amber-500 mr-3">
              <CogIcon className="h-5 w-5 text-white" />
            </div>
            <h3 className="text-lg font-medium text-gray-900">System Email (Engage Monitoring)</h3>
          </div>
        </div>
        <div className="card-body">
          <p className="text-sm text-gray-600 mb-4">
            Connect <strong>automated.response@prezlab.com</strong> to enable monitoring of the engage group inbox
            for proposal follow-ups. This only needs to be set up once and will auto-refresh.
          </p>

          <div className="space-y-4">
            {/* System Status Display */}
            {systemAuthStatusQuery.isLoading && (
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <ArrowPathIcon className="h-4 w-4 animate-spin" />
                Checking system email status...
              </div>
            )}

            {!systemAuthStatusQuery.isLoading && isSystemAuthorized && systemAuthStatus && (
              <div className="rounded-lg border border-green-200 bg-green-50 p-4">
                <div className="flex items-start gap-3">
                  <CheckCircleIcon className="h-5 w-5 text-green-600" />
                  <div className="flex-1">
                    <h4 className="text-sm font-semibold text-green-900">System Email Connected</h4>
                    <p className="mt-1 text-sm text-green-700">
                      {systemAuthStatus.user_name && <span className="font-medium">{systemAuthStatus.user_name}</span>}
                      {systemAuthStatus.user_email && (
                        <span className="ml-2 text-green-600">({systemAuthStatus.user_email})</span>
                      )}
                    </p>
                    {systemAuthStatus.expires_soon && (
                      <p className="mt-2 text-xs text-amber-600">
                        ⚠️ Token will expire soon. Click "Reconnect" to refresh.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {!systemAuthStatusQuery.isLoading && !isSystemAuthorized && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
                <div className="flex items-start gap-3">
                  <ExclamationTriangleIcon className="h-5 w-5 text-amber-600" />
                  <div>
                    <h4 className="text-sm font-semibold text-amber-900">System Email Not Connected</h4>
                    <p className="mt-1 text-sm text-amber-700">
                      The engage monitoring account needs to be connected. Click "Connect System Email" and authorize
                      with <strong>automated.response@prezlab.com</strong> credentials.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* System Action Buttons */}
            <div className="flex flex-wrap gap-3">
              {!isSystemAuthorized ? (
                <button
                  type="button"
                  onClick={() => startSystemAuthMutation.mutate()}
                  disabled={isAuthenticatingSystem || startSystemAuthMutation.isLoading}
                  className="btn-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isAuthenticatingSystem ? (
                    <>
                      <ArrowPathIcon className="h-4 w-4 animate-spin" />
                      Waiting for authorization...
                    </>
                  ) : (
                    <>
                      <CogIcon className="h-4 w-4" />
                      Connect System Email
                    </>
                  )}
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => startSystemAuthMutation.mutate()}
                    disabled={isAuthenticatingSystem || startSystemAuthMutation.isLoading}
                    className="inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                  >
                    <ArrowPathIcon className="h-4 w-4 mr-2" />
                    Reconnect System Email
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (window.confirm('Are you sure you want to revoke system email access? This will disable proposal follow-ups.')) {
                        revokeSystemMutation.mutate();
                      }
                    }}
                    disabled={revokeSystemMutation.isLoading}
                    className="inline-flex items-center rounded-md border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 shadow-sm hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
                  >
                    <TrashIcon className="h-4 w-4 mr-2" />
                    Revoke System Access
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Personal Email Integration Section */}
      <div className="card mb-6">
        <div className="card-header">
          <div className="flex items-center">
            <div className="flex items-center justify-center h-8 w-8 rounded-md bg-indigo-500 mr-3">
              <EnvelopeIcon className="h-5 w-5 text-white" />
            </div>
            <h3 className="text-lg font-medium text-gray-900">Personal Email (For Sending)</h3>
          </div>
        </div>
        <div className="card-body">
          <p className="text-sm text-gray-600 mb-4">
            Connect your personal Microsoft email account to send follow-up emails. All sent emails will
            automatically CC engage@prezlab.com.
          </p>

          <div className="space-y-4">
            {/* Status Display */}
            {authStatusQuery.isLoading && (
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <ArrowPathIcon className="h-4 w-4 animate-spin" />
                Checking authorization status...
              </div>
            )}

            {!authStatusQuery.isLoading && isAuthorized && authStatus && (
              <div className="rounded-lg border border-green-200 bg-green-50 p-4">
                <div className="flex items-start gap-3">
                  <CheckCircleIcon className="h-5 w-5 text-green-600" />
                  <div className="flex-1">
                    <h4 className="text-sm font-semibold text-green-900">Connected</h4>
                    <p className="mt-1 text-sm text-green-700">
                      {authStatus.user_name && <span className="font-medium">{authStatus.user_name}</span>}
                      {authStatus.user_email && (
                        <span className="ml-2 text-green-600">({authStatus.user_email})</span>
                      )}
                    </p>
                    {authStatus.expires_soon && (
                      <p className="mt-2 text-xs text-amber-600">
                        ⚠️ Your access token will expire soon. Click "Reconnect" to refresh.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {!authStatusQuery.isLoading && !isAuthorized && (
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <div className="flex items-start gap-3">
                  <XCircleIcon className="h-5 w-5 text-gray-400" />
                  <div>
                    <h4 className="text-sm font-semibold text-gray-900">Not Connected</h4>
                    <p className="mt-1 text-sm text-gray-600">
                      Click "Connect Email" below to authorize access to your Microsoft email.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex flex-wrap gap-3">
              {!isAuthorized ? (
                <button
                  type="button"
                  onClick={() => startAuthMutation.mutate()}
                  disabled={isAuthenticating || startAuthMutation.isLoading}
                  className="btn-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isAuthenticating ? (
                    <>
                      <ArrowPathIcon className="h-4 w-4 animate-spin" />
                      Waiting for authorization...
                    </>
                  ) : (
                    <>
                      <EnvelopeIcon className="h-4 w-4" />
                      Connect Email
                    </>
                  )}
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => startAuthMutation.mutate()}
                    disabled={isAuthenticating || startAuthMutation.isLoading}
                    className="inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                  >
                    <ArrowPathIcon className="h-4 w-4 mr-2" />
                    Reconnect
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (window.confirm('Are you sure you want to revoke email access?')) {
                        revokeMutation.mutate();
                      }
                    }}
                    disabled={revokeMutation.isLoading}
                    className="inline-flex items-center rounded-md border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 shadow-sm hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
                  >
                    <TrashIcon className="h-4 w-4 mr-2" />
                    Revoke Access
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Quick Validation */}
      <div className="card mb-6">
        <div className="card-header">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium text-gray-900">Configuration Status</h3>
            <button
              onClick={handleValidateConfig}
              disabled={validateMutation.isLoading}
              className="btn-primary flex items-center gap-2"
            >
              {validateMutation.isLoading ? (
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
              ) : (
                <CheckCircleIcon className="h-4 w-4" />
              )}
              Validate Configuration
            </button>
          </div>
        </div>
        <div className="card-body">
          {validateMutation.data && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-4"
            >
              {validateMutation.data.errors?.length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded-md p-4">
                  <div className="flex">
                    <ExclamationTriangleIcon className="h-5 w-5 text-red-400" />
                    <div className="ml-3">
                      <h3 className="text-sm font-medium text-red-800">
                        Configuration Errors
                      </h3>
                      <div className="mt-2 text-sm text-red-700">
                        <ul className="list-disc pl-5 space-y-1">
                          {validateMutation.data.errors.map((error: string, index: number) => (
                            <li key={index}>{error}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {validateMutation.data.warnings?.length > 0 && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
                  <div className="flex">
                    <ExclamationTriangleIcon className="h-5 w-5 text-yellow-400" />
                    <div className="ml-3">
                      <h3 className="text-sm font-medium text-yellow-800">
                        Configuration Warnings
                      </h3>
                      <div className="mt-2 text-sm text-yellow-700">
                        <ul className="list-disc pl-5 space-y-1">
                          {validateMutation.data.warnings.map((warning: string, index: number) => (
                            <li key={index}>{warning}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {validateMutation.data.valid && (
                <div className="bg-green-50 border border-green-200 rounded-md p-4">
                  <div className="flex">
                    <CheckCircleIcon className="h-5 w-5 text-green-400" />
                    <div className="ml-3">
                      <h3 className="text-sm font-medium text-green-800">
                        Configuration Valid
                      </h3>
                      <div className="mt-2 text-sm text-green-700">
                        All required settings are properly configured.
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </div>
      </div>

      {/* Configuration Sections */}
      {/* Knowledge Base Section */}
      <div className="card mb-6">
        <div className="card-header">
          <div className="flex items-center">
            <div className="flex items-center justify-center h-8 w-8 rounded-md bg-purple-500 mr-3">
              <DocumentTextIcon className="h-5 w-5 text-white" />
            </div>
            <h3 className="text-lg font-medium text-gray-900">Knowledge Base</h3>
          </div>
        </div>
        <div className="card-body space-y-6">
          <p className="text-sm text-gray-600">
            Upload PDFs containing company information, reference templates, and guides. These documents provide context for AI analyses and document generation.
          </p>

          {/* Upload Form */}
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 space-y-4">
            <h4 className="text-sm font-semibold text-gray-900">Upload New Document</h4>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">PDF File</label>
              <input
                type="file"
                accept=".pdf"
                onChange={handleFileChange}
                className="block w-full text-sm text-gray-500 file:mr-4 file:rounded-md file:border-0 file:bg-purple-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-purple-700"
              />
              {selectedFile && (
                <p className="mt-1 text-sm text-gray-600">
                  Selected: {selectedFile.name} ({formatFileSize(selectedFile.size)})
                </p>
              )}
            </div>

            <div>
              <label htmlFor="kb_description" className="block text-sm font-medium text-gray-700 mb-1">
                Description (Optional)
              </label>
              <input
                id="kb_description"
                type="text"
                value={kbDescription}
                onChange={(e) => setKbDescription(e.target.value)}
                placeholder="Brief description of this document..."
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
              />
            </div>

            <div>
              <label htmlFor="kb_document_type" className="block text-sm font-medium text-gray-700 mb-1">
                Document Type
              </label>
              <select
                id="kb_document_type"
                value={documentType}
                onChange={(e) => setDocumentType(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
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
              onClick={handleKBUpload}
              disabled={!selectedFile || isUploading}
              className="inline-flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50"
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

          {/* Documents List */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-semibold text-gray-900">
                Uploaded Documents ({kbDocuments.length})
              </h4>
              <button
                onClick={() => refetchKB()}
                className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                <ArrowPathIcon className={`h-4 w-4 ${isLoadingKB ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>

            <div className="space-y-2">
              {isLoadingKB && (
                <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-4 text-center text-sm text-gray-500">
                  Loading documents...
                </div>
              )}

              {!isLoadingKB && kbDocuments.length === 0 && (
                <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-4 text-center text-sm text-gray-500">
                  No documents uploaded yet. Upload your first PDF above to get started.
                </div>
              )}

              {kbDocuments.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-start justify-between rounded-lg border border-gray-200 bg-white p-3"
                >
                  <div className="flex gap-3">
                    <DocumentTextIcon className="h-5 w-5 flex-shrink-0 text-gray-400 mt-0.5" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h5 className="text-sm font-medium text-gray-900 truncate">{doc.filename}</h5>
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
                        <p className="mt-1 text-xs text-gray-600">{doc.description}</p>
                      )}
                      <div className="mt-1 flex gap-3 text-xs text-gray-500">
                        <span>{formatFileSize(doc.file_size)}</span>
                        <span>Uploaded {formatDate(doc.created_at)}</span>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => {
                      if (window.confirm(`Are you sure you want to delete "${doc.filename}"?`)) {
                        deleteKBMutation.mutate(doc.id);
                      }
                    }}
                    disabled={deleteKBMutation.isLoading}
                    className="inline-flex items-center gap-1 rounded-md border border-red-300 bg-white px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 flex-shrink-0"
                  >
                    <TrashIcon className="h-3.5 w-3.5" />
                    Delete
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Edit Mode Toggle */}
      <div className="mt-8 flex justify-end">
        <button
          onClick={() => setIsEditing(!isEditing)}
          className={`${isEditing ? 'btn-success' : 'btn-primary'} flex items-center gap-2`}
        >
          <CogIcon className="h-4 w-4" />
          {isEditing ? 'Save Changes' : 'Edit Configuration'}
        </button>
      </div>
    </div>
  );
}
