import React, { useState } from 'react';
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

export default function ConfigPage() {
  const [isEditing, setIsEditing] = useState(false);
  const queryClient = useQueryClient();

  // Fetch configuration
  const { data: config, isLoading } = useQuery<ConfigData>('config',
    () => apiClient.get('/api/config').then(res => res.data)
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

  const handleValidateConfig = () => {
    validateMutation.mutate();
  };

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
        <h1 className="text-3xl font-bold text-gray-900">System Configuration</h1>
        <p className="mt-2 text-gray-600">
          Manage your system settings and integrations
        </p>
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
            {!config?.google_service_account_configured && (
              <div className="mt-4 p-4 bg-gray-50 rounded-md">
                <h4 className="text-sm font-medium text-gray-900 mb-2">Setup Steps:</h4>
                <ol className="text-sm text-gray-600 space-y-1 list-decimal list-inside">
                  <li>Go to Google Cloud Console</li>
                  <li>Create a new project or select existing</li>
                  <li>Enable Google Sheets API</li>
                  <li>Create service account credentials</li>
                  <li>Download JSON key and save as 'google_service_account.json'</li>
                </ol>
              </div>
            )}
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
            {!config?.apify_token_configured && (
              <div className="mt-4 p-4 bg-yellow-50 rounded-md">
                <p className="text-sm text-yellow-800">
                  LinkedIn enrichment is optional but recommended for better lead quality. 
                  Without it, the system will skip LinkedIn profile enrichment.
                </p>
              </div>
            )}
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