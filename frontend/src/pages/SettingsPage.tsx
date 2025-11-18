import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useQuery, useMutation } from 'react-query';
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
} from '@heroicons/react/24/outline';
import { apiClient } from '../utils/api';

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

export default function SettingsPage() {
  const [isEditing, setIsEditing] = useState(false);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [isAuthenticatingSystem, setIsAuthenticatingSystem] = useState(false);

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
      <div className="space-y-6">
        {/* Odoo Configuration */}
        <div className="card">
          <div className="card-header">
            <div className="flex items-center">
              <div className="flex items-center justify-center h-8 w-8 rounded-md bg-blue-500 mr-3">
                <CogIcon className="h-5 w-5 text-white" />
              </div>
              <h3 className="text-lg font-medium text-gray-900">Odoo Integration</h3>
            </div>
          </div>
          <div className="card-body">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="form-label">Odoo URL</label>
                <input
                  type="text"
                  className="form-input"
                  value={config?.odoo_url || ''}
                  disabled={!isEditing}
                />
              </div>
              <div>
                <label className="form-label">Database</label>
                <input
                  type="text"
                  className="form-input"
                  value={config?.odoo_db || ''}
                  disabled={!isEditing}
                />
              </div>
              <div>
                <label className="form-label">Username</label>
                <input
                  type="text"
                  className="form-input"
                  value={config?.odoo_username || ''}
                  disabled={!isEditing}
                />
              </div>
              <div>
                <label className="form-label">Connection Status</label>
                <div className="mt-1">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                    <div className="h-2 w-2 bg-green-400 rounded-full mr-2"></div>
                    Connected
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Google Sheets Configuration */}
        <div className="card">
          <div className="card-header">
            <div className="flex items-center">
              <div className="flex items-center justify-center h-8 w-8 rounded-md bg-green-500 mr-3">
                <CloudIcon className="h-5 w-5 text-white" />
              </div>
              <h3 className="text-lg font-medium text-gray-900">Google Sheets Integration</h3>
            </div>
          </div>
          <div className="card-body">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="form-label">Service Account Status</label>
                <div className="mt-1">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    config?.google_service_account_configured
                      ? 'bg-green-100 text-green-800'
                      : 'bg-red-100 text-red-800'
                  }`}>
                    <div className={`h-2 w-2 rounded-full mr-2 ${
                      config?.google_service_account_configured ? 'bg-green-400' : 'bg-red-400'
                    }`}></div>
                    {config?.google_service_account_configured ? 'Configured' : 'Not Configured'}
                  </span>
                </div>
              </div>
              <div>
                <label className="form-label">Setup Instructions</label>
                <div className="mt-1">
                  <a
                    href="https://console.cloud.google.com/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800 text-sm"
                  >
                    Google Cloud Console →
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Processing Configuration */}
        <div className="card">
          <div className="card-header">
            <div className="flex items-center">
              <div className="flex items-center justify-center h-8 w-8 rounded-md bg-purple-500 mr-3">
                <UserIcon className="h-5 w-5 text-white" />
              </div>
              <h3 className="text-lg font-medium text-gray-900">Processing Settings</h3>
            </div>
          </div>
          <div className="card-body">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="form-label">Salesperson Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={config?.salesperson_name || ''}
                  disabled={!isEditing}
                />
              </div>
              <div>
                <label className="form-label">Batch Size</label>
                <input
                  type="number"
                  className="form-input"
                  value={config?.batch_size || 50}
                  disabled={!isEditing}
                />
              </div>
              <div>
                <label className="form-label">Max Concurrent Requests</label>
                <input
                  type="number"
                  className="form-input"
                  value={config?.max_concurrent_requests || 5}
                  disabled={!isEditing}
                />
              </div>
            </div>
          </div>
        </div>

        {/* LinkedIn/Apify Configuration */}
        <div className="card">
          <div className="card-header">
            <div className="flex items-center">
              <div className="flex items-center justify-center h-8 w-8 rounded-md bg-blue-600 mr-3">
                <KeyIcon className="h-5 w-5 text-white" />
              </div>
              <h3 className="text-lg font-medium text-gray-900">LinkedIn Enrichment (Apify)</h3>
            </div>
          </div>
          <div className="card-body">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="form-label">API Token Status</label>
                <div className="mt-1">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    config?.apify_token_configured
                      ? 'bg-green-100 text-green-800'
                      : 'bg-yellow-100 text-yellow-800'
                  }`}>
                    <div className={`h-2 w-2 rounded-full mr-2 ${
                      config?.apify_token_configured ? 'bg-green-400' : 'bg-yellow-400'
                    }`}></div>
                    {config?.apify_token_configured ? 'Configured' : 'Optional - Not Configured'}
                  </span>
                </div>
              </div>
              <div>
                <label className="form-label">Setup Instructions</label>
                <div className="mt-1">
                  <a
                    href="https://apify.com/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800 text-sm"
                  >
                    Apify Console →
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

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
        <div className="card-body">
          <p className="text-sm text-gray-600 mb-4">
            Access documentation, guides, and resources to help you use the Lead Automation Hub effectively.
          </p>
          <a
            href="/knowledge-base"
            className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
          >
            <DocumentTextIcon className="h-5 w-5" />
            <span>Open Knowledge Base</span>
            <ArrowTopRightOnSquareIcon className="h-4 w-4" />
          </a>
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
