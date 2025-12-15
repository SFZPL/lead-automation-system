import React, { useMemo, useState, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from 'react-query';
import toast from 'react-hot-toast';
import html2pdf from 'html2pdf.js';
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
  PaperAirplaneIcon,
  DocumentArrowDownIcon,
} from '@heroicons/react/24/outline';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
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

  // Persist activeTab to localStorage
  const [activeTab, setActiveTab] = useState<'analyze' | 'saved' | 'reports'>(() => {
    try {
      const saved = localStorage.getItem('lostLeads_activeTab');
      return (saved as 'analyze' | 'saved' | 'reports') || 'analyze';
    } catch {
      return 'analyze';
    }
  });

  // Persist expandedSavedId and editingAnalysisId to localStorage
  const [expandedSavedId, setExpandedSavedId] = useState<string | null>(() => {
    try {
      const saved = localStorage.getItem('lostLeads_expandedSavedId');
      return saved ? saved : null;
    } catch {
      return null;
    }
  });

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
  const [reportDateFrom, setReportDateFrom] = useState<string>('');
  const [reportDateTo, setReportDateTo] = useState<string>('');
  const [includePatternAnalysis, setIncludePatternAnalysis] = useState<boolean>(false);
  const [isGeneratingReport, setIsGeneratingReport] = useState<boolean>(false);
  const [isSendingToTeams, setIsSendingToTeams] = useState<boolean>(false);

  // Persist report data to sessionStorage
  const [reportData, setReportData] = useState<any>(() => {
    try {
      const saved = sessionStorage.getItem('lostLeads_reportData');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

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

  // Persist activeTab to localStorage
  React.useEffect(() => {
    localStorage.setItem('lostLeads_activeTab', activeTab);
  }, [activeTab]);

  // Persist expandedSavedId to localStorage
  React.useEffect(() => {
    if (expandedSavedId) {
      localStorage.setItem('lostLeads_expandedSavedId', expandedSavedId);
    } else {
      localStorage.removeItem('lostLeads_expandedSavedId');
    }
  }, [expandedSavedId]);

  // Persist report data to sessionStorage
  React.useEffect(() => {
    if (reportData) {
      sessionStorage.setItem('lostLeads_reportData', JSON.stringify(reportData));
    } else {
      sessionStorage.removeItem('lostLeads_reportData');
    }
  }, [reportData]);

  // Ref for PDF export
  const reportRef = useRef<HTMLDivElement>(null);
  const [isExportingPdf, setIsExportingPdf] = useState<boolean>(false);

  // Export report to PDF
  const exportToPdf = async () => {
    if (!reportRef.current || !reportData) {
      toast.error('No report to export');
      return;
    }

    setIsExportingPdf(true);
    toast.loading('Generating PDF...', { id: 'pdf-export' });

    try {
      const element = reportRef.current;
      const currentDate = new Date().toISOString().split('T')[0];
      const dateRange = reportDateFrom && reportDateTo
        ? `${reportDateFrom}-to-${reportDateTo}`
        : currentDate;

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const opt: any = {
        margin: [10, 10, 10, 10],
        filename: `lost-leads-report-${dateRange}.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: {
          scale: 2,
          useCORS: true,
          logging: false,
          letterRendering: true
        },
        jsPDF: {
          unit: 'mm',
          format: 'a4',
          orientation: 'portrait'
        },
        pagebreak: { mode: ['avoid-all', 'css', 'legacy'] }
      };

      await html2pdf().set(opt).from(element).save();
      toast.success('PDF exported successfully', { id: 'pdf-export' });
    } catch (error) {
      console.error('PDF export error:', error);
      toast.error('Failed to export PDF', { id: 'pdf-export' });
    } finally {
      setIsExportingPdf(false);
    }
  };

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
      return new Intl.NumberFormat(undefined, { style: 'currency', currency: 'AED' }).format(value);
    } catch (error) {
      return `AED ${value}`;
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
        type_filter: reportTypeFilter || undefined,
        date_from: reportDateFrom || undefined,
        date_to: reportDateTo || undefined,
        include_pattern_analysis: includePatternAnalysis
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

  const handleSendToTeams = async () => {
    if (!reportData) {
      toast.error('No report to send');
      return;
    }

    setIsSendingToTeams(true);
    try {
      await api.post('/lost-leads/send-to-teams', {
        report_data: reportData,
        date_from: reportDateFrom || undefined,
        date_to: reportDateTo || undefined
      });
      toast.success('Report sent to Teams successfully!');
    } catch (error: any) {
      console.error('Error sending to Teams:', error);
      toast.error(error?.response?.data?.detail || 'Failed to send report to Teams');
    } finally {
      setIsSendingToTeams(false);
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

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-4">
              <div>
                <label htmlFor="reportLimit" className="block text-sm font-medium text-gray-700 mb-1">
                  Number of Leads
                </label>
                <input
                  id="reportLimit"
                  type="number"
                  min={1}
                  max={1000}
                  value={reportLimit}
                  onChange={(e) => setReportLimit(Math.min(Math.max(1, Number(e.target.value) || 1), 1000))}
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

              <div>
                <label htmlFor="reportDateFrom" className="block text-sm font-medium text-gray-700 mb-1">
                  From Date (Lost)
                </label>
                <input
                  id="reportDateFrom"
                  type="date"
                  value={reportDateFrom}
                  onChange={(e) => setReportDateFrom(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                />
              </div>

              <div>
                <label htmlFor="reportDateTo" className="block text-sm font-medium text-gray-700 mb-1">
                  To Date (Lost)
                </label>
                <input
                  id="reportDateTo"
                  type="date"
                  value={reportDateTo}
                  onChange={(e) => setReportDateTo(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                />
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

            {/* AI Analysis Option */}
            <div className="mt-4 rounded-lg border-2 border-primary-200 bg-gradient-to-r from-primary-50 to-purple-50 p-4">
              <div className="flex items-start gap-3">
                <input
                  id="includePatternAnalysis"
                  type="checkbox"
                  checked={includePatternAnalysis}
                  onChange={(e) => setIncludePatternAnalysis(e.target.checked)}
                  className="mt-1 h-5 w-5 rounded border-primary-300 text-primary-600 focus:ring-2 focus:ring-primary-500"
                />
                <div className="flex-1">
                  <label htmlFor="includePatternAnalysis" className="flex items-center gap-2 text-base font-semibold text-gray-900 cursor-pointer">
                    <SparklesIcon className="h-5 w-5 text-primary-600" />
                    Integrate Full AI Analysis
                  </label>
                  <p className="mt-1 text-sm text-gray-600">
                    Powered by GPT-5: Lost reason clustering, customer profiles, stage analysis, deal size correlation, response time impact & re-engagement recommendations
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Report Results */}
          {reportData && (
            <div className="space-y-6">
              {/* Report Header with Export/Send buttons */}
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-gray-900">Lost Leads Report</h2>
                <div className="flex items-center gap-3">
                  <button
                    onClick={exportToPdf}
                    disabled={isExportingPdf}
                    className="inline-flex items-center gap-2 rounded-lg bg-gray-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isExportingPdf ? (
                      <>
                        <ArrowPathIcon className="h-4 w-4 animate-spin" />
                        Exporting...
                      </>
                    ) : (
                      <>
                        <DocumentArrowDownIcon className="h-4 w-4" />
                        Export PDF
                      </>
                    )}
                  </button>
                  <button
                    onClick={handleSendToTeams}
                    disabled={isSendingToTeams}
                    className="inline-flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isSendingToTeams ? (
                      <>
                        <ArrowPathIcon className="h-4 w-4 animate-spin" />
                        Sending...
                      </>
                    ) : (
                      <>
                        <PaperAirplaneIcon className="h-4 w-4" />
                        Send to Teams
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* PDF Export Container */}
              <div ref={reportRef} className="pdf-export-content">

              {/* Pipeline Performance (Funnel Metrics with MoM Comparison) */}
              {reportData.funnel_metrics && (
                <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">
                    Pipeline Performance
                    <span className="text-sm font-normal text-gray-500 ml-2">
                      ({reportData.funnel_metrics.current_period?.label} vs {reportData.funnel_metrics.previous_period?.label})
                    </span>
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                    {/* Leads In */}
                    <div className="bg-blue-50 rounded-lg p-4">
                      <div className="text-sm font-medium text-blue-600">Leads In</div>
                      <div className="text-2xl font-bold text-blue-900 mt-1">
                        {reportData.funnel_metrics.current_period?.leads_in || 0}
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        vs {reportData.funnel_metrics.previous_period?.leads_in || 0} prev
                        {reportData.funnel_metrics.changes?.leads_in !== null && (
                          <span className={`ml-1 font-medium ${reportData.funnel_metrics.changes.leads_in >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            ({reportData.funnel_metrics.changes.leads_in >= 0 ? '+' : ''}{reportData.funnel_metrics.changes.leads_in}%)
                          </span>
                        )}
                      </div>
                    </div>
                    {/* Qualified */}
                    <div className="bg-indigo-50 rounded-lg p-4">
                      <div className="text-sm font-medium text-indigo-600">Qualified (Opportunities)</div>
                      <div className="text-2xl font-bold text-indigo-900 mt-1">
                        {reportData.funnel_metrics.current_period?.qualified || 0}
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        vs {reportData.funnel_metrics.previous_period?.qualified || 0} prev
                        {reportData.funnel_metrics.changes?.qualified !== null && (
                          <span className={`ml-1 font-medium ${reportData.funnel_metrics.changes.qualified >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            ({reportData.funnel_metrics.changes.qualified >= 0 ? '+' : ''}{reportData.funnel_metrics.changes.qualified}%)
                          </span>
                        )}
                      </div>
                    </div>
                    {/* Won */}
                    <div className="bg-green-50 rounded-lg p-4">
                      <div className="text-sm font-medium text-green-600">Won</div>
                      <div className="text-2xl font-bold text-green-900 mt-1">
                        {reportData.funnel_metrics.current_period?.won_count || 0}
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        vs {reportData.funnel_metrics.previous_period?.won_count || 0} prev
                        {reportData.funnel_metrics.changes?.won_count !== null && (
                          <span className={`ml-1 font-medium ${reportData.funnel_metrics.changes.won_count >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            ({reportData.funnel_metrics.changes.won_count >= 0 ? '+' : ''}{reportData.funnel_metrics.changes.won_count}%)
                          </span>
                        )}
                      </div>
                    </div>
                    {/* Value Won */}
                    <div className="bg-emerald-50 rounded-lg p-4">
                      <div className="text-sm font-medium text-emerald-600">Value Won</div>
                      <div className="text-2xl font-bold text-emerald-900 mt-1">
                        AED {(reportData.funnel_metrics.current_period?.won_value || 0).toLocaleString()}
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        vs AED {(reportData.funnel_metrics.previous_period?.won_value || 0).toLocaleString()} prev
                        {reportData.funnel_metrics.changes?.won_value !== null && (
                          <span className={`ml-1 font-medium ${reportData.funnel_metrics.changes.won_value >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            ({reportData.funnel_metrics.changes.won_value >= 0 ? '+' : ''}{reportData.funnel_metrics.changes.won_value}%)
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  {/* Conversion Rates */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-gray-200">
                    <div className="text-center">
                      <div className="text-sm text-gray-500">Lead → Qualified Rate</div>
                      <div className="text-xl font-bold text-gray-900">
                        {reportData.funnel_metrics.current_period?.lead_to_qualified_rate || 0}%
                      </div>
                      {reportData.funnel_metrics.changes?.lead_to_qualified_rate !== null && (
                        <div className={`text-xs ${reportData.funnel_metrics.changes.lead_to_qualified_rate >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {reportData.funnel_metrics.changes.lead_to_qualified_rate >= 0 ? '↑' : '↓'} {Math.abs(reportData.funnel_metrics.changes.lead_to_qualified_rate)}% vs prev
                        </div>
                      )}
                    </div>
                    <div className="text-center">
                      <div className="text-sm text-gray-500">Qualified → Won Rate</div>
                      <div className="text-xl font-bold text-gray-900">
                        {reportData.funnel_metrics.current_period?.qualified_to_won_rate || 0}%
                      </div>
                      {reportData.funnel_metrics.changes?.qualified_to_won_rate !== null && (
                        <div className={`text-xs ${reportData.funnel_metrics.changes.qualified_to_won_rate >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {reportData.funnel_metrics.changes.qualified_to_won_rate >= 0 ? '↑' : '↓'} {Math.abs(reportData.funnel_metrics.changes.qualified_to_won_rate)}% vs prev
                        </div>
                      )}
                    </div>
                    <div className="text-center">
                      <div className="text-sm text-gray-500">Overall Win Rate</div>
                      <div className="text-xl font-bold text-gray-900">
                        {reportData.funnel_metrics.current_period?.overall_win_rate || 0}%
                      </div>
                      {reportData.funnel_metrics.changes?.overall_win_rate !== null && (
                        <div className={`text-xs ${reportData.funnel_metrics.changes.overall_win_rate >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {reportData.funnel_metrics.changes.overall_win_rate >= 0 ? '↑' : '↓'} {Math.abs(reportData.funnel_metrics.changes.overall_win_rate)}% vs prev
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Summary Statistics */}
              <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Summary Statistics</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="bg-red-50 rounded-lg p-4">
                    <div className="text-sm font-medium text-red-600">Total Quotation Value Sent</div>
                    <div className="text-2xl font-bold text-red-900 mt-1">
                      AED {reportData.summary.total_missed_value.toLocaleString()}
                    </div>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-4">
                    <div className="text-sm font-medium text-blue-600">Average Quotation Value</div>
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

              {/* Monthly Trends Chart */}
              {reportData.monthly_trends && reportData.monthly_trends.length > 0 && (
                <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Month-by-Month Trends</h3>
                  <div className="h-96">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={reportData.monthly_trends} margin={{ top: 20, right: 30, left: 20, bottom: 80 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                          dataKey="month_display"
                          tick={{ fontSize: 12 }}
                          angle={-45}
                          textAnchor="end"
                          height={100}
                        />
                        <YAxis
                          yAxisId="left"
                          tick={{ fontSize: 12 }}
                          label={{ value: 'Count', angle: -90, position: 'insideLeft' }}
                        />
                        <YAxis
                          yAxisId="right"
                          orientation="right"
                          tick={{ fontSize: 12 }}
                          label={{ value: 'Value (AED)', angle: 90, position: 'insideRight' }}
                        />
                        <Tooltip
                          formatter={(value: any, name: string) => {
                            if (name === 'Total Value') {
                              return [`AED ${Number(value).toLocaleString()}`, name];
                            }
                            return [value, name];
                          }}
                        />
                        <Legend />
                        <Line yAxisId="left" type="monotone" dataKey="count" stroke="#8b5cf6" strokeWidth={3} name="Total Lost" dot={{ r: 5 }} />
                        <Line yAxisId="left" type="monotone" dataKey="leads" stroke="#3b82f6" strokeWidth={2} name="Leads" dot={{ r: 4 }} />
                        <Line yAxisId="left" type="monotone" dataKey="opportunities" stroke="#10b981" strokeWidth={2} name="Opportunities" dot={{ r: 4 }} />
                        <Line yAxisId="right" type="monotone" dataKey="total_value" stroke="#ef4444" strokeWidth={3} name="Total Value" dot={{ r: 5 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

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
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Why Re-contact?</th>
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
                          <td className="px-4 py-3 text-sm text-gray-600 max-w-xs">
                            <span className="text-xs italic text-gray-500">
                              {opp.reconnect_reason || 'Worth re-evaluating'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Full List of Lost Leads */}
              {reportData.all_lost_leads && reportData.all_lost_leads.length > 0 && (
                <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">
                    All Lost Leads ({reportData.all_lost_leads.length})
                  </h3>
                  <div className="overflow-x-auto max-h-96 overflow-y-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50 sticky top-0">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Company</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Value</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Stage</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reason</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Salesperson</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Lost Date</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {reportData.all_lost_leads.map((lead: any, idx: number) => (
                          <tr key={idx} className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">{lead.name}</td>
                            <td className="px-4 py-3 text-sm text-gray-600">{lead.partner_name || '-'}</td>
                            <td className="px-4 py-3 text-sm text-gray-900">
                              {lead.expected_revenue ? `AED ${lead.expected_revenue.toLocaleString()}` : '-'}
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              {lead.stage_id ? (Array.isArray(lead.stage_id) ? lead.stage_id[1] : lead.stage_id) : '-'}
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              {lead.lost_reason_id ? (Array.isArray(lead.lost_reason_id) ? lead.lost_reason_id[1] : lead.lost_reason_id) : '-'}
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              {lead.user_id ? (Array.isArray(lead.user_id) ? lead.user_id[1] : lead.user_id) : '-'}
                            </td>
                            <td className="px-4 py-3 text-sm">
                              <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                                lead.type === 'opportunity' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'
                              }`}>
                                {lead.type || 'lead'}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              {lead.write_date ? new Date(lead.write_date).toLocaleDateString() : '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* AI Analysis */}
              {reportData.pattern_analysis && (
                <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">AI Analysis</h3>

                  {reportData.pattern_analysis.error ? (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                      <p className="text-sm text-red-800">
                        <strong>Analysis Error:</strong> {reportData.pattern_analysis.error}
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-6">
                      {/* Executive Summary */}
                      {reportData.pattern_analysis.executive_summary && (
                        <div className="bg-gradient-to-r from-primary-50 to-purple-50 rounded-xl p-5 border-2 border-primary-200">
                          <div className="flex items-center gap-2 mb-3">
                            <SparklesIcon className="h-5 w-5 text-primary-600" />
                            <h4 className="text-md font-bold text-gray-900">Executive Summary</h4>
                          </div>
                          <p className="text-gray-800">{reportData.pattern_analysis.executive_summary}</p>
                        </div>
                      )}

                      {/* Root Cause Analysis */}
                      {reportData.pattern_analysis.root_cause_analysis && (
                        <div>
                          <h4 className="text-md font-semibold text-gray-800 mb-3">Root Cause Analysis</h4>
                          <div className="space-y-3">
                            {reportData.pattern_analysis.root_cause_analysis.primary_causes?.map((cause: any, idx: number) => (
                              <div key={idx} className="bg-red-50 rounded-lg p-4 border-l-4 border-red-400">
                                <div className="flex justify-between items-start mb-2">
                                  <span className="font-medium text-gray-900">{cause.cause}</span>
                                  <span className={`text-xs px-2 py-1 rounded-full ${
                                    cause.impact === 'high' ? 'bg-red-200 text-red-800' :
                                    cause.impact === 'medium' ? 'bg-yellow-200 text-yellow-800' :
                                    'bg-gray-200 text-gray-800'
                                  }`}>
                                    {cause.impact} impact
                                  </span>
                                </div>
                                <p className="text-sm text-gray-700">{cause.explanation}</p>
                              </div>
                            ))}
                            {reportData.pattern_analysis.root_cause_analysis.contributing_factors?.length > 0 && (
                              <div className="bg-gray-50 rounded-lg p-4">
                                <p className="text-sm font-medium text-gray-700 mb-2">Contributing Factors:</p>
                                <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                                  {reportData.pattern_analysis.root_cause_analysis.contributing_factors.map((factor: string, idx: number) => (
                                    <li key={idx}>{factor}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Customer Segment Insights */}
                      {reportData.pattern_analysis.customer_segment_insights && (
                        <div>
                          <h4 className="text-md font-semibold text-gray-800 mb-3">Customer Segment Insights</h4>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {reportData.pattern_analysis.customer_segment_insights.high_risk_profiles?.map((profile: any, idx: number) => (
                              <div key={idx} className="bg-orange-50 rounded-lg p-4 border-l-4 border-orange-400">
                                <p className="font-medium text-gray-900 mb-1">{profile.profile}</p>
                                <p className="text-xs text-orange-700 mb-2">Loss Rate: {profile.loss_rate_indicator}</p>
                                <p className="text-sm text-gray-700">{profile.recommendation}</p>
                              </div>
                            ))}
                            {reportData.pattern_analysis.customer_segment_insights.best_fit_customers && (
                              <div className="bg-green-50 rounded-lg p-4 border-l-4 border-green-400">
                                <p className="font-medium text-gray-900 mb-1">Best Fit Customers</p>
                                <p className="text-sm text-gray-700">{reportData.pattern_analysis.customer_segment_insights.best_fit_customers}</p>
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Stage Breakdown */}
                      {reportData.pattern_analysis.stage_breakdown && (
                        <div>
                          <h4 className="text-md font-semibold text-gray-800 mb-3">Pipeline Stage Analysis</h4>
                          <div className="bg-yellow-50 rounded-lg p-4 border-l-4 border-yellow-400 mb-3">
                            <p className="font-medium text-gray-900 mb-1">
                              Critical Stage: {reportData.pattern_analysis.stage_breakdown.critical_stage}
                            </p>
                            <p className="text-sm text-gray-700 mb-2">{reportData.pattern_analysis.stage_breakdown.bottleneck_analysis}</p>
                            {reportData.pattern_analysis.stage_breakdown.time_insight && (
                              <p className="text-sm text-gray-600 italic">{reportData.pattern_analysis.stage_breakdown.time_insight}</p>
                            )}
                          </div>
                          {reportData.pattern_analysis.stage_breakdown.stage_recommendations?.length > 0 && (
                            <div className="space-y-2">
                              {reportData.pattern_analysis.stage_breakdown.stage_recommendations.map((rec: any, idx: number) => (
                                <div key={idx} className="bg-gray-50 rounded-lg p-3 text-sm">
                                  <span className="font-medium text-gray-900">{rec.stage}:</span>
                                  <span className="text-gray-600 ml-1">{rec.issue}</span>
                                  <span className="text-green-700 ml-1">→ {rec.fix}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Deal Size Insights */}
                      {reportData.pattern_analysis.deal_size_insights && (
                        <div>
                          <h4 className="text-md font-semibold text-gray-800 mb-3">Deal Size Analysis</h4>
                          <div className="bg-indigo-50 rounded-lg p-4 border-l-4 border-indigo-400">
                            <p className="font-medium text-gray-900 mb-1">
                              Most at Risk: {reportData.pattern_analysis.deal_size_insights.most_at_risk_segment}
                            </p>
                            <p className="text-sm text-gray-700 mb-2">{reportData.pattern_analysis.deal_size_insights.trend}</p>
                            {reportData.pattern_analysis.deal_size_insights.pricing_recommendation && (
                              <p className="text-sm text-indigo-700">
                                <strong>Pricing Insight:</strong> {reportData.pattern_analysis.deal_size_insights.pricing_recommendation}
                              </p>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Competitor Insights */}
                      {reportData.pattern_analysis.competitor_insights && (
                        <div>
                          <h4 className="text-md font-semibold text-gray-800 mb-3">Competitor Analysis</h4>
                          <div className="bg-purple-50 rounded-lg p-4 border-l-4 border-purple-400">
                            {reportData.pattern_analysis.competitor_insights.estimated_competitor_wins > 0 && (
                              <p className="font-medium text-purple-900 mb-2">
                                {reportData.pattern_analysis.competitor_insights.estimated_competitor_wins} deals lost to competitors
                              </p>
                            )}
                            {reportData.pattern_analysis.competitor_insights.common_patterns && (
                              <p className="text-sm text-gray-700 mb-2">{reportData.pattern_analysis.competitor_insights.common_patterns}</p>
                            )}
                            {reportData.pattern_analysis.competitor_insights.differentiation_gaps?.length > 0 && (
                              <div className="mb-2">
                                <p className="text-sm font-medium text-gray-700">Differentiation Gaps:</p>
                                <ul className="list-disc list-inside text-sm text-gray-600">
                                  {reportData.pattern_analysis.competitor_insights.differentiation_gaps.map((gap: string, idx: number) => (
                                    <li key={idx}>{gap}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {reportData.pattern_analysis.competitor_insights.counter_strategy && (
                              <p className="text-sm text-purple-700">
                                <strong>Counter Strategy:</strong> {reportData.pattern_analysis.competitor_insights.counter_strategy}
                              </p>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Action Plan */}
                      {reportData.pattern_analysis.action_plan && (
                        <div>
                          <h4 className="text-md font-semibold text-gray-800 mb-3">Action Plan</h4>
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {reportData.pattern_analysis.action_plan.immediate_actions?.length > 0 && (
                              <div className="bg-green-50 rounded-lg p-4 border-l-4 border-green-400">
                                <p className="font-medium text-green-900 mb-2">Immediate Actions</p>
                                <ul className="space-y-1">
                                  {reportData.pattern_analysis.action_plan.immediate_actions.map((action: string, idx: number) => (
                                    <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
                                      <span className="text-green-600 mt-0.5">✓</span>
                                      {action}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {reportData.pattern_analysis.action_plan.process_improvements?.length > 0 && (
                              <div className="bg-blue-50 rounded-lg p-4 border-l-4 border-blue-400">
                                <p className="font-medium text-blue-900 mb-2">Process Improvements</p>
                                <ul className="space-y-1">
                                  {reportData.pattern_analysis.action_plan.process_improvements.map((improvement: string, idx: number) => (
                                    <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
                                      <span className="text-blue-600 mt-0.5">→</span>
                                      {improvement}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {reportData.pattern_analysis.action_plan.team_training_needs?.length > 0 && (
                              <div className="bg-amber-50 rounded-lg p-4 border-l-4 border-amber-400">
                                <p className="font-medium text-amber-900 mb-2">Training Needs</p>
                                <ul className="space-y-1">
                                  {reportData.pattern_analysis.action_plan.team_training_needs.map((need: string, idx: number) => (
                                    <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
                                      <span className="text-amber-600 mt-0.5">📚</span>
                                      {need}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Re-engagement Strategy */}
                      {reportData.pattern_analysis.re_engagement_strategy && (
                        <div>
                          <h4 className="text-md font-semibold text-gray-800 mb-3">Re-engagement Strategy</h4>
                          <div className="bg-blue-50 rounded-lg p-4 border-l-4 border-blue-400">
                            {reportData.pattern_analysis.re_engagement_strategy.high_value_recoverable > 0 && (
                              <p className="font-medium text-blue-900 mb-2">
                                {reportData.pattern_analysis.re_engagement_strategy.high_value_recoverable} high-value leads worth re-engaging
                              </p>
                            )}
                            {reportData.pattern_analysis.re_engagement_strategy.best_timing && (
                              <p className="text-sm text-gray-700 mb-2">
                                <strong>Best Timing:</strong> {reportData.pattern_analysis.re_engagement_strategy.best_timing}
                              </p>
                            )}
                            {reportData.pattern_analysis.re_engagement_strategy.approach_by_reason?.length > 0 && (
                              <div className="mt-3 space-y-2">
                                {reportData.pattern_analysis.re_engagement_strategy.approach_by_reason.map((approach: any, idx: number) => (
                                  <div key={idx} className="bg-white rounded p-2 text-sm">
                                    <span className="font-medium text-gray-900">{approach.lost_reason}:</span>
                                    <span className="text-gray-700 ml-1">{approach.re_engagement_approach}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Fallback for old format - Top Loss Reasons */}
                      {!reportData.pattern_analysis.root_cause_analysis && reportData.pattern_analysis.top_loss_reasons?.length > 0 && (
                        <div>
                          <h4 className="text-md font-semibold text-gray-800 mb-3">Top Loss Reasons</h4>
                          <div className="space-y-3">
                            {reportData.pattern_analysis.top_loss_reasons.map((reason: any, idx: number) => (
                              <div key={idx} className="bg-gray-50 rounded-lg p-4 border-l-4 border-red-400">
                                <div className="flex justify-between items-start mb-2">
                                  <span className="font-medium text-gray-900">{reason.reason}</span>
                                  <span className="text-sm text-gray-600">{reason.count} ({reason.percentage}%)</span>
                                </div>
                                <p className="text-sm text-green-700 flex items-start gap-2">
                                  <span className="font-medium">Action:</span> {reason.action}
                                </p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Fallback for old format - Quick Wins */}
                      {!reportData.pattern_analysis.action_plan && reportData.pattern_analysis.quick_wins?.length > 0 && (
                        <div>
                          <h4 className="text-md font-semibold text-gray-800 mb-3">Quick Wins</h4>
                          <div className="bg-green-50 rounded-lg p-4 border-l-4 border-green-400">
                            <ul className="space-y-2">
                              {reportData.pattern_analysis.quick_wins.map((win: string, idx: number) => (
                                <li key={idx} className="flex items-start gap-2 text-sm text-gray-800">
                                  <span className="text-green-600 mt-0.5">✓</span>
                                  {win}
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      )}

                      {/* Fallback for old format - Re-engage Priority */}
                      {!reportData.pattern_analysis.re_engagement_strategy && reportData.pattern_analysis.re_engage_priority && (
                        <div>
                          <h4 className="text-md font-semibold text-gray-800 mb-3">Re-engagement Opportunity</h4>
                          <div className="bg-blue-50 rounded-lg p-4 border-l-4 border-blue-400">
                            {reportData.pattern_analysis.re_engage_priority.high_value_recoverable > 0 && (
                              <p className="font-medium text-blue-900 mb-2">
                                {reportData.pattern_analysis.re_engage_priority.high_value_recoverable} high-value leads worth re-engaging
                              </p>
                            )}
                            <p className="text-sm text-gray-700 mb-1">
                              <strong>Criteria:</strong> {reportData.pattern_analysis.re_engage_priority.criteria}
                            </p>
                            <p className="text-sm text-gray-700">
                              <strong>Approach:</strong> {reportData.pattern_analysis.re_engage_priority.suggested_approach}
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
              </div>{/* End PDF Export Container */}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default LostLeadsPage;
