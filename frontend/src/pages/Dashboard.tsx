import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';
import {
  PlayIcon,
  ArrowPathIcon,
  ChartBarIcon,
  UserGroupIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';
import { useQuery } from 'react-query';
import ProgressBar from '../components/ProgressBar';
import StatsCard from '../components/StatsCard';
import ActionButton from '../components/ActionButton';
import { useWebSocket } from '../hooks/useWebSocket';
import { apiClient } from '../utils/api';

interface Operation {
  id: string;
  type: string;
  status: string;
  progress: number;
  current_step: string;
  leads_processed: number;
  total_leads: number;
  errors: string[];
  started_at: string;
}

export default function Dashboard() {
  const [currentOperation, setCurrentOperation] = useState<Operation | null>(null);
  const [isExtractingLeads, setIsExtractingLeads] = useState(false);
  const [isEnrichingLeads, setIsEnrichingLeads] = useState(false);
  const [isRunningPipeline, setIsRunningPipeline] = useState(false);
  
  const { lastMessage } = useWebSocket();

  // Fetch configuration
  const { data: config, isLoading: configLoading } = useQuery('config', 
    () => apiClient.get('/api/config').then(res => res.data)
  );

  // Fetch leads count
  const { data: leadsCount, refetch: refetchLeadsCount } = useQuery('leadsCount',
    () => apiClient.get('/api/leads/count').then(res => res.data.count),
    { 
      refetchInterval: 30000, // Refetch every 30 seconds
      enabled: !isExtractingLeads && !isRunningPipeline 
    }
  );

  // Handle WebSocket messages
  useEffect(() => {
    if (lastMessage) {
      try {
        const message = JSON.parse(lastMessage.data);
        if (message.type === 'operation_update') {
          setCurrentOperation(message.data);
          
          // Update button states based on operation status
          const { data } = message;
          if (data.status === 'completed' || data.status === 'failed') {
            setIsExtractingLeads(false);
            setIsEnrichingLeads(false);
            setIsRunningPipeline(false);
            
            // Show notification
            if (data.status === 'completed') {
              toast.success(`${data.type.replace('_', ' ')} completed successfully!`);
            } else {
              toast.error(`${data.type.replace('_', ' ')} failed!`);
            }
            
            // Refetch data
            refetchLeadsCount();
          }
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    }
  }, [lastMessage, refetchLeadsCount]);

  const handleExtractLeads = async () => {
    if (isExtractingLeads) return;
    
    setIsExtractingLeads(true);
    try {
      const response = await apiClient.post('/api/operations/extract-leads');
      toast.success('Started extracting leads from Odoo');
      setCurrentOperation({
        id: response.data.operation_id,
        type: 'extract_leads',
        status: 'starting',
        progress: 0,
        current_step: 'Initializing',
        leads_processed: 0,
        total_leads: 0,
        errors: [],
        started_at: new Date().toISOString(),
      });
    } catch (error) {
      console.error('Error starting lead extraction:', error);
      toast.error('Failed to start lead extraction');
      setIsExtractingLeads(false);
    }
  };

  const handleEnrichLeads = async () => {
    console.log('🔥 FRONTEND: Enrich button clicked!');
    console.log('🔥 FRONTEND: isEnrichingLeads:', isEnrichingLeads);
    console.log('🔥 FRONTEND: isOperationRunning:', isOperationRunning);
    console.log('🔥 FRONTEND: currentOperation:', currentOperation);
    
    if (isEnrichingLeads) {
      console.log('🔥 FRONTEND: Already enriching, returning early');
      return;
    }
    
    setIsEnrichingLeads(true);
    console.log('🔥 FRONTEND: About to call API...');
    try {
      const response = await apiClient.post('/api/operations/enrich-leads');
      console.log('🔥 FRONTEND: API call successful!', response.data);
      toast.success('Started enriching leads');
      setCurrentOperation({
        id: response.data.operation_id,
        type: 'enrich_leads',
        status: 'starting',
        progress: 0,
        current_step: 'Initializing enrichment',
        leads_processed: 0,
        total_leads: 0,
        errors: [],
        started_at: new Date().toISOString(),
      });
    } catch (error) {
      console.error('Error starting lead enrichment:', error);
      toast.error('Failed to start lead enrichment');
      setIsEnrichingLeads(false);
    }
  };

  const handleRunFullPipeline = async () => {
    if (isRunningPipeline) return;
    
    setIsRunningPipeline(true);
    try {
      const response = await apiClient.post('/api/operations/full-pipeline');
      toast.success('Started full automation pipeline');
      setCurrentOperation({
        id: response.data.operation_id,
        type: 'full_pipeline',
        status: 'starting',
        progress: 0,
        current_step: 'Initializing pipeline',
        leads_processed: 0,
        total_leads: 0,
        errors: [],
        started_at: new Date().toISOString(),
      });
    } catch (error) {
      console.error('Error starting full pipeline:', error);
      toast.error('Failed to start full pipeline');
      setIsRunningPipeline(false);
    }
  };

  if (configLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  const isOperationRunning = currentOperation && 
    (currentOperation.status === 'running' || currentOperation.status === 'starting');

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Lead Automation Dashboard</h1>
        <p className="mt-2 text-gray-600">
          Streamline your lead management with automated extraction and enrichment
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        <StatsCard
          title="Unenriched Leads"
          value={leadsCount || 0}
          icon={UserGroupIcon}
          color="blue"
          trend="+12%"
        />
        <StatsCard
          title="Success Rate"
          value="94%"
          icon={CheckCircleIcon}
          color="green"
          trend="+5%"
        />
        <StatsCard
          title="Avg. Processing Time"
          value="2.3 min"
          icon={ClockIcon}
          color="purple"
          trend="-15%"
        />
        <StatsCard
          title="Data Quality"
          value="4.2/5"
          icon={ChartBarIcon}
          color="indigo"
          trend="+0.3"
        />
      </div>

      {/* Main Action Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Extract Leads */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="card"
        >
          <div className="card-body text-center">
            <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-blue-100 mb-4">
              <UserGroupIcon className="h-6 w-6 text-blue-600" />
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">Extract Leads</h3>
            <p className="text-sm text-gray-500 mb-6">
              Pull all unenriched leads from Odoo and prepare them for processing
            </p>
            <ActionButton
              onClick={handleExtractLeads}
              disabled={isOperationRunning || isExtractingLeads}
              loading={isExtractingLeads}
              variant="primary"
              className="w-full"
            >
              {isExtractingLeads ? 'Extracting...' : 'Extract Leads'}
            </ActionButton>
          </div>
        </motion.div>

        {/* Enrich Leads */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="card"
        >
          <div className="card-body text-center">
            <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-100 mb-4">
              <ArrowPathIcon className="h-6 w-6 text-green-600" />
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">Enrich Leads</h3>
            <p className="text-sm text-gray-500 mb-6">
              Enhance leads with company data, LinkedIn profiles, and quality scoring
            </p>
            <ActionButton
              onClick={handleEnrichLeads}
              disabled={isOperationRunning || isEnrichingLeads}
              loading={isEnrichingLeads}
              variant="success"
              className="w-full"
            >
              {isEnrichingLeads ? 'Enriching...' : 'Start Enrichment'}
            </ActionButton>
          </div>
        </motion.div>

        {/* Full Pipeline */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="card"
        >
          <div className="card-body text-center">
            <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-purple-100 mb-4">
              <PlayIcon className="h-6 w-6 text-purple-600" />
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">Full Pipeline</h3>
            <p className="text-sm text-gray-500 mb-6">
              Run the complete automation: extract, enrich, and update Odoo
            </p>
            <ActionButton
              onClick={handleRunFullPipeline}
              disabled={isOperationRunning || isRunningPipeline}
              loading={isRunningPipeline}
              variant="primary"
              className="w-full"
            >
              {isRunningPipeline ? 'Running...' : 'Run Full Pipeline'}
            </ActionButton>
          </div>
        </motion.div>
      </div>

      {/* Operation Progress */}
      {currentOperation && isOperationRunning && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="card mb-8"
        >
          <div className="card-header">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-medium text-gray-900">
                Operation in Progress
              </h3>
              <div className="flex items-center">
                <ClockIcon className="h-5 w-5 text-gray-400 mr-2" />
                <span className="text-sm text-gray-500">
                  Started {new Date(currentOperation.started_at).toLocaleTimeString()}
                </span>
              </div>
            </div>
          </div>
          <div className="card-body">
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">
                  {currentOperation.current_step}
                </span>
                <span className="text-sm text-gray-500">
                  {Math.round(currentOperation.progress)}%
                </span>
              </div>
              <ProgressBar progress={currentOperation.progress} />
            </div>
            
            {currentOperation.total_leads > 0 && (
              <div className="text-sm text-gray-600">
                Processed: {currentOperation.leads_processed} / {currentOperation.total_leads} leads
              </div>
            )}

            {currentOperation.errors.length > 0 && (
              <div className="mt-4">
                <div className="flex items-center mb-2">
                  <ExclamationTriangleIcon className="h-5 w-5 text-yellow-400 mr-2" />
                  <span className="text-sm font-medium text-gray-700">Warnings</span>
                </div>
                <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3">
                  {currentOperation.errors.slice(0, 3).map((error, index) => (
                    <p key={index} className="text-sm text-yellow-800">• {error}</p>
                  ))}
                  {currentOperation.errors.length > 3 && (
                    <p className="text-sm text-yellow-600 mt-1">
                      +{currentOperation.errors.length - 3} more warnings
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        </motion.div>
      )}

      {/* Configuration Status */}
      <div className="card">
        <div className="card-header">
          <h3 className="text-lg font-medium text-gray-900">System Configuration</h3>
        </div>
        <div className="card-body">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Odoo Connection</span>
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  Connected
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Google Sheets</span>
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  config?.google_service_account_configured 
                    ? 'bg-green-100 text-green-800' 
                    : 'bg-red-100 text-red-800'
                }`}>
                  {config?.google_service_account_configured ? 'Configured' : 'Not Configured'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">LinkedIn Enrichment</span>
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  config?.apify_token_configured 
                    ? 'bg-green-100 text-green-800' 
                    : 'bg-yellow-100 text-yellow-800'
                }`}>
                  {config?.apify_token_configured ? 'Enabled' : 'Disabled'}
                </span>
              </div>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Salesperson</span>
                <span className="text-sm font-medium text-gray-900">
                  {config?.salesperson_name}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Batch Size</span>
                <span className="text-sm font-medium text-gray-900">
                  {config?.batch_size}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Max Concurrent</span>
                <span className="text-sm font-medium text-gray-900">
                  {config?.max_concurrent_requests}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}