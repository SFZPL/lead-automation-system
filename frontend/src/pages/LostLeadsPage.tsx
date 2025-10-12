import React, { useMemo, useState } from 'react';
import { useMutation, useQuery } from 'react-query';
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

const LostLeadsPage: React.FC = () => {
  const [limit, setLimit] = useState<number>(10);
  const [salesperson, setSalesperson] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [selectedLeadId, setSelectedLeadId] = useState<number | null>(null);
  const [maxInternalNotes, setMaxInternalNotes] = useState<number>(6);
  const [maxEmails, setMaxEmails] = useState<number>(4);
  const [includeOutlookEmails, setIncludeOutlookEmails] = useState<boolean>(false);
  const [insights, setInsights] = useState<Record<number, LostLeadAnalysis>>({});
  const [loadingStep, setLoadingStep] = useState<number>(0);

  // Get user identifier from localStorage for email search
  const userIdentifier = localStorage.getItem('email_user_identifier') || '';

  // Loading steps for multi-step indicator
  const loadingSteps = [
    'Connecting to Odoo...',
    'Fetching lead details...',
    includeOutlookEmails ? 'Searching Outlook emails...' : 'Fetching internal notes...',
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
    async ({ leadId, params }: {
      leadId: number;
      params: {
        max_internal_notes?: number;
        max_emails?: number;
        user_identifier?: string;
        include_outlook_emails?: boolean;
      }
    }) => {
      // Reset and start progressing through steps
      setLoadingStep(0);
      const stepInterval = setInterval(() => {
        setLoadingStep(prev => Math.min(prev + 1, loadingSteps.length - 1));
      }, 8000); // Progress every 8 seconds

      try {
        const response = await api.analyzeLostLead(leadId, params);
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

  const selectedAnalysis = selectedLeadId ? insights[selectedLeadId] : undefined;

  const keyFactors = useMemo(
    () => (selectedAnalysis?.analysis?.key_factors as string[] | undefined)?.filter((item) => !!item && item.trim().length > 0) ?? [],
    [selectedAnalysis]
  );
  const talkingPoints = useMemo(
    () => (selectedAnalysis?.analysis?.follow_up_plan?.talking_points as string[] | undefined)?.filter((item) => !!item && item.trim().length > 0) ?? [],
    [selectedAnalysis]
  );
  const proposedActions = useMemo(
    () => (selectedAnalysis?.analysis?.follow_up_plan?.proposed_actions as string[] | undefined)?.filter((item) => !!item && item.trim().length > 0) ?? [],
    [selectedAnalysis]
  );
  const risks = useMemo(
    () => (selectedAnalysis?.analysis?.follow_up_plan?.risks as string[] | undefined)?.filter((item) => !!item && item.trim().length > 0) ?? [],
    [selectedAnalysis]
  );
  const intelGaps = useMemo(
    () => (selectedAnalysis?.analysis?.intel_gaps as string[] | undefined)?.filter((item) => !!item && item.trim().length > 0) ?? [],
    [selectedAnalysis]
  );

  const handleAnalyze = (leadId: number) => {
    setSelectedLeadId(leadId);
    analyzeMutation.mutate({
      leadId,
      params: {
        max_internal_notes: maxInternalNotes,
        max_emails: maxEmails,
        user_identifier: includeOutlookEmails ? userIdentifier : undefined,
        include_outlook_emails: includeOutlookEmails,
      },
    });
  };

  const formatCurrency = (value?: number) => {
    if (value === undefined || value === null) return '—';
    try {
      return new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD' }).format(value);
    } catch (error) {
      return `$${value}`;
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
            to revive the conversation. Adjust the limits below to control how many notes and emails feed the analysis.
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
          <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 shadow-sm">
            <label htmlFor="max-notes" className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Notes
            </label>
            <input
              id="max-notes"
              type="number"
              min={1}
              max={20}
              value={maxInternalNotes}
              onChange={(event) => setMaxInternalNotes(Math.min(Math.max(1, Number(event.target.value) || 1), 20))}
              className="w-20 rounded-md border border-gray-300 px-2 py-1 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </div>
          <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 shadow-sm">
            <label htmlFor="max-emails" className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Emails
            </label>
            <input
              id="max-emails"
              type="number"
              min={1}
              max={20}
              value={maxEmails}
              onChange={(event) => setMaxEmails(Math.min(Math.max(1, Number(event.target.value) || 1), 20))}
              className="w-20 rounded-md border border-gray-300 px-2 py-1 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </div>
          <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 shadow-sm">
            <input
              id="outlook-emails"
              type="checkbox"
              checked={includeOutlookEmails}
              onChange={(e) => setIncludeOutlookEmails(e.target.checked)}
              disabled={!userIdentifier}
              className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500 disabled:opacity-50"
            />
            <label
              htmlFor="outlook-emails"
              className="text-xs font-medium uppercase tracking-wide text-gray-500 cursor-pointer"
              title={!userIdentifier ? 'Configure email in Email Settings first' : 'Search Outlook/Microsoft emails'}
            >
              Outlook
            </label>
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
                      {pending ? loadingSteps[loadingStep] : isSelected ? 'Re-run analysis' : 'Analyse lead'}
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
              <p className="mt-1 text-sm text-gray-500">We will pull recent internal notes and emails, then craft a tailored comeback plan.</p>
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
                  <div className="text-sm text-gray-500">
                    <p>Stage: {selectedAnalysis.lead?.stage_id || 'Lost'}</p>
                    <p>Salesperson: {selectedAnalysis.lead?.user_id || 'Unassigned'}</p>
                  </div>
                </div>

                <div className="mt-4 space-y-4 text-sm text-gray-700">
                  <div>
                    <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Loss Summary</h3>
                    <p className="mt-1 whitespace-pre-line text-gray-800">
                      {selectedAnalysis.analysis?.loss_summary || 'No summary produced.'}
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
                        {selectedAnalysis.analysis?.follow_up_plan?.objective || 'No objective suggested.'}
                      </p>
                    </div>
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                      <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Timeline</h3>
                      <p className="mt-1 text-gray-800">
                        {selectedAnalysis.analysis?.follow_up_plan?.recommended_timeline || 'No timeline provided.'}
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
                    {selectedAnalysis.internal_notes.length === 0 && <p className="text-gray-500">No internal notes were available.</p>}
                    {selectedAnalysis.internal_notes.map((note) => (
                      <div key={note.id} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
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
                    {selectedAnalysis.emails.length === 0 && <p className="text-gray-500">No customer-facing emails were found.</p>}
                    {selectedAnalysis.emails.map((email) => (
                      <div key={email.id} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
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
          )}
        </section>
      </div>
    </div>
  );
};

export default LostLeadsPage;
