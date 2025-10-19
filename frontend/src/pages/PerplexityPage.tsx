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

interface BatchEnrichmentResponse {
  total: number;
  successful: number;
  failed: number;
  results: EnrichedLeadResult[];
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

  const fetchPrompt = async () => {
    setIsFetchingPrompt(true);
    setEnrichmentResults([]);
    setApprovalState({});

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
      }
    } catch (error: any) {
      console.error('Failed to fetch leads:', error);
      toast.error(`Unable to fetch leads: ${error.message || error}`);
    } finally {
      setIsFetchingPrompt(false);
    }
  };

  // Manual mode: Parse pasted Perplexity output
  const handleManualEnrich = async () => {
    if (!promptData || !perplexityOutput.trim()) {
      toast.error('Please paste Perplexity output');
      return;
    }

    setIsEnriching(true);

    try {
      const response = await fetch(`${API_BASE_URL}/perplexity/parse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          results_text: perplexityOutput,
          update: true
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to parse Perplexity output');
      }

      const data = await response.json();
      toast.success(`Successfully updated ${data.updated} lead${data.updated !== 1 ? 's' : ''} in Odoo`);

      // Refresh the prompt/leads
      fetchPrompt();
      setPerplexityOutput('');
    } catch (error: any) {
      console.error('Error parsing output:', error);
      toast.error(error.message || 'Failed to parse Perplexity output');
    } finally {
      setIsEnriching(false);
    }
  };

  // API mode: Automatic enrichment
  const handleApiEnrich = async () => {
    if (!promptData || promptData.leads.length === 0) {
      toast.error('No leads to enrich');
      return;
    }

    setIsEnriching(true);
    setEnrichmentResults([]);
    setApprovalState({});

    const leadIds = promptData.leads.map((lead) => lead.id);

    try {
      const response = await fetch(`${API_BASE_URL}/perplexity/enrich-batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lead_ids: leadIds }),
      });

      if (!response.ok) {
        throw new Error('Failed to enrich leads');
      }

      const data: BatchEnrichmentResponse = await response.json();
      setEnrichmentResults(data.results);
      setCurrentLeadIndex(0);

      // Initialize approval state
      const initialState: LeadApprovalState = {};
      data.results.forEach((result) => {
        if (result.success) {
          initialState[result.lead_id] = {
            approved: false,
            rejectedFields: new Set(),
          };
        }
      });
      setApprovalState(initialState);

      toast.success(`Enriched ${data.successful} of ${data.total} leads`);
    } catch (error) {
      console.error('Error enriching leads:', error);
      toast.error('Failed to enrich leads');
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
      .map((result) => result.suggested_data);

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

  const renderFieldComparison = (
    leadId: number,
    fieldName: string,
    currentValue: any,
    suggestedValue: any
  ) => {
    const isChanged = currentValue !== suggestedValue && suggestedValue !== '';
    const isEmpty = !currentValue || currentValue === '<br>' || currentValue === '';

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
        <div className="font-medium text-sm text-gray-700 mb-2">{fieldName}</div>
        <div className="space-y-1">
          <div className="text-xs text-gray-500">
            Current:{' '}
            <span className="font-mono text-gray-700">
              {isEmpty ? <em className="text-gray-400">Empty</em> : String(currentValue)}
            </span>
          </div>
          <div className="text-xs text-gray-600">
            Suggested:{' '}
            <span className="font-mono text-gray-900 font-medium">{String(suggestedValue)}</span>
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
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
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
                ? 'bg-blue-600 text-white'
                : 'bg-white text-gray-700 hover:bg-gray-100'
            }`}
          >
            Manual Mode
          </button>
          <button
            onClick={() => setMode('api')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              mode === 'api'
                ? 'bg-blue-600 text-white'
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
                <h2 className="text-lg font-semibold text-blue-600 mb-1">
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
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                >
                  {isFetchingPrompt ? 'Fetching...' : 'Fetch Leads'}
                </button>
              </div>
            ) : (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="bg-blue-50 px-4 py-2 rounded-lg">
                    <p className="text-sm font-semibold text-blue-900">
                      Fetched Leads
                    </p>
                    <p className="text-2xl font-bold text-blue-600">{promptData.leadCount}</p>
                  </div>
                  <button
                    onClick={fetchPrompt}
                    disabled={isFetchingPrompt || isEnriching}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 text-sm"
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
              <h2 className="text-lg font-semibold text-blue-600 mb-1">
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
                <div className="flex items-center justify-between">
                  <div className="text-sm text-gray-600">
                    {!promptData && (
                      <div className="flex items-center gap-2 text-yellow-600">
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                        </svg>
                        Fetch leads first to generate the prompt.
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(promptData.prompt);
                      toast.success('Prompt copied to clipboard!');
                    }}
                    className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
                  >
                    <SparklesIcon className="w-5 h-5" />
                    Generate AI Prompt
                  </button>
                </div>
              ) : (
                <button
                  onClick={handleApiEnrich}
                  disabled={isEnriching || isPushing}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                >
                  {isEnriching ? 'Enriching...' : `Enrich ${promptData.leadCount} Lead${promptData.leadCount !== 1 ? 's' : ''}`}
                </button>
              )}
            </div>
          </div>
        )}

        {/* Step 3: Paste Results (Manual mode only) */}
        {mode === 'manual' && promptData && promptData.leads.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 mb-6">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-blue-600 mb-1">
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
                className="w-full h-64 p-3 border border-gray-300 rounded-lg font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
        )}

        {/* Step 4: Update Odoo (Manual mode only) */}
        {mode === 'manual' && promptData && promptData.leads.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 mb-6">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-blue-600 mb-1">
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
                    Update 0 Leads in Odoo
                  </>
                )}
              </button>
            </div>
          </div>
        )}

      {/* Step 3: Review & Approve (API mode only) */}
      {mode === 'api' && enrichmentResults.length > 0 && (
        <>
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">
                  Step 3: Review & Push to Odoo
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
    </div>
  );
};

export default PerplexityPage;
