import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from 'react-query';
import toast from 'react-hot-toast';
import {
  SparklesIcon,
  ArrowPathIcon,
  MagnifyingGlassIcon,
  EnvelopeOpenIcon,
  ClipboardDocumentListIcon,
  ClockIcon,
  UserCircleIcon,
  BanknotesIcon,
  ExclamationTriangleIcon,
  HeartIcon,
  TrashIcon,
  BuildingOfficeIcon,
  PencilIcon,
  DocumentTextIcon,
  XCircleIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';
import api from '../utils/api';

interface LostLeadSummary {
  id: number;
  name: string;
  record_type?: string;  // 'lead' or 'opportunity'
  partner_name?: string;
  contact_name?: string;
  stage?: string;
  lost_reason?: string;
  lost_reason_category?: string;
  probability?: number;
  expected_revenue?: number;
  salesperson?: string;
  email?: string;
  phone?: string;
  mobile?: string;
  create_date?: string;
  last_update?: string;
}

interface LostLeadMessage {
  id?: number;
  date?: string;
  formatted_date?: string;
  author?: string;
  subject?: string;
  body: string;
}

interface LostLeadAnalysis {
  lead: Record<string, any>;
  analysis: Record<string, any>;
  internal_notes: LostLeadMessage[];
  emails: LostLeadMessage[];
}

interface SharedAnalysis {
  id: string;
  lead_id: number;
  title: string;
  analysis_data: LostLeadAnalysis;
  created_by_user_id: number;
  created_at: string;
  lead_name?: string;
  company_name?: string;
}

const extractStringItems = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.reduce<string[]>((acc, item) => {
    let text: string | null = null;

    if (typeof item === 'string') {
      text = item.trim();
    } else if (item && typeof item === 'object') {
      const candidate =
        (item as Record<string, unknown>).text ??
        (item as Record<string, unknown>).content ??
        (item as Record<string, unknown>).value;

      if (typeof candidate === 'string') {
        text = candidate.trim();
      }
    } else if (typeof item === 'number' || typeof item === 'boolean') {
      text = String(item).trim();
    }

    if (text && text.length > 0) {
      acc.push(text);
    }

    return acc;
  }, []);
};

const LostLeadsPage: React.FC = () => {
  const [limit, setLimit] = useState<number>(10);
  const [salesperson, setSalesperson] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  // Load insights from sessionStorage on mount
  const [insights, setInsights] = useState<Record<number, LostLeadAnalysis>>(() => {
    try {
      const saved = sessionStorage.getItem('lost_lead_insights');
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  // Load selected lead ID from sessionStorage on mount
  const [selectedLeadId, setSelectedLeadId] = useState<number | null>(() => {
    try {
      const saved = sessionStorage.getItem('lost_lead_selected_id');
      return saved ? parseInt(saved, 10) : null;
    } catch {
      return null;
    }
  });

  const [loadingStep, setLoadingStep] = useState<number>(0);
  const [showSaveModal, setShowSaveModal] = useState<boolean>(false);
  const [saveTitle, setSaveTitle] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'analyze' | 'saved' | 'reports'>('analyze');
  const [expandedSavedId, setExpandedSavedId] = useState<string | null>(null);
  const [editingAnalysisId, setEditingAnalysisId] = useState<string | null>(null);
  const [showDraftModal, setShowDraftModal] = useState<boolean>(false);
  const [selectedSavedItem, setSelectedSavedItem] = useState<SharedAnalysis | null>(null);
  const [draftEmail, setDraftEmail] = useState<string>('');
  const [isGeneratingDraft, setIsGeneratingDraft] = useState<boolean>(false);
  const [draftSubject, setDraftSubject] = useState<string>('');
  const [draftCc, setDraftCc] = useState<string>('engage@prezlab.com');
  const [isSendingEmail, setIsSendingEmail] = useState<boolean>(false);
  const [editingInPlace, setEditingInPlace] = useState<boolean>(false);
  const [editedTitle, setEditedTitle] = useState<string>('');
  const [reportLimit, setReportLimit] = useState<number>(50);
  const [reportTypeFilter, setReportTypeFilter] = useState<string>('');
  const [isGeneratingReport, setIsGeneratingReport] = useState<boolean>(false);
  const [reportData, setReportData] = useState<any>(null);

  const queryClient = useQueryClient();

  // Persist insights to sessionStorage whenever they change
  React.useEffect(() => {
    sessionStorage.setItem('lost_lead_insights', JSON.stringify(insights));
  }, [insights]);

  // Persist selected lead ID whenever it changes
  React.useEffect(() => {
    if (selectedLeadId !== null) {
      sessionStorage.setItem('lost_lead_selected_id', selectedLeadId.toString());
    }
  }, [selectedLeadId]);

  // Loading steps for multi-step indicator
  const loadingSteps = [
    'Connecting to Odoo...',
    'Fetching lead details...',
    'Searching engage emails...',
    'Analyzing with AI...',
    'Generating insights...'
  ];

  const lostLeadsQuery = useQuery(
    ['lost-leads', limit, salesperson, typeFilter],
    async () => {
      const params: { limit: number; salesperson?: string; type_filter?: string } = { limit };
      if (salesperson.trim()) {
        params.salesperson = salesperson.trim();
      }
      if (typeFilter.trim()) {
        params.type_filter = typeFilter.trim();
      }
      const response = await api.getLostLeads(params);
      return response.data;
    },
    {
      keepPreviousData: true,
      onError: (error: any) => {
        toast.error(error?.response?.data?.detail || 'Unable to fetch lost leads');
      },
    }
  );

  const leads: LostLeadSummary[] = useMemo(() => lostLeadsQuery.data?.items ?? [], [lostLeadsQuery.data]);

  const analyzeMutation = useMutation(
    async ({ leadId }: { leadId: number }) => {
      // Reset and start progressing through steps
      setLoadingStep(0);
      const stepInterval = setInterval(() => {
        setLoadingStep(prev => Math.min(prev + 1, loadingSteps.length - 1));
      }, 8000); // Progress every 8 seconds

      try {
        const response = await api.analyzeLostLead(leadId, {});
        clearInterval(stepInterval);
        setLoadingStep(loadingSteps.length - 1); // Final step
        return response.data as LostLeadAnalysis;
      } catch (error) {
        clearInterval(stepInterval);
        throw error;
      }
    },
    {
      onSuccess: (data, variables) => {
        setInsights((prev) => ({ ...prev, [variables.leadId]: data }));
        setLoadingStep(0); // Reset
        toast.success('Analysis ready');
      },
      onError: (error: any) => {
        setLoadingStep(0); // Reset
        toast.error(error?.response?.data?.detail || 'Unable to analyse lost lead');
      },
    }
  );

  const saveMutation = useMutation(
    async ({ leadId, title, analysisData }: {
      leadId: number;
      title: string;
      analysisData: LostLeadAnalysis;
    }) => {
      const response = await api.post(`/lost-leads/${leadId}/save-analysis`, {
        lead_id: leadId,
        title,
        analysis_data: analysisData,
      });
      return response.data;
    },
    {
      onSuccess: () => {
        toast.success('Analysis saved and shared successfully');
        setShowSaveModal(false);
        setSaveTitle('');
        queryClient.invalidateQueries('shared-analyses');
      },
      onError: (error: any) => {
        toast.error(error?.response?.data?.detail || 'Failed to save analysis');
      },
    }
  );

  // Fetch shared analyses
  const { data: savedAnalyses = [], isLoading: loadingSaved, refetch: refetchSaved } = useQuery<SharedAnalysis[]>(
    'shared-analyses',
    async () => {
      const response = await api.get('/re-engage/analyses');
      return response.data;
    },
    {
      enabled: activeTab === 'saved',
      onError: (error: any) => {
        toast.error(error?.response?.data?.detail || 'Failed to load saved analyses');
      },
    }
  );

  // Delete analysis mutation
  const deleteMutation = useMutation(
    async (analysisId: string) => {
      await api.delete(`/re-engage/analyses/${analysisId}`);
    },
    {
      onSuccess: () => {
        toast.success('Analysis deleted successfully');
        queryClient.invalidateQueries('shared-analyses');
      },
      onError: (error: any) => {
        toast.error(error?.response?.data?.detail || 'Failed to delete analysis');
      },
    }
  );

  // Update analysis mutation
  const updateMutation = useMutation(
    async ({ analysisId, data }: { analysisId: string; data: any }) => {
      await api.put(`/re-engage/analyses/${analysisId}`, data);
    },
    {
      onSuccess: () => {
        toast.success('Analysis updated successfully');
        queryClient.invalidateQueries('shared-analyses');
        setEditingAnalysisId(null);
      },
      onError: (error: any) => {
        toast.error(error?.response?.data?.detail || 'Failed to update analysis');
      },
    }
  );

  const selectedAnalysis = selectedLeadId ? insights[selectedLeadId] : undefined;

  const keyFactors = useMemo(() => extractStringItems(selectedAnalysis?.analysis?.key_factors), [selectedAnalysis]);
  const talkingPoints = useMemo(
    () => extractStringItems(selectedAnalysis?.analysis?.follow_up_plan?.talking_points),
    [selectedAnalysis]
  );
  const proposedActions = useMemo(
    () => extractStringItems(selectedAnalysis?.analysis?.follow_up_plan?.proposed_actions),
    [selectedAnalysis]
  );
  const risks = useMemo(() => extractStringItems(selectedAnalysis?.analysis?.follow_up_plan?.risks), [selectedAnalysis]);
  const intelGaps = useMemo(() => extractStringItems(selectedAnalysis?.analysis?.intel_gaps), [selectedAnalysis]);

  const handleAnalyze = (leadId: number) => {
    setSelectedLeadId(leadId);

    // If analysis already exists for this lead, just switch to it
    if (insights[leadId]) {
      return;
    }

    // Otherwise, run new analysis (always includes engage emails)
    analyzeMutation.mutate({ leadId });
  };

  const formatCurrency = (value?: number) => {
    if (value === undefined || value === null) return '—';
    try {
      return new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD' }).format(value);
    } catch (error) {
      return `$${value}`;
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const handleGenerateDraft = async (savedItem: SharedAnalysis) => {
    setSelectedSavedItem(savedItem);
    setIsGeneratingDraft(true);
    setShowDraftModal(true);
    setDraftEmail('');

    try {
      const response = await api.generateLostLeadDraft({
        lead_data: savedItem.analysis_data.lead,
        analysis_data: savedItem.analysis_data
      });
      setDraftEmail(response.data.draft || '');
      toast.success('Draft generated successfully!');
    } catch (error) {
      console.error('Error generating draft:', error);
      toast.error('Failed to generate draft');
      setShowDraftModal(false);
    } finally {
      setIsGeneratingDraft(false);
    }
  };

  const renderAnalysisContent = (analysis: LostLeadAnalysis) => {
    const keyFactors = extractStringItems(analysis?.analysis?.key_factors);
    const talkingPoints = extractStringItems(analysis?.analysis?.follow_up_plan?.talking_points);
    const proposedActions = extractStringItems(analysis?.analysis?.follow_up_plan?.proposed_actions);
    const risks = extractStringItems(analysis?.analysis?.follow_up_plan?.risks);
    const intelGaps = extractStringItems(analysis?.analysis?.intel_gaps);

    return (
      <div className="space-y-6">
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="space-y-4 text-sm text-gray-700">
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Loss Summary</h3>
              <p className="mt-1 whitespace-pre-line text-gray-800">
                {analysis.analysis?.loss_summary || 'No summary produced.'}
              </p>
            </div>

            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Key Factors</h3>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {keyFactors.length > 0 ? (
                  keyFactors.map((factor, index) => <li key={index}>{factor}</li>)
                ) : (
                  <li>No contributing factors identified.</li>
                )}
              </ul>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Objective</h3>
                <p className="mt-1 text-gray-800">
                  {analysis.analysis?.follow_up_plan?.objective || 'No objective suggested.'}
                </p>
              </div>
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Timeline</h3>
                <p className="mt-1 text-gray-800">
                  {analysis.analysis?.follow_up_plan?.recommended_timeline || 'No timeline provided.'}
                </p>
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Talking Points</h3>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-gray-800">
                  {talkingPoints.length > 0 ? (
                    talkingPoints.map((point, index) => <li key={index}>{point}</li>)
                  ) : (
                    <li>No talking points generated.</li>
                  )}
                </ul>
              </div>
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Proposed Actions</h3>
                <ol className="mt-1 list-decimal space-y-1 pl-5 text-gray-800">
                  {proposedActions.length > 0 ? (
                    proposedActions.map((action, index) => <li key={index}>{action}</li>)
                  ) : (
                    <li>No proposed actions generated.</li>
                  )}
                </ol>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Risks to Monitor</h3>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-gray-800">
                {risks.length > 0 ? (
                  risks.map((risk, index) => (
                    <li key={index} className="flex items-start gap-2">
                      <ExclamationTriangleIcon className="mt-0.5 h-4 w-4 text-amber-500" />
                      <span>{risk}</span>
                    </li>
                  ))
                ) : (
                  <li>No risks documented.</li>
                )}
              </ul>
            </div>

            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Intelligence Gaps</h3>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-gray-800">
                {intelGaps.length > 0 ? (
                  intelGaps.map((gap, index) => <li key={index}>{gap}</li>)
                ) : (
                  <li>No information gaps flagged.</li>
                )}
              </ul>
            </div>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <h3 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
              <ClipboardDocumentListIcon className="h-4 w-4" /> Internal Notes
            </h3>
            <div className="mt-4 space-y-4 text-sm text-gray-700">
              {analysis.internal_notes.length === 0 && <p className="text-gray-500">No internal notes were available.</p>}
              {analysis.internal_notes.map((note, idx) => (
                <div key={idx} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      <UserCircleIcon className="h-4 w-4" />
                      {note.author || 'Unknown author'}
                    </span>
                    <span className="flex items-center gap-1">
                      <ClockIcon className="h-4 w-4" />
                      {note.formatted_date || 'Unknown date'}
                    </span>
                  </div>
                  <p className="mt-2 whitespace-pre-line text-gray-800">{note.body}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <h3 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
              <EnvelopeOpenIcon className="h-4 w-4" /> Customer Emails
            </h3>
            <div className="mt-4 space-y-4 text-sm text-gray-700">
              {analysis.emails.length === 0 && <p className="text-gray-500">No customer-facing emails were found.</p>}
              {analysis.emails.map((email, idx) => (
                <div key={idx} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      <UserCircleIcon className="h-4 w-4" />
                      {email.author || email.subject || 'External contact'}
                    </span>
                    <span className="flex items-center gap-1">
                      <ClockIcon className="h-4 w-4" />
                      {email.formatted_date || 'Unknown date'}
                    </span>
                  </div>
                  {email.subject && (
                    <p className="mt-1 text-xs font-medium text-gray-500">{email.subject}</p>
                  )}
                  <p className="mt-2 whitespace-pre-line text-gray-800">{email.body}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const handleGenerateReport = async () => {
    setIsGeneratingReport(true);
    setReportData(null);
    try {
      const response = await api.generateLostLeadsReport({
        limit: reportLimit,
        salesperson,
        type_filter: reportTypeFilter || undefined
      });
      setReportData(response.data.report);
      toast.success('Report generated successfully!');
    } catch (error) {
      console.error('Error generating report:', error);
      toast.error('Failed to generate report');
    } finally {
      setIsGeneratingReport(false);
    }
  };

  return (
    <div className="space-y-6 px-4 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.2em] text-primary-600">
            <SparklesIcon className="h-4 w-4" />
            Lost Lead Triage
          </div>
          <h1 className="mt-2 text-2xl font-semibold text-gray-900">Diagnose Lost Opportunities</h1>
          <p className="mt-2 max-w-3xl text-sm text-gray-600">
            Review recently lost opportunities, understand the context behind the loss, and generate a personalised plan
            to revive the conversation.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 shadow-sm">
            <label htmlFor="limit" className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Results
            </label>
            <input
              id="limit"
              type="number"
              min={1}
              max={50}
              value={limit}
              onChange={(event) => setLimit(Math.min(Math.max(1, Number(event.target.value) || 1), 50))}
              className="w-20 rounded-md border border-gray-300 px-2 py-1 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </div>
          <button
            type="button"
            onClick={() => lostLeadsQuery.refetch()}
            className="inline-flex items-center rounded-md border border-transparent bg-primary-600 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
          >
            <ArrowPathIcon className={`mr-2 h-4 w-4 ${lostLeadsQuery.isFetching ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </header>

      {/* Tab Switcher */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex gap-8">
          <button
            onClick={() => setActiveTab('analyze')}
            className={`whitespace-nowrap border-b-2 px-1 py-4 text-sm font-medium ${
              activeTab === 'analyze'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
            }`}
          >
            Analyze Lost Leads
          </button>
          <button
            onClick={() => setActiveTab('saved')}
            className={`whitespace-nowrap border-b-2 px-1 py-4 text-sm font-medium ${
              activeTab === 'saved'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
            }`}
          >
            <div className="flex items-center gap-2">
              <HeartIcon className="h-4 w-4" />
              Re-Engage ({savedAnalyses.length})
            </div>
          </button>
          <button
            onClick={() => setActiveTab('reports')}
            className={`whitespace-nowrap border-b-2 px-1 py-4 text-sm font-medium ${
              activeTab === 'reports'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
            }`}
          >
            <div className="flex items-center gap-2">
              <ChartBarIcon className="h-4 w-4" />
              Reports & Analytics
            </div>
          </button>
        </nav>
      </div>

      {/* Analyze Tab Content */}
      {activeTab === 'analyze' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <section className="lg:col-span-1 space-y-4">
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" />
              <input
                type="text"
                placeholder="Filter by salesperson"
                value={salesperson}
                onChange={(event) => setSalesperson(event.target.value)}
                className="w-full rounded-lg border border-gray-200 bg-white py-2 pl-10 pr-3 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
              />
            </div>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setTypeFilter('')}
                className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                  typeFilter === ''
                    ? 'border-primary-500 bg-primary-50 text-primary-700'
                    : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
                }`}
              >
                All
              </button>
              <button
                type="button"
                onClick={() => setTypeFilter('lead')}
                className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                  typeFilter === 'lead'
                    ? 'border-primary-500 bg-primary-50 text-primary-700'
                    : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
                }`}
              >
                Leads
              </button>
              <button
                type="button"
                onClick={() => setTypeFilter('opportunity')}
                className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                  typeFilter === 'opportunity'
                    ? 'border-primary-500 bg-primary-50 text-primary-700'
                    : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
                }`}
              >
                Opportunities
              </button>
            </div>

            <div className="space-y-3">
              {lostLeadsQuery.isLoading && (
                <div className="rounded-xl border border-dashed border-gray-300 bg-white/70 p-6 text-center text-sm text-gray-500">
                  Loading lost leads...
                </div>
              )}

              {!lostLeadsQuery.isLoading && leads.length === 0 && (
                <div className="rounded-xl border border-dashed border-gray-300 bg-white/70 p-6 text-center text-sm text-gray-500">
                  No lost opportunities found with the current filters.
                </div>
              )}

              {leads.map((lead) => {
                const isSelected = selectedLeadId === lead.id;
                const pending = analyzeMutation.isLoading && analyzeMutation.variables?.leadId === lead.id;
                const hasAnalysis = !!insights[lead.id];
                return (
                  <button
                    key={lead.id}
                    type="button"
                    onClick={() => handleAnalyze(lead.id)}
                    className={`w-full rounded-xl border p-4 text-left shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                      isSelected ? 'border-primary-400 bg-primary-50' : 'border-gray-200 bg-white hover:border-primary-200'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="text-base font-semibold text-gray-900">{lead.name}</h3>
                          {lead.record_type && (
                            <span
                              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                                lead.record_type === 'opportunity'
                                  ? 'bg-blue-100 text-blue-700'
                                  : 'bg-gray-100 text-gray-700'
                              }`}
                            >
                              {lead.record_type === 'opportunity' ? 'Opportunity' : 'Lead'}
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-600">{lead.partner_name || 'Unknown account'}</p>
                        {lead.lost_reason && (
                          <p className="mt-1 text-xs text-gray-500">Reason: {lead.lost_reason}</p>
                        )}
                      </div>
                      <div className="flex flex-col items-end gap-1 text-xs text-gray-500">
                        <span>{lead.stage || 'Lost stage'}</span>
                        {lead.last_update && <span>Updated {new Date(lead.last_update).toLocaleDateString()}</span>}
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-gray-500">
                      {lead.salesperson && (
                        <span className="inline-flex items-center gap-1">
                          <UserCircleIcon className="h-4 w-4" />
                          {lead.salesperson}
                        </span>
                      )}
                      {typeof lead.expected_revenue === 'number' && (
                        <span className="inline-flex items-center gap-1">
                          <BanknotesIcon className="h-4 w-4" />
                          {formatCurrency(lead.expected_revenue)}
                        </span>
                      )}
                      {lead.probability !== undefined && (
                        <span>{lead.probability}% probability</span>
                      )}
                    </div>
                    <div className="mt-3 text-right">
                      <span
                        className={`inline-flex items-center gap-2 rounded-md px-3 py-1 text-sm font-medium ${
                          pending
                            ? 'bg-primary-600 text-white'
                            : isSelected
                            ? 'bg-primary-100 text-primary-700'
                            : 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {pending ? (
                          <ArrowPathIcon className="h-4 w-4 animate-spin" />
                        ) : (
                          <SparklesIcon className="h-4 w-4" />
                        )}
                        {pending ? loadingSteps[loadingStep] : hasAnalysis ? (isSelected ? 'View analysis' : 'Analyzed') : 'Analyse lead'}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="lg:col-span-2">
            {!selectedAnalysis && (
              <div className="flex h-full flex-col items-center justify-center rounded-2xl border border-dashed border-gray-300 bg-white/70 p-10 text-center text-gray-500">
                <ClipboardDocumentListIcon className="h-10 w-10 text-gray-400" />
                <p className="mt-3 text-base font-medium text-gray-700">Select a lost opportunity to generate analysis.</p>
                <p className="mt-1 text-sm text-gray-500">We will pull all relevant internal notes and emails, then craft a tailored comeback plan.</p>
              </div>
            )}

            {selectedAnalysis && (
              <div className="space-y-6">
                <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <h2 className="text-xl font-semibold text-gray-900">{selectedAnalysis.lead?.name}</h2>
                      <p className="text-sm text-gray-600">{selectedAnalysis.lead?.partner_name || 'Unknown account'}</p>
                    </div>
                    <div className="flex flex-col gap-2 items-end">
                      <div className="text-sm text-gray-500">
                        <p>Stage: {selectedAnalysis.lead?.stage_id || 'Lost'}</p>
                        <p>Salesperson: {selectedAnalysis.lead?.user_id || 'Unassigned'}</p>
                      </div>
                      <button
                        onClick={() => setShowSaveModal(true)}
                        className="inline-flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
                      >
                        <HeartIcon className="h-4 w-4" />
                        Save & Share
                      </button>
                    </div>
                  </div>
                </div>

                {renderAnalysisContent(selectedAnalysis)}
              </div>
            )}
          </section>
        </div>
      )}

      {/* Saved Tab Content */}
      {activeTab === 'saved' && (
        <div className="space-y-6">
          {loadingSaved ? (
            <div className="flex h-96 items-center justify-center">
              <div className="flex items-center gap-3 text-gray-600">
                <ArrowPathIcon className="h-6 w-6 animate-spin" />
                <span>Loading saved analyses...</span>
              </div>
            </div>
          ) : savedAnalyses.length === 0 ? (
            <div className="rounded-lg border-2 border-dashed border-gray-300 bg-white p-12 text-center">
              <HeartIcon className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">No saved analyses</h3>
              <p className="mt-1 text-sm text-gray-500">
                When you save a lost lead analysis, it will appear here for the whole team to review.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {savedAnalyses.map((savedItem) => (
                <div
                  key={savedItem.id}
                  className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm transition-shadow hover:shadow-md"
                >
                  {/* Header */}
                  <div
                    className="border-b border-gray-200 bg-gray-50 px-6 py-4 cursor-pointer hover:bg-gray-100 transition-colors"
                    onClick={() => setExpandedSavedId(expandedSavedId === savedItem.id ? null : savedItem.id)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h3 className="text-lg font-semibold text-gray-900">
                          {savedItem.title || `Analysis #${savedItem.id.slice(0, 8)}`}
                        </h3>
                        <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-gray-600">
                          {savedItem.analysis_data.lead?.name && (
                            <div className="flex items-center gap-1.5">
                              <UserCircleIcon className="h-4 w-4" />
                              <span>{savedItem.analysis_data.lead.name}</span>
                            </div>
                          )}
                          {savedItem.analysis_data.lead?.partner_name && (
                            <div className="flex items-center gap-1.5">
                              <BuildingOfficeIcon className="h-4 w-4" />
                              <span>{savedItem.analysis_data.lead.partner_name}</span>
                            </div>
                          )}
                          <div className="flex items-center gap-1.5">
                            <ClockIcon className="h-4 w-4" />
                            <span>{formatDate(savedItem.created_at)}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => handleGenerateDraft(savedItem)}
                          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 flex items-center gap-2"
                        >
                          <DocumentTextIcon className="h-4 w-4" />
                          Generate Draft
                        </button>
                        <button
                          onClick={() => {
                            if (editingAnalysisId === savedItem.id) {
                              // Cancel editing
                              setEditingAnalysisId(null);
                              setEditingInPlace(false);
                              setEditedTitle('');
                            } else {
                              // Start editing
                              setEditingAnalysisId(String(savedItem.id));
                              setEditingInPlace(true);
                              setEditedTitle(savedItem.title || '');
                              setExpandedSavedId(savedItem.id);
                            }
                          }}
                          className={`rounded-lg border px-4 py-2 text-sm font-medium ${
                            editingAnalysisId === savedItem.id
                              ? 'border-orange-300 bg-orange-50 text-orange-700 hover:bg-orange-100'
                              : 'border-primary-300 bg-white text-primary-700 hover:bg-primary-50'
                          }`}
                        >
                          <PencilIcon className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => {
                            if (window.confirm('Are you sure you want to delete this analysis?')) {
                              deleteMutation.mutate(savedItem.id);
                            }
                          }}
                          disabled={deleteMutation.isLoading}
                          className="rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                        >
                          <TrashIcon className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Expanded Content */}
                  {expandedSavedId === savedItem.id && (
                    <div className="px-6 py-6">
                      {editingAnalysisId === savedItem.id && editingInPlace ? (
                        <div className="space-y-4">
                          {/* Edit Title */}
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                              Title
                            </label>
                            <input
                              type="text"
                              value={editedTitle}
                              onChange={(e) => setEditedTitle(e.target.value)}
                              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                              placeholder="Analysis title"
                            />
                          </div>

                          {/* Read-only Analysis Content */}
                          <div className="border-t pt-4">
                            <p className="text-sm text-gray-500 mb-3">
                              Analysis content (read-only):
                            </p>
                            {renderAnalysisContent(savedItem.analysis_data)}
                          </div>

                          {/* Save/Cancel Buttons */}
                          <div className="flex gap-3 pt-4 border-t">
                            <button
                              onClick={() => {
                                setEditingAnalysisId(null);
                                setEditingInPlace(false);
                                setEditedTitle('');
                              }}
                              className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                            >
                              Cancel
                            </button>
                            <button
                              onClick={() => {
                                updateMutation.mutate({
                                  analysisId: savedItem.id,
                                  data: {
                                    lead_id: savedItem.lead_id,
                                    title: editedTitle.trim() || savedItem.title,
                                    analysis_data: savedItem.analysis_data,
                                  }
                                });
                                setEditingAnalysisId(null);
                                setEditingInPlace(false);
                                setEditedTitle('');
                              }}
                              disabled={updateMutation.isLoading}
                              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center gap-2"
                            >
                              {updateMutation.isLoading ? (
                                <>
                                  <ArrowPathIcon className="h-4 w-4 animate-spin" />
                                  Saving...
                                </>
                              ) : (
                                'Save Changes'
                              )}
                            </button>
                          </div>
                        </div>
                      ) : (
                        renderAnalysisContent(savedItem.analysis_data)
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Save Modal */}
      {showSaveModal && selectedAnalysis && selectedLeadId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <h3 className="text-lg font-semibold text-gray-900">
              {editingAnalysisId ? 'Update Analysis' : 'Save & Share Analysis'}
            </h3>
            <p className="mt-2 text-sm text-gray-600">
              {editingAnalysisId
                ? 'Update the title for this analysis.'
                : 'Give this analysis a title. It will be visible to all team members in the Saved tab.'}
            </p>
            <div className="mt-4">
              <label htmlFor="save-title" className="block text-sm font-medium text-gray-700">
                Title
              </label>
              <input
                id="save-title"
                type="text"
                value={saveTitle}
                onChange={(e) => setSaveTitle(e.target.value)}
                placeholder={`${selectedAnalysis.lead?.name || 'Lost Lead'} | ${selectedAnalysis.lead?.partner_name || 'Analysis'}`}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
              />
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowSaveModal(false);
                  setSaveTitle('');
                }}
                className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  const title = saveTitle.trim() || `${selectedAnalysis.lead?.name || 'Lost Lead'} | ${selectedAnalysis.lead?.partner_name || 'Analysis'}`;

                  if (editingAnalysisId) {
                    // Update existing analysis
                    updateMutation.mutate({
                      analysisId: editingAnalysisId,
                      data: {
                        lead_id: selectedLeadId,
                        title,
                        analysis_data: selectedAnalysis,
                      }
                    });
                  } else {
                    // Save new analysis
                    saveMutation.mutate({
                      leadId: selectedLeadId,
                      title,
                      analysisData: selectedAnalysis,
                    });
                  }

                  setShowSaveModal(false);
                  setSaveTitle('');
                }}
                disabled={saveMutation.isLoading || updateMutation.isLoading}
                className="inline-flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
              >
                {(saveMutation.isLoading || updateMutation.isLoading) ? (
                  <>
                    <ArrowPathIcon className="h-4 w-4 animate-spin" />
                    {editingAnalysisId ? 'Updating...' : 'Saving...'}
                  </>
                ) : (
                  <>
                    <HeartIcon className="h-4 w-4" />
                    {editingAnalysisId ? 'Update' : 'Save & Share'}
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Draft Email Modal */}
      {showDraftModal && selectedSavedItem && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-3xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Re-Engagement Email Draft</h3>
                <p className="text-sm text-gray-600 mt-1">
                  For: {selectedSavedItem.analysis_data.lead?.partner_name || selectedSavedItem.analysis_data.lead?.contact_name || selectedSavedItem.analysis_data.lead?.name}
                </p>
              </div>
              <button
                onClick={() => {
                  setShowDraftModal(false);
                  setDraftEmail('');
                  setSelectedSavedItem(null);
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <XCircleIcon className="w-6 h-6" />
              </button>
            </div>

            {/* Loading State */}
            {isGeneratingDraft && (
              <div className="text-center py-12">
                <ArrowPathIcon className="w-12 h-12 text-blue-500 animate-spin mx-auto mb-4" />
                <p className="text-gray-600">Generating re-engagement email draft...</p>
              </div>
            )}

            {/* Draft Editor */}
            {!isGeneratingDraft && (
              <>
                {/* Subject Field */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Subject
                  </label>
                  <input
                    type="text"
                    value={draftSubject}
                    onChange={(e) => setDraftSubject(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    placeholder="Email subject..."
                  />
                </div>

                {/* CC Field */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    CC (comma-separated)
                  </label>
                  <input
                    type="text"
                    value={draftCc}
                    onChange={(e) => setDraftCc(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    placeholder="email1@example.com, email2@example.com"
                  />
                  <p className="mt-1 text-xs text-gray-500">engage@prezlab.com is included by default</p>
                </div>

                {/* Email Body */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Email Body (editable)
                  </label>
                  <textarea
                    value={draftEmail}
                    onChange={(e) => setDraftEmail(e.target.value)}
                    rows={10}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md font-sans text-sm"
                    placeholder="Draft email will appear here..."
                  />
                </div>

                {/* Action Buttons */}
                <div className="flex gap-3">
                  <button
                    onClick={() => {
                      setShowDraftModal(false);
                      setDraftEmail('');
                      setSelectedSavedItem(null);
                    }}
                    className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                  >
                    Cancel
                  </button>

                  <button
                    onClick={async () => {
                      if (!selectedSavedItem?.lead_id) {
                        toast.error('No lead selected');
                        return;
                      }

                      setIsSendingEmail(true);
                      try {
                        const token = localStorage.getItem('prezlab_auth_token') || sessionStorage.getItem('prezlab_auth_token');

                        // Parse CC emails
                        const ccEmails = draftCc.split(',').map(e => e.trim()).filter(e => e);

                        const response = await fetch(`${process.env.REACT_APP_API_BASE || 'http://localhost:8000'}/lost-leads/send-email`, {
                          method: 'POST',
                          headers: {
                            'Content-Type': 'application/json',
                            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                          },
                          body: JSON.stringify({
                            lead_id: selectedSavedItem.lead_id,
                            subject: draftSubject,
                            body: draftEmail,
                            cc: ccEmails
                          })
                        });

                        if (!response.ok) {
                          const error = await response.json();
                          throw new Error(error.detail || 'Failed to send email');
                        }

                        toast.success('Email sent successfully!');
                        setShowDraftModal(false);
                        setDraftEmail('');
                        setDraftSubject('');
                        setDraftCc('engage@prezlab.com');
                      } catch (error: any) {
                        console.error('Send email error:', error);
                        toast.error(error.message || 'Failed to send email');
                      } finally {
                        setIsSendingEmail(false);
                      }
                    }}
                    disabled={!draftEmail.trim() || !draftSubject.trim() || isSendingEmail}
                    className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {isSendingEmail ? (
                      <>
                        <ArrowPathIcon className="w-4 h-4 animate-spin" />
                        Sending...
                      </>
                    ) : (
                      'Send Email'
                    )}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Reports Tab Content */}
      {activeTab === 'reports' && (
        <div className="space-y-6">
          {/* Report Generation Controls */}
          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Generate Lost Leads Report</h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <label htmlFor="reportLimit" className="block text-sm font-medium text-gray-700 mb-1">
                  Number of Leads
                </label>
                <input
                  id="reportLimit"
                  type="number"
                  min={1}
                  max={200}
                  value={reportLimit}
                  onChange={(e) => setReportLimit(Math.min(Math.max(1, Number(e.target.value) || 1), 200))}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                />
              </div>

              <div>
                <label htmlFor="reportTypeFilter" className="block text-sm font-medium text-gray-700 mb-1">
                  Type Filter
                </label>
                <select
                  id="reportTypeFilter"
                  value={reportTypeFilter}
                  onChange={(e) => setReportTypeFilter(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                >
                  <option value="">All (Leads & Opportunities)</option>
                  <option value="lead">Leads Only</option>
                  <option value="opportunity">Opportunities Only</option>
                </select>
              </div>

              <div className="flex items-end">
                <button
                  onClick={handleGenerateReport}
                  disabled={isGeneratingReport}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isGeneratingReport ? (
                    <>
                      <ArrowPathIcon className="h-4 w-4 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <ChartBarIcon className="h-4 w-4" />
                      Generate Report
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Report Results */}
          {reportData && (
            <div className="space-y-6">
              {/* Summary Statistics */}
              <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Summary Statistics</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="bg-red-50 rounded-lg p-4">
                    <div className="text-sm font-medium text-red-600">Total Missed Value</div>
                    <div className="text-2xl font-bold text-red-900 mt-1">
                      AED {reportData.summary.total_missed_value.toLocaleString()}
                    </div>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-4">
                    <div className="text-sm font-medium text-blue-600">Average Deal Size</div>
                    <div className="text-2xl font-bold text-blue-900 mt-1">
                      AED {reportData.summary.average_deal_value.toLocaleString()}
                    </div>
                  </div>
                  <div className="bg-purple-50 rounded-lg p-4">
                    <div className="text-sm font-medium text-purple-600">Total Lost Leads</div>
                    <div className="text-2xl font-bold text-purple-900 mt-1">
                      {reportData.summary.total_count}
                    </div>
                  </div>
                  <div className="bg-green-50 rounded-lg p-4">
                    <div className="text-sm font-medium text-green-600">Leads vs Opportunities</div>
                    <div className="text-sm font-bold text-green-900 mt-1">
                      {reportData.summary.leads_count} / {reportData.summary.opportunities_count}
                    </div>
                  </div>
                </div>
              </div>

              {/* Lost Reasons Analysis */}
              <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Lost Reasons Analysis</h3>
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-3">By Frequency</h4>
                    <div className="space-y-2">
                      {reportData.reasons_analysis.by_frequency.slice(0, 5).map((reason: any, idx: number) => (
                        <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                          <span className="text-sm font-medium text-gray-900">{reason.reason}</span>
                          <span className="text-sm text-gray-600">{reason.count} leads ({reason.percentage}%)</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-3">By Value</h4>
                    <div className="space-y-2">
                      {reportData.reasons_analysis.by_value.slice(0, 5).map((reason: any, idx: number) => (
                        <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                          <span className="text-sm font-medium text-gray-900">{reason.reason}</span>
                          <span className="text-sm text-gray-600">AED {reason.total_value.toLocaleString()} ({reason.percentage}%)</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-3">By Stage</h4>
                    <div className="space-y-2">
                      {reportData.stage_analysis?.slice(0, 5).map((stage: any, idx: number) => (
                        <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                          <span className="text-sm font-medium text-gray-900">{stage.stage}</span>
                          <span className="text-sm text-gray-600">{stage.count} leads ({stage.percentage}%)</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Top Re-contact Opportunities */}
              <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Top 10 Re-contact Opportunities</h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Score</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Company</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Value</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Stage</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reason</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {reportData.top_opportunities.map((opp: any, idx: number) => (
                        <tr key={idx} className="hover:bg-gray-50">
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                              opp.reconnect_score > 70 ? 'bg-green-100 text-green-800' :
                              opp.reconnect_score > 50 ? 'bg-yellow-100 text-yellow-800' :
                              'bg-gray-100 text-gray-800'
                            }`}>
                              {opp.reconnect_score}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">{opp.name}</td>
                          <td className="px-4 py-3 text-sm text-gray-600">{opp.partner_name || '-'}</td>
                          <td className="px-4 py-3 text-sm text-gray-900">AED {opp.expected_revenue.toLocaleString()}</td>
                          <td className="px-4 py-3 text-sm text-gray-600">{opp.stage_name || '-'}</td>
                          <td className="px-4 py-3 text-sm text-gray-600">{opp.lost_reason}</td>
                          <td className="px-4 py-3 text-sm">
                            <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                              opp.type === 'opportunity' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'
                            }`}>
                              {opp.type}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default LostLeadsPage;
