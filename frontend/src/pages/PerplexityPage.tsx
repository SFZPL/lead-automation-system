import React, { useState } from 'react';
import toast from 'react-hot-toast';
import {
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  SparklesIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';

const API_BASE_URL = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

interface LeadPreview {
  id: number;
  name: string;
  email: string;
  company: string;
}

interface PromptData {
  prompt: string;
  leadCount: number;
  leads: LeadPreview[];
}

interface EnrichedLeadResult {
  lead_id: number;
  success: boolean;
  current_data?: Record<string, any>;
  suggested_data?: Record<string, any>;
  error?: string;
}

interface LeadApprovalState {
  [leadId: number]: {
    approved: boolean;
    rejectedFields: Set<string>;
  };
}

const PerplexityPage: React.FC = () => {
  // Mode selection: 'manual' (copy-paste) or 'api' (automatic)
  const [mode, setMode] = useState<'manual' | 'api'>('manual');

  const [promptData, setPromptData] = useState<PromptData | null>(null);
  const [isFetchingPrompt, setIsFetchingPrompt] = useState(false);
  const [enrichmentResults, setEnrichmentResults] = useState<EnrichedLeadResult[]>([]);
  const [isEnriching, setIsEnriching] = useState(false);
  const [isPushing, setIsPushing] = useState(false);
  const [approvalState, setApprovalState] = useState<LeadApprovalState>({});
  const [currentLeadIndex, setCurrentLeadIndex] = useState(0);

  // Manual mode state
  const [perplexityOutput, setPerplexityOutput] = useState('');

  // Smart analysis state
  const [smartAnalysis, setSmartAnalysis] = useState<any>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [selectedBatchIndex, setSelectedBatchIndex] = useState(0);

  // Editable fields state - tracks manual edits to suggested values
  const [fieldEdits, setFieldEdits] = useState<{
    [leadId: number]: { [fieldName: string]: any };
  }>({});

  // Prompt modal state for Teams app
  const [showPromptModal, setShowPromptModal] = useState(false);
  const [modalPromptText, setModalPromptText] = useState('');

  // Streaming progress state
  const [enrichmentProgress, setEnrichmentProgress] = useState<{
    current: number;
    total: number;
    currentLeadName: string;
  } | null>(null);

  const fetchPrompt = async () => {
    setIsFetchingPrompt(true);
    setEnrichmentResults([]);
    setApprovalState({});
    setSmartAnalysis(null);
    setSelectedBatchIndex(0);

    try {
      const response = await fetch(`${API_BASE_URL}/perplexity/generate`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const data = await response.json();
      const leads = (data.leads || []).map((lead: any, index: number): LeadPreview => ({
        id: lead.id ?? index,
        name: lead.full_name ?? lead.name ?? 'Unknown',
        email: lead.email ?? '',
        company: lead.company_name ?? lead.company ?? '',
      }));

      setPromptData({
        prompt: data.prompt,
        leadCount: data.lead_count ?? leads.length,
        leads,
      });

      if (leads.length === 0) {
        toast('No unenriched leads found in Odoo.', { icon: 'ℹ️' });
      } else {
        toast.success(`Found ${leads.length} unenriched lead${leads.length === 1 ? '' : 's'}`);

        // Automatically run smart analysis for manual mode
        if (mode === 'manual' && leads.length > 0) {
          await fetchSmartAnalysis();
        }
      }
    } catch (error: any) {
      console.error('Failed to fetch leads:', error);
      toast.error(`Unable to fetch leads: ${error.message || error}`);
    } finally {
      setIsFetchingPrompt(false);
    }
  };

  const fetchSmartAnalysis = async () => {
    setIsAnalyzing(true);
    setSmartAnalysis(null);
    setSelectedBatchIndex(0);

    try {
      const response = await fetch(`${API_BASE_URL}/perplexity/smart-analysis`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const data = await response.json();
      setSmartAnalysis(data);

      // Only show toast if batch count > 1 (when splitting is beneficial)
      if (data.recommended_batches > 1) {
        toast.success(`Smart split: ${data.recommended_batches} batches for optimal results`);
      }
    } catch (error: any) {
      console.error('Failed to analyze leads:', error);
      toast.error(`Unable to analyze leads: ${error.message || error}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Manual mode: Parse pasted Perplexity output and show preview
  const handleManualEnrich = async () => {
    if (!promptData || !perplexityOutput.trim()) {
      toast.error('Please paste Perplexity output');
      return;
    }

    setIsEnriching(true);

    try {
      const response = await fetch(`${API_BASE_URL}/perplexity/parse-preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          results_text: perplexityOutput,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to parse Perplexity output');
      }

      const data = await response.json();

      // Set results for preview/approval
      setEnrichmentResults(data.results);
      setCurrentLeadIndex(0);

      // Initialize approval state
      const initialState: LeadApprovalState = {};
      data.results.forEach((result: EnrichedLeadResult) => {
        if (result.success) {
          initialState[result.lead_id] = {
            approved: false,
            rejectedFields: new Set(),
          };
        }
      });
      setApprovalState(initialState);

      toast.success(`Parsed ${data.results.length} lead${data.results.length !== 1 ? 's' : ''}. Review and approve below.`);
    } catch (error: any) {
      console.error('Error parsing output:', error);
      toast.error(error.message || 'Failed to parse Perplexity output');
    } finally {
      setIsEnriching(false);
    }
  };

  // API mode: Automatic enrichment with streaming
  const handleApiEnrich = async () => {
    if (!promptData || promptData.leads.length === 0) {
      toast.error('No leads to enrich');
      return;
    }

    setIsEnriching(true);
    setEnrichmentResults([]);
    setApprovalState({});
    setEnrichmentProgress(null);

    const leadIds = promptData.leads.map((lead) => lead.id);

    try {
      const response = await fetch(`${API_BASE_URL}/perplexity/enrich-batch-stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lead_ids: leadIds }),
      });

      if (!response.ok) {
        throw new Error('Failed to start enrichment');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'progress') {
                setEnrichmentProgress({
                  current: data.current,
                  total: data.total,
                  currentLeadName: data.lead_name,
                });
              } else if (data.type === 'success') {
                // Lead enriched successfully
                console.log(`✓ Enriched: ${data.lead_name}`);
              } else if (data.type === 'error') {
                console.error(`✗ Error enriching ${data.lead_name}: ${data.message}`);
              } else if (data.type === 'complete') {
                // Final results
                setEnrichmentResults(data.results);
                setCurrentLeadIndex(0);

                // Initialize approval state
                const initialState: LeadApprovalState = {};
                data.results.forEach((result: EnrichedLeadResult) => {
                  if (result.success) {
                    initialState[result.lead_id] = {
                      approved: false,
                      rejectedFields: new Set(),
                    };
                  }
                });
                setApprovalState(initialState);

                setEnrichmentProgress(null);
                toast.success(`Enriched ${data.successful} of ${data.total} leads`);
              }
            } catch (e) {
              console.error('Error parsing SSE message:', e);
            }
          }
        }
      }
    } catch (error) {
      console.error('Error enriching leads:', error);
      toast.error('Failed to enrich leads');
      setEnrichmentProgress(null);
    } finally {
      setIsEnriching(false);
    }
  };

  const toggleLeadApproval = (leadId: number) => {
    setApprovalState((prev) => ({
      ...prev,
      [leadId]: {
        ...prev[leadId],
        approved: !prev[leadId]?.approved,
      },
    }));
  };

  const handlePushToOdoo = async () => {
    const approvedLeads = enrichmentResults
      .filter((result) => result.success && approvalState[result.lead_id]?.approved)
      .map((result) => {
        const leadId = result.lead_id;
        const suggestedData = { ...result.suggested_data };

        // Apply any manual edits to the suggested data
        if (fieldEdits[leadId]) {
          Object.keys(fieldEdits[leadId]).forEach(fieldName => {
            suggestedData[fieldName] = fieldEdits[leadId][fieldName];
          });
        }

        return suggestedData;
      });

    if (approvedLeads.length === 0) {
      toast.error('No leads approved for update');
      return;
    }

    setIsPushing(true);

    try {
      const response = await fetch(`${API_BASE_URL}/perplexity/push-approved`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved_leads: approvedLeads }),
      });

      if (!response.ok) {
        throw new Error('Failed to push leads to Odoo');
      }

      const data = await response.json();

      if (data.successful > 0) {
        toast.success(
          `Successfully pushed ${data.successful} lead${
            data.successful !== 1 ? 's' : ''
          } to Odoo${data.failed > 0 ? ` (${data.failed} failed)` : ''}`
        );

        // Clear successful leads from the list
        setEnrichmentResults((prev) =>
          prev.filter(
            (result) =>
              !approvalState[result.lead_id]?.approved ||
              data.errors.includes(String(result.lead_id))
          )
        );

        // Refresh lead list
        fetchPrompt();
      } else {
        toast.error(`Failed to push leads: ${data.errors.join(', ')}`);
      }
    } catch (error) {
      console.error('Error pushing to Odoo:', error);
      toast.error('Failed to push leads to Odoo');
    } finally {
      setIsPushing(false);
    }
  };

  const getChangedFields = (current: Record<string, any>, suggested: Record<string, any>) => {
    const changed: string[] = [];
    Object.keys(suggested).forEach((key) => {
      if (key !== 'id' && suggested[key] !== current[key]) {
        const currentVal = current[key] || '';
        const suggestedVal = suggested[key] || '';
        if (currentVal !== suggestedVal && suggestedVal !== '') {
          changed.push(key);
        }
      }
    });
    return changed;
  };

  const handleFieldEdit = (leadId: number, fieldName: string, newValue: any) => {
    setFieldEdits(prev => ({
      ...prev,
      [leadId]: {
        ...(prev[leadId] || {}),
        [fieldName]: newValue
      }
    }));
  };

  const getEffectiveValue = (leadId: number, fieldName: string, suggestedValue: any) => {
    // If there's a manual edit, use that. Otherwise use the suggested value.
    return fieldEdits[leadId]?.[fieldName] !== undefined
      ? fieldEdits[leadId][fieldName]
      : suggestedValue;
  };

  const renderFieldComparison = (
    leadId: number,
    fieldName: string,
    currentValue: any,
    suggestedValue: any
  ) => {
    const effectiveValue = getEffectiveValue(leadId, fieldName, suggestedValue);
    const isChanged = currentValue !== effectiveValue && effectiveValue !== '';
    const isEmpty = !currentValue || currentValue === '<br>' || currentValue === '';
    const isEdited = fieldEdits[leadId]?.[fieldName] !== undefined;

    return (
      <div
        key={fieldName}
        className={`p-3 rounded-lg border ${
          isChanged
            ? isEmpty
              ? 'bg-green-50 border-green-200'
              : 'bg-yellow-50 border-yellow-200'
            : 'bg-gray-50 border-gray-200'
        }`}
      >
        <div className="font-medium text-sm text-gray-700 mb-2 flex items-center justify-between">
          <span>{fieldName}</span>
          {isEdited && (
            <span className="text-xs text-primary-600 font-normal">✏️ Edited</span>
          )}
        </div>
        <div className="space-y-2">
          <div className="text-xs text-gray-500">
            Current:{' '}
            <span className="font-mono text-gray-700">
              {isEmpty ? <em className="text-gray-400">Empty</em> : String(currentValue)}
            </span>
          </div>
          <div className="text-xs text-gray-600">
            <label className="block mb-1">Suggested (editable):</label>
            <input
              type="text"
              value={effectiveValue || ''}
              onChange={(e) => handleFieldEdit(leadId, fieldName, e.target.value)}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:border-primary-500 focus:ring-1 focus:ring-primary-500 font-mono"
              placeholder="Enter value..."
            />
          </div>
        </div>
      </div>
    );
  };

  const renderLeadCard = (result: EnrichedLeadResult) => {
    if (!result.success || !result.current_data || !result.suggested_data) {
      return (
        <div
          key={result.lead_id}
          className="bg-white rounded-lg shadow-sm border border-red-200 p-6"
        >
          <div className="flex items-center gap-2 text-red-600 mb-2">
            <XCircleIcon className="w-5 h-5" />
            <span className="font-semibold">Lead {result.lead_id} - Failed</span>
          </div>
          <p className="text-sm text-gray-600">{result.error || 'Unknown error'}</p>
        </div>
      );
    }

    const changedFields = getChangedFields(result.current_data, result.suggested_data);
    const isApproved = approvalState[result.lead_id]?.approved ?? false;  // Default to not approved

    return (
      <div
        key={result.lead_id}
        className={`bg-white rounded-lg shadow-sm border ${
          isApproved ? 'border-green-200' : 'border-gray-200'
        } p-6`}
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">
              {result.current_data['Full Name'] || `Lead ${result.lead_id}`}
            </h3>
            <p className="text-sm text-gray-500">
              {result.current_data['Company Name'] || 'No company'}
            </p>
          </div>
          <button
            onClick={() => toggleLeadApproval(result.lead_id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
              isApproved
                ? 'bg-green-100 text-green-700 hover:bg-green-200'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {isApproved ? (
              <>
                <CheckCircleIcon className="w-5 h-5" />
                Approved
              </>
            ) : (
              <>
                <XCircleIcon className="w-5 h-5" />
                Rejected
              </>
            )}
          </button>
        </div>

        {changedFields.length > 0 && (
          <div className="mb-3">
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-800">
              {changedFields.length} field{changedFields.length !== 1 ? 's' : ''} updated
            </span>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {Object.keys(result.suggested_data)
            .filter((key) => key !== 'id')
            .map((fieldName) =>
              renderFieldComparison(
                result.lead_id,
                fieldName,
                result.current_data![fieldName],
                result.suggested_data![fieldName]
              )
            )}
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto p-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Lead Enrichment Workflow
          </h1>
          <p className="text-gray-600">
            Fetch raw leads, generate a Perplexity prompt, paste the AI response, and push the enriched data back into Odoo.
          </p>
        </div>

        {/* Mode Toggle - Compact tabs */}
        <div className="mb-6 flex gap-2">
          <button
            onClick={() => setMode('manual')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              mode === 'manual'
                ? 'bg-primary-600 text-white'
                : 'bg-white text-gray-700 hover:bg-gray-100'
            }`}
          >
            Manual Mode
          </button>
          <button
            onClick={() => setMode('api')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              mode === 'api'
                ? 'bg-primary-600 text-white'
                : 'bg-white text-gray-700 hover:bg-gray-100'
            }`}
          >
            API Mode
          </button>
        </div>

        {/* Step 1: Fetch Leads */}
        <div className="bg-white rounded-lg border border-gray-200 mb-6">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-lg font-semibold text-primary-600 mb-1">
                  Step 1: Fetch Leads
                </h2>
                <p className="text-sm text-gray-600">
                  Retrieve unenriched leads from Odoo.
                </p>
              </div>
            </div>
          </div>

          <div className="p-6">
            {!promptData ? (
              <div className="flex flex-col items-center justify-center py-8">
                <div className="w-16 h-16 mb-4 text-gray-300">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                </div>
                <p className="text-gray-500 mb-4">No leads fetched yet</p>
                <button
                  onClick={fetchPrompt}
                  disabled={isFetchingPrompt || isEnriching}
                  className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                >
                  {isFetchingPrompt ? 'Fetching...' : 'Fetch Leads'}
                </button>
              </div>
            ) : (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="bg-primary-50 px-4 py-2 rounded-lg">
                    <p className="text-sm font-semibold text-primary-900">
                      Fetched Leads
                    </p>
                    <p className="text-2xl font-bold text-primary-600">{promptData.leadCount}</p>
                  </div>
                  <button
                    onClick={fetchPrompt}
                    disabled={isFetchingPrompt || isEnriching}
                    className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-300 text-sm"
                  >
                    Refresh Leads
                  </button>
                </div>

                {/* Leads table */}
                <div className="border border-gray-200 rounded-lg overflow-hidden">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Company</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {promptData.leads.map((lead) => (
                        <tr key={lead.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm text-gray-900">{lead.name}</td>
                          <td className="px-4 py-3 text-sm text-gray-600">{lead.email}</td>
                          <td className="px-4 py-3 text-sm text-gray-600">{lead.company || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Step 2: Generate/Enrich */}
        {promptData && promptData.leads.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 mb-6">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-primary-600 mb-1">
                Step 2: {mode === 'manual' ? 'Generate Prompt' : 'Enrich with API'}
              </h2>
              <p className="text-sm text-gray-600">
                {mode === 'manual'
                  ? 'Copy the generated prompt into Perplexity.'
                  : 'Automatically enrich leads via Perplexity API.'}
              </p>
            </div>

            <div className="p-6">
              {mode === 'manual' ? (
                <div className="space-y-4">
                  {isAnalyzing && (
                    <div className="flex items-center justify-center gap-2 text-primary-600 py-4">
                      <ArrowPathIcon className="w-5 h-5 animate-spin" />
                      <span>Analyzing lead complexity...</span>
                    </div>
                  )}

                  {/* Batch Cards */}
                  {smartAnalysis && smartAnalysis.batches && smartAnalysis.batches.length > 0 ? (
                    <div className="grid gap-4">
                      {smartAnalysis.batches.map((batch: any, index: number) => (
                        <div key={index} className="border border-gray-200 rounded-lg p-4 hover:border-primary-300 transition-colors">
                          <div className="flex items-center justify-between mb-3">
                            <div>
                              <h3 className="font-semibold text-gray-900">
                                {smartAnalysis.batches.length > 1 ? `Prompt ${batch.batch_number} of ${smartAnalysis.batches.length}` : 'Enrichment Prompt'}
                              </h3>
                              <p className="text-sm text-gray-600">{batch.lead_count} lead{batch.lead_count !== 1 ? 's' : ''}</p>
                            </div>
                            <button
                              onClick={() => {
                                // Show modal for manual copy (works reliably in Teams)
                                setModalPromptText(batch.prompt);
                                setShowPromptModal(true);
                              }}
                              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors flex items-center gap-2"
                            >
                              <SparklesIcon className="w-5 h-5" />
                              Copy Prompt
                            </button>
                          </div>

                          {/* Lead List */}
                          <div className="space-y-2">
                            {batch.leads.map((lead: any) => (
                              <div key={lead.id} className="flex items-center gap-2 text-sm bg-gray-50 rounded px-3 py-2">
                                <span className={`px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap ${
                                  lead.complexity === 'Very High' ? 'bg-red-100 text-red-700' :
                                  lead.complexity === 'High' ? 'bg-orange-100 text-orange-700' :
                                  lead.complexity === 'Medium' ? 'bg-yellow-100 text-yellow-700' :
                                  'bg-green-100 text-green-700'
                                }`}>
                                  {lead.complexity}
                                </span>
                                <span className="text-gray-900 font-medium">{lead.name}</span>
                                {lead.factors && lead.factors.length > 0 && (
                                  <span className="text-gray-500 text-xs">({lead.factors.join(', ')})</span>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}

                      {/* Info Box when split into multiple batches */}
                      {smartAnalysis.batches.length > 1 && (
                        <div className="bg-primary-50 border border-primary-200 rounded-lg p-4">
                          <p className="text-sm text-primary-800">
                            💡 <strong>Why split?</strong> Smaller batches allow Perplexity to focus more deeply on each lead,
                            resulting in more accurate LinkedIn URLs and job titles. Process each batch separately for best results.
                          </p>
                        </div>
                      )}
                    </div>
                  ) : !isAnalyzing && promptData && (
                    <div className="text-center text-gray-500 py-8">
                      No batches available. Try refreshing leads.
                    </div>
                  )}
                </div>
              ) : (
                <button
                  onClick={handleApiEnrich}
                  disabled={isEnriching || isPushing}
                  className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                >
                  {isEnriching ? (
                    <>
                      <ArrowPathIcon className="w-5 h-5 animate-spin" />
                      {enrichmentProgress ? (
                        <span>
                          Enriching {enrichmentProgress.currentLeadName}... ({enrichmentProgress.current}/{enrichmentProgress.total})
                        </span>
                      ) : (
                        <span>Starting enrichment...</span>
                      )}
                    </>
                  ) : (
                    `Enrich ${promptData.leadCount} Lead${promptData.leadCount !== 1 ? 's' : ''}`
                  )}
                </button>
              )}
            </div>
          </div>
        )}

        {/* Step 3: Paste Results (Manual mode only) */}
        {mode === 'manual' && promptData && promptData.leads.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 mb-6">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-primary-600 mb-1">
                Step 3: Paste Results
              </h2>
              <p className="text-sm text-gray-600">
                After running the prompt in Perplexity, copy the entire response and paste it here.
              </p>
            </div>

            <div className="p-6">
              <textarea
                value={perplexityOutput}
                onChange={(e) => setPerplexityOutput(e.target.value)}
                placeholder="Paste the full Perplexity response..."
                className="w-full h-64 p-3 border border-gray-300 rounded-lg font-mono text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              />
            </div>
          </div>
        )}

        {/* Step 4: Update Odoo (Manual mode only) */}
        {mode === 'manual' && promptData && promptData.leads.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 mb-6">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-primary-600 mb-1">
                Step 4: Update Odoo
              </h2>
              <p className="text-sm text-gray-600">
                Push the enriched data back into Odoo once it looks correct.
              </p>
            </div>

            <div className="p-6">
              <button
                onClick={handleManualEnrich}
                disabled={isEnriching || !perplexityOutput.trim()}
                className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
              >
                {isEnriching ? (
                  <>
                    <ArrowPathIcon className="w-5 h-5 animate-spin" />
                    Processing...
                  </>
                ) : (
                  <>
                    <CheckCircleIcon className="w-5 h-5" />
                    Parse & Preview
                  </>
                )}
              </button>
            </div>
          </div>
        )}

      {/* Step 3: Review & Approve (Both modes) */}
      {enrichmentResults.length > 0 && (
        <>
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">
                  {mode === 'manual' ? 'Step 5: Review & Push to Odoo' : 'Step 3: Review & Push to Odoo'}
                </h2>
                <p className="text-sm text-gray-600 mt-1">
                  Review changes and approve leads to update in Odoo
                </p>
              </div>
              <button
                onClick={handlePushToOdoo}
                disabled={isPushing || isEnriching}
                className="flex items-center gap-2 px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {isPushing ? (
                  <>
                    <ArrowPathIcon className="w-5 h-5 animate-spin" />
                    Pushing...
                  </>
                ) : (
                  <>
                    <CheckCircleIcon className="w-5 h-5" />
                    Push Approved to Odoo
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Navigation */}
          {enrichmentResults.length > 1 && (
            <div className="flex items-center justify-between mb-4">
              <button
                onClick={() => setCurrentLeadIndex((prev) => Math.max(0, prev - 1))}
                disabled={currentLeadIndex === 0}
                className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeftIcon className="w-5 h-5" />
                Previous
              </button>
              <span className="text-sm text-gray-600">
                Lead {currentLeadIndex + 1} of {enrichmentResults.length}
              </span>
              <button
                onClick={() =>
                  setCurrentLeadIndex((prev) => Math.min(enrichmentResults.length - 1, prev + 1))
                }
                disabled={currentLeadIndex === enrichmentResults.length - 1}
                className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Next
                <ChevronRightIcon className="w-5 h-5" />
              </button>
            </div>
          )}

          {/* Show only current lead */}
          <div>{renderLeadCard(enrichmentResults[currentLeadIndex])}</div>
        </>
      )}

      {!promptData && !isFetchingPrompt && (
        <div className="bg-gray-50 rounded-lg border border-gray-200 p-12 text-center">
          <SparklesIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">Click "Fetch Leads" to get started</p>
        </div>
      )}
      </div>

      {/* Prompt Modal for Teams - Manual Copy */}
      {showPromptModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] flex flex-col">
            <div className="p-6 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Copy Prompt</h3>
              <p className="text-sm text-gray-600 mt-1">Select all text below and copy it manually (Ctrl+A, then Ctrl+C)</p>
            </div>
            <div className="flex-1 overflow-auto p-6">
              <textarea
                readOnly
                value={modalPromptText}
                className="w-full h-full min-h-[400px] p-4 border border-gray-300 rounded-lg font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary-500"
                onClick={(e) => e.currentTarget.select()}
              />
            </div>
            <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={() => setShowPromptModal(false)}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PerplexityPage;
