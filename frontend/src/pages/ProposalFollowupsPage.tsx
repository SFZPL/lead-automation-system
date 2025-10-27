import React, { useState } from 'react';
import { useQuery, useQueryClient } from 'react-query';
import toast from 'react-hot-toast';
import {
  EnvelopeIcon,
  ClockIcon,
  BuildingOfficeIcon,
  UserCircleIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  ExclamationCircleIcon,
  CheckCircleIcon,
  PlayIcon,
  UserPlusIcon,
  XCircleIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import api from '../utils/api';
import AssignLeadModal from '../components/AssignLeadModal';

interface ProposalFollowupSummary {
  unanswered_count: number;
  pending_proposals_count: number;
  filtered_count?: number;
  total_count: number;
  days_back: number;
  no_response_days: number;
  last_updated?: string;
}

interface OdooLead {
  id: number;
  name: string;
  partner_name?: string;
  contact_name?: string;
  stage?: string;
  probability?: number;
  expected_revenue?: number;
  type?: string;
}

interface ThreadAnalysis {
  summary: string;
  sentiment: string;
  urgency: string;
  key_points: string[];
  draft_email: string;
}

interface EmailClassification {
  is_lead: boolean;
  confidence: number;
  category: string;
}

interface ProposalFollowupThread {
  conversation_id: string;
  external_email: string;
  subject: string;
  days_waiting: number;
  last_contact_date?: string;
  proposal_date?: string;
  odoo_lead?: OdooLead | null;
  analysis?: ThreadAnalysis;
  classification?: EmailClassification;
}

interface ProposalFollowupData {
  summary: ProposalFollowupSummary;
  unanswered: ProposalFollowupThread[];
  pending_proposals: ProposalFollowupThread[];
  filtered?: ProposalFollowupThread[];
}

interface SavedReport {
  id: number;
  report_type: '90day' | 'monthly' | 'weekly';
  report_period: string;
  created_at: string;
  result: ProposalFollowupData;
  parameters: {
    days_back: number;
    no_response_days: number;
    engage_email: string;
  };
}

const ProposalFollowupsPage: React.FC = () => {
  const queryClient = useQueryClient();

  // Restore state from localStorage on mount
  const getStoredState = <T,>(key: string, defaultValue: T): T => {
    try {
      const stored = localStorage.getItem(`proposalFollowups_${key}`);
      return stored ? JSON.parse(stored) : defaultValue;
    } catch {
      return defaultValue;
    }
  };

  const [daysBack, setDaysBack] = useState<number>(() => getStoredState('daysBack', 3));
  const [noResponseDays, setNoResponseDays] = useState<number>(() => getStoredState('noResponseDays', 3));
  const [selectedTab, setSelectedTab] = useState<'unanswered' | 'pending' | 'reports'>(() => getStoredState('selectedTab', 'unanswered'));
  const [expandedThread, setExpandedThread] = useState<string | null>(() => getStoredState('expandedThread', null));
  const [hasStarted, setHasStarted] = useState<boolean>(false);
  const [startTime, setStartTime] = useState<number | null>(null);
  const [elapsedTime, setElapsedTime] = useState<number>(0);
  const [forceRefresh, setForceRefresh] = useState<boolean>(false);
  const [showLeadsOnly, setShowLeadsOnly] = useState<boolean>(() => getStoredState('showLeadsOnly', false));
  const [showFilteredEmails, setShowFilteredEmails] = useState<boolean>(() => getStoredState('showFilteredEmails', false));
  const [assignModalOpen, setAssignModalOpen] = useState<boolean>(false);
  const [selectedLeadForAssignment, setSelectedLeadForAssignment] = useState<ProposalFollowupThread | null>(null);
  const [showGenerateReportModal, setShowGenerateReportModal] = useState<boolean>(false);
  const [selectedReportType, setSelectedReportType] = useState<'90day' | 'monthly' | 'weekly'>('weekly');
  const [showDraftModal, setShowDraftModal] = useState<boolean>(false);
  const [selectedThread, setSelectedThread] = useState<ProposalFollowupThread | null>(null);
  const [draftEmail, setDraftEmail] = useState<string>('');
  const [editPrompt, setEditPrompt] = useState<string>('');
  const [isGeneratingDraft, setIsGeneratingDraft] = useState<boolean>(false);
  const [isRefiningDraft, setIsRefiningDraft] = useState<boolean>(false);
  const [isSendingEmail, setIsSendingEmail] = useState<boolean>(false);
  const [isGeneratingReport, setIsGeneratingReport] = useState<boolean>(false);
  const [reportGenerationStartTime, setReportGenerationStartTime] = useState<number | null>(null);

  // Mock users list - TODO: Replace with actual API call to fetch users
  const mockUsers = [
    { id: 1, name: 'John Doe', email: 'john@prezlab.com' },
    { id: 2, name: 'Jane Smith', email: 'jane@prezlab.com' },
    { id: 3, name: 'Admin User', email: 'admin@prezlab.com' },
  ];

  // Fetch proposal follow-ups - load cached data on mount, refresh only when triggered
  const followupsQuery = useQuery(
    ['proposal-followups', daysBack, noResponseDays, forceRefresh],
    async () => {
      const response = await api.getProposalFollowups({
        days_back: daysBack,
        no_response_days: noResponseDays,
        engage_email: 'automated.response@prezlab.com',
        force_refresh: forceRefresh
      });
      return response.data as ProposalFollowupData;
    },
    {
      enabled: true, // Always enabled to load cached data
      refetchOnWindowFocus: false,
      refetchOnMount: false,
      refetchOnReconnect: false,
      retry: 1,
      staleTime: Infinity, // Never consider data stale
      onSuccess: () => {
        // Mark as started once data is loaded
        if (!hasStarted) {
          setHasStarted(true);
        }
        // Reset force refresh after successful fetch
        if (forceRefresh) {
          setForceRefresh(false);
        }
      }
    }
  );

  // Fetch saved reports
  const reportsQuery = useQuery(
    ['saved-reports'],
    async () => {
      const response = await api.getSavedReports();
      console.log('Saved reports response:', response.data);
      return response.data.reports as SavedReport[];
    },
    {
      enabled: selectedTab === 'reports',
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000, // 5 minutes
      onError: (error) => {
        console.error('Error fetching saved reports:', error);
        toast.error('Failed to load saved reports');
      }
    }
  );

  // Persist state to localStorage
  React.useEffect(() => {
    localStorage.setItem('proposalFollowups_daysBack', JSON.stringify(daysBack));
  }, [daysBack]);

  React.useEffect(() => {
    localStorage.setItem('proposalFollowups_noResponseDays', JSON.stringify(noResponseDays));
  }, [noResponseDays]);

  React.useEffect(() => {
    localStorage.setItem('proposalFollowups_selectedTab', JSON.stringify(selectedTab));
  }, [selectedTab]);

  React.useEffect(() => {
    localStorage.setItem('proposalFollowups_expandedThread', JSON.stringify(expandedThread));
  }, [expandedThread]);

  React.useEffect(() => {
    localStorage.setItem('proposalFollowups_showLeadsOnly', JSON.stringify(showLeadsOnly));
  }, [showLeadsOnly]);

  React.useEffect(() => {
    localStorage.setItem('proposalFollowups_showFilteredEmails', JSON.stringify(showFilteredEmails));
  }, [showFilteredEmails]);

  // Timer effect for elapsed time
  React.useEffect(() => {
    if (followupsQuery.isLoading && startTime) {
      const timer = setInterval(() => {
        setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
      }, 1000);
      return () => clearInterval(timer);
    } else if (!followupsQuery.isLoading) {
      setStartTime(null);
      setElapsedTime(0);
    }
  }, [followupsQuery.isLoading, startTime]);

  // Timer effect for report generation elapsed time
  const [reportElapsedTime, setReportElapsedTime] = React.useState<number>(0);
  React.useEffect(() => {
    if (isGeneratingReport && reportGenerationStartTime) {
      const timer = setInterval(() => {
        setReportElapsedTime(Math.floor((Date.now() - reportGenerationStartTime) / 1000));
      }, 1000);
      return () => clearInterval(timer);
    } else {
      setReportElapsedTime(0);
    }
  }, [isGeneratingReport, reportGenerationStartTime]);

  const handleStartAnalysis = () => {
    setHasStarted(true);
    setStartTime(Date.now());
    setElapsedTime(0);
    setForceRefresh(true); // Trigger new analysis with force_refresh=true
  };

  const handleCancelAnalysis = () => {
    followupsQuery.remove(); // Clear query cache
    setHasStarted(false);
    setStartTime(null);
    setElapsedTime(0);
  };

  const handleAssignLead = (thread: ProposalFollowupThread) => {
    setSelectedLeadForAssignment(thread);
    setAssignModalOpen(true);
  };

  const handleGenerateDraft = async (thread: ProposalFollowupThread) => {
    setSelectedThread(thread);
    setIsGeneratingDraft(true);
    setShowDraftModal(true);
    setDraftEmail('');
    setEditPrompt('');

    try {
      const response = await api.generateDraft({
        thread_data: thread
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

  const handleRefineDraft = async () => {
    if (!editPrompt.trim()) {
      toast.error('Please enter refinement instructions');
      return;
    }

    setIsRefiningDraft(true);
    try {
      const response = await api.refineDraft({
        current_draft: draftEmail,
        edit_prompt: editPrompt
      });
      setDraftEmail(response.data.refined_draft || '');
      setEditPrompt('');
      toast.success('Draft refined successfully!');
    } catch (error) {
      console.error('Error refining draft:', error);
      toast.error('Failed to refine draft');
    } finally {
      setIsRefiningDraft(false);
    }
  };

  const handleSendEmail = async () => {
    if (!selectedThread || !draftEmail.trim()) {
      toast.error('No draft to send');
      return;
    }

    setIsSendingEmail(true);
    try {
      await api.sendFollowupEmail({
        conversation_id: selectedThread.conversation_id,
        draft_body: draftEmail,
        subject: selectedThread.subject
      });
      toast.success('Email sent successfully and marked as complete!');
      setShowDraftModal(false);
      setDraftEmail('');
      setSelectedThread(null);
      // Refresh the follow-ups to remove completed item
      followupsQuery.refetch();
    } catch (error) {
      console.error('Error sending email:', error);
      toast.error('Failed to send email');
    } finally {
      setIsSendingEmail(false);
    }
  };

  const handleMarkComplete = async (thread: ProposalFollowupThread) => {
    try {
      await api.markFollowupComplete({
        thread_id: thread.conversation_id,
        conversation_id: thread.conversation_id,
        notes: 'Manually marked as complete'
      });
      toast.success('Follow-up marked as complete!');
      // Refresh to remove from list
      followupsQuery.refetch();
    } catch (error) {
      console.error('Error marking complete:', error);
      toast.error('Failed to mark as complete');
    }
  };

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatLastUpdated = (timestamp?: string): string => {
    if (!timestamp) return '';
    try {
      const date = new Date(timestamp);
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
      });
    } catch {
      return timestamp;
    }
  };

  const getSentimentColor = (sentiment: string) => {
    const s = sentiment.toLowerCase();
    if (s.includes('positive')) return 'text-green-600';
    if (s.includes('negative')) return 'text-red-600';
    if (s.includes('urgent')) return 'text-orange-600';
    return 'text-gray-600';
  };

  const getUrgencyBadge = (urgency: string) => {
    const u = urgency.toLowerCase();
    if (u === 'high') return 'bg-red-100 text-red-800';
    if (u === 'medium') return 'bg-yellow-100 text-yellow-800';
    return 'bg-green-100 text-green-800';
  };

  const getClassificationBadge = (classification?: EmailClassification) => {
    if (!classification) return null;

    const { is_lead, category, confidence } = classification;

    if (is_lead) {
      return (
        <span className="px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800">
          ✓ Lead ({Math.round(confidence * 100)}%)
        </span>
      );
    } else {
      const categoryLabels: { [key: string]: string } = {
        'job_application': '💼 Job App',
        'newsletter': '📰 Newsletter',
        'event_invitation': '🎉 Event',
        'supplier': '📦 Supplier',
        'recruitment': '👔 Recruitment',
        'spam': '🚫 Spam',
        'other': '❓ Other'
      };

      return (
        <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-700">
          {categoryLabels[category] || category}
        </span>
      );
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A';
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    } catch {
      return dateString;
    }
  };

  const renderThreadCard = (thread: ProposalFollowupThread, category: 'unanswered' | 'pending') => {
    const isExpanded = expandedThread === thread.conversation_id;

    return (
      <div
        key={thread.conversation_id}
        className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 hover:shadow-md transition-shadow"
      >
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <EnvelopeIcon className="w-5 h-5 text-blue-500" />
              <h3 className="font-semibold text-gray-900">{thread.subject || 'No Subject'}</h3>
            </div>
            <div className="flex items-center gap-4 text-sm text-gray-600">
              <div className="flex items-center gap-1">
                <UserCircleIcon className="w-4 h-4" />
                <span>{thread.external_email}</span>
              </div>
              <div className="flex items-center gap-1">
                <ClockIcon className="w-4 h-4" />
                <span>{thread.days_waiting} days ago</span>
              </div>
              {thread.classification && (
                <div className="flex items-center gap-1">
                  {getClassificationBadge(thread.classification)}
                </div>
              )}
            </div>
          </div>

          {thread.analysis && (
            <span className={`px-2 py-1 text-xs font-medium rounded ${getUrgencyBadge(thread.analysis.urgency)}`}>
              {thread.analysis.urgency.toUpperCase()}
            </span>
          )}
        </div>

        {/* Odoo Lead Info */}
        {thread.odoo_lead && (
          <div className="bg-blue-50 rounded-md p-3 mb-3">
            <div className="flex items-center gap-2 mb-1">
              <BuildingOfficeIcon className="w-4 h-4 text-blue-600" />
              <span className="font-medium text-blue-900">
                {thread.odoo_lead.partner_name || thread.odoo_lead.name}
              </span>
            </div>
            <div className="text-sm text-blue-700 space-y-1">
              <div>Contact: {thread.odoo_lead.contact_name || 'N/A'}</div>
              <div>Stage: {thread.odoo_lead.stage || 'Unknown'}</div>
              {thread.odoo_lead.expected_revenue && (
                <div>Value: ${thread.odoo_lead.expected_revenue.toLocaleString()}</div>
              )}
            </div>
          </div>
        )}

        {/* Analysis */}
        {thread.analysis && (
          <div className="space-y-3">
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-1">Summary</h4>
              <p className="text-sm text-gray-600">{thread.analysis.summary}</p>
            </div>

            {thread.analysis.sentiment && (
              <div>
                <span className="text-sm font-medium text-gray-700">Sentiment: </span>
                <span className={`text-sm font-medium ${getSentimentColor(thread.analysis.sentiment)}`}>
                  {thread.analysis.sentiment}
                </span>
              </div>
            )}

            {thread.analysis.key_points && thread.analysis.key_points.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-1">Key Points</h4>
                <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                  {thread.analysis.key_points.map((point, idx) => (
                    <li key={idx}>{point}</li>
                  ))}
                </ul>
              </div>
            )}

          </div>
        )}

        {/* No Analysis */}
        {!thread.analysis && (
          <div className="text-sm text-gray-500 italic">
            Analysis not available for this thread
          </div>
        )}

        {/* Action Buttons */}
        <div className="mt-4 pt-4 border-t border-gray-200 flex gap-3">
          <button
            onClick={() => handleGenerateDraft(thread)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
          >
            <DocumentTextIcon className="w-4 h-4" />
            Generate Draft
          </button>

          <button
            onClick={() => handleMarkComplete(thread)}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 transition-colors"
          >
            <CheckCircleIcon className="w-4 h-4" />
            Mark Complete
          </button>

          <a
            href={`https://outlook.office.com/mail/inbox/id/${thread.conversation_id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            Open Thread
          </a>

          <button
            onClick={() => handleAssignLead(thread)}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 transition-colors"
          >
            <UserPlusIcon className="w-4 h-4" />
            Assign Lead
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Proposal Follow-ups</h1>
          <p className="text-gray-600 mt-1">
            Track unanswered emails and proposals awaiting response
          </p>
          {followupsQuery.data?.summary.last_updated && (
            <p className="text-sm text-gray-500 mt-1">
              Last updated: {formatLastUpdated(followupsQuery.data.summary.last_updated)}
            </p>
          )}
        </div>

        {!hasStarted ? (
          <button
            onClick={handleStartAnalysis}
            className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 text-lg font-semibold"
          >
            <PlayIcon className="w-6 h-6" />
            Start Analysis
          </button>
        ) : (
          <button
            onClick={() => followupsQuery.refetch()}
            disabled={followupsQuery.isLoading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            <ArrowPathIcon className={`w-5 h-5 ${followupsQuery.isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        )}
      </div>

      {/* Settings */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <div className="flex items-center gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Look back (days)
            </label>
            <input
              type="number"
              value={daysBack}
              onChange={(e) => setDaysBack(Number(e.target.value))}
              disabled={hasStarted}
              className="w-24 px-3 py-2 border border-gray-300 rounded-md disabled:bg-gray-100 disabled:cursor-not-allowed"
              min="1"
              max="30"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              No response threshold (days)
            </label>
            <input
              type="number"
              value={noResponseDays}
              onChange={(e) => setNoResponseDays(Number(e.target.value))}
              disabled={hasStarted}
              className="w-24 px-3 py-2 border border-gray-300 rounded-md disabled:bg-gray-100 disabled:cursor-not-allowed"
              min="1"
              max="14"
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="showLeadsOnly"
              checked={showLeadsOnly}
              onChange={(e) => setShowLeadsOnly(e.target.checked)}
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <label htmlFor="showLeadsOnly" className="text-sm font-medium text-gray-700">
              Show Leads Only
            </label>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="showFilteredEmails"
              checked={showFilteredEmails}
              onChange={(e) => setShowFilteredEmails(e.target.checked)}
              className="w-4 h-4 text-yellow-600 border-gray-300 rounded focus:ring-yellow-500"
            />
            <label htmlFor="showFilteredEmails" className="text-sm font-medium text-gray-700">
              Show Filtered Emails
              {followupsQuery.data?.summary?.filtered_count ? (
                <span className="ml-1 text-xs text-gray-500">
                  ({followupsQuery.data.summary.filtered_count})
                </span>
              ) : null}
            </label>
          </div>

          {hasStarted && (
            <p className="text-xs text-gray-500 italic ml-2">
              Settings locked during analysis
            </p>
          )}
        </div>
      </div>

      {/* Summary Cards */}
      {hasStarted && followupsQuery.data && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Unanswered Emails</p>
                <p className="text-3xl font-bold text-orange-600 mt-1">
                  {followupsQuery.data.summary.unanswered_count}
                </p>
              </div>
              <ExclamationCircleIcon className="w-12 h-12 text-orange-400" />
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Pending Proposals</p>
                <p className="text-3xl font-bold text-blue-600 mt-1">
                  {followupsQuery.data.summary.pending_proposals_count}
                </p>
              </div>
              <ClockIcon className="w-12 h-12 text-blue-400" />
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total Follow-ups</p>
                <p className="text-3xl font-bold text-purple-600 mt-1">
                  {followupsQuery.data.summary.total_count}
                </p>
              </div>
              <EnvelopeIcon className="w-12 h-12 text-purple-400" />
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
        {hasStarted && (
          <>
            <button
              onClick={() => setSelectedTab('unanswered')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                selectedTab === 'unanswered'
                  ? 'border-orange-500 text-orange-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Unanswered Emails
              {followupsQuery.data && (
                <span className="ml-2 py-0.5 px-2 rounded-full text-xs bg-orange-100 text-orange-800">
                  {followupsQuery.data.summary.unanswered_count}
                </span>
              )}
            </button>

            <button
              onClick={() => setSelectedTab('pending')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                selectedTab === 'pending'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Pending Proposals
              {followupsQuery.data && (
                <span className="ml-2 py-0.5 px-2 rounded-full text-xs bg-blue-100 text-blue-800">
                  {followupsQuery.data.summary.pending_proposals_count}
                </span>
              )}
            </button>
          </>
        )}

        <button
          onClick={() => setSelectedTab('reports')}
          className={`py-4 px-1 border-b-2 font-medium text-sm ${
            selectedTab === 'reports'
              ? 'border-purple-500 text-purple-600'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          📊 Saved Reports
          {reportsQuery.data && (
            <span className="ml-2 py-0.5 px-2 rounded-full text-xs bg-purple-100 text-purple-800">
              {reportsQuery.data.length}
            </span>
          )}
        </button>
        </nav>
      </div>

      {/* Content */}
      <div>
        {!hasStarted && (
          <div className="text-center py-20">
            <PlayIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-900 mb-2">Ready to Analyze</h3>
            <p className="text-gray-600">
              Click "Start Analysis" to begin scanning proposal follow-ups from engage@prezlab.com
            </p>
          </div>
        )}

        {hasStarted && followupsQuery.isLoading && (
          <div className="text-center py-12">
            <ArrowPathIcon className="w-12 h-12 text-blue-500 animate-spin mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-900 mb-2">Analyzing Proposal Follow-ups</h3>
            <div className="space-y-2">
              <p className="text-gray-700">
                <span className="font-medium">Elapsed Time:</span> {formatTime(elapsedTime)}
              </p>
              <p className="text-gray-600 text-sm">
                Fetching emails from engage@prezlab.com, analyzing threads, and matching to Odoo leads...
              </p>
              <p className="text-gray-500 text-sm italic">
                Estimated time: 3-5 minutes
              </p>
              <button
                onClick={handleCancelAnalysis}
                className="mt-4 px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 text-sm font-medium"
              >
                Cancel Analysis
              </button>
            </div>
          </div>
        )}

        {hasStarted && followupsQuery.isError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">
              Error loading follow-ups. Make sure the engage email is connected in Settings.
            </p>
          </div>
        )}

        {followupsQuery.data && (
          <div className="space-y-4">
            {selectedTab === 'unanswered' && (
              <>
                {(() => {
                  const filteredThreads = showLeadsOnly
                    ? followupsQuery.data.unanswered.filter(t => t.classification?.is_lead !== false)
                    : followupsQuery.data.unanswered;

                  return filteredThreads.length === 0 ? (
                    <div className="text-center py-12 bg-gray-50 rounded-lg">
                      <CheckCircleIcon className="w-12 h-12 text-green-500 mx-auto mb-2" />
                      <p className="text-gray-600">
                        {showLeadsOnly
                          ? 'No unanswered lead emails! Great job! 🎉'
                          : 'No unanswered emails! Great job! 🎉'}
                      </p>
                    </div>
                  ) : (
                    filteredThreads.map((thread) =>
                      renderThreadCard(thread, 'unanswered')
                    )
                  );
                })()}
              </>
            )}

            {selectedTab === 'pending' && (
              <>
                {(() => {
                  const filteredThreads = showLeadsOnly
                    ? followupsQuery.data.pending_proposals.filter(t => t.classification?.is_lead !== false)
                    : followupsQuery.data.pending_proposals;

                  return filteredThreads.length === 0 ? (
                    <div className="text-center py-12 bg-gray-50 rounded-lg">
                      <CheckCircleIcon className="w-12 h-12 text-green-500 mx-auto mb-2" />
                      <p className="text-gray-600">
                        {showLeadsOnly
                          ? 'No pending lead proposals! All caught up! 🎉'
                          : 'No pending proposals! All caught up! 🎉'}
                      </p>
                    </div>
                  ) : (
                    filteredThreads.map((thread) =>
                      renderThreadCard(thread, 'pending')
                    )
                  );
                })()}
              </>
            )}

            {/* Filtered Emails Section */}
            {showFilteredEmails && followupsQuery.data?.filtered && followupsQuery.data.filtered.length > 0 && (
              <div className="mt-6 space-y-4">
                <div className="border-t border-gray-200 pt-6">
                  <h3 className="text-lg font-semibold text-gray-700 mb-3 flex items-center gap-2">
                    <ExclamationCircleIcon className="w-5 h-5 text-yellow-600" />
                    Filtered Emails ({followupsQuery.data.filtered.length})
                    <span className="text-xs font-normal text-gray-500">
                      (job apps, spam, newsletters, etc.)
                    </span>
                  </h3>
                  <div className="space-y-3">
                    {followupsQuery.data.filtered.map((thread, index) => (
                      <div key={index} className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <h4 className="font-medium text-gray-900">{thread.subject}</h4>
                            <p className="text-sm text-gray-600 mt-1">
                              From: {thread.external_email}
                            </p>
                            <div className="flex items-center gap-3 mt-2 text-xs">
                              <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded">
                                {thread.classification?.category || 'unknown'}
                              </span>
                              <span className="text-gray-500">
                                Confidence: {Math.round((thread.classification?.confidence || 0) * 100)}%
                              </span>
                              <span className="text-gray-500">
                                {thread.days_waiting} days ago
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {selectedTab === 'reports' && (
              <div className="space-y-4">
                {/* Generate Report Button */}
                <div className="flex justify-between items-center">
                  <div>
                    <h2 className="text-lg font-semibold text-gray-900">Saved Reports</h2>
                    <p className="text-sm text-gray-600">View and generate follow-up reports for your team</p>
                  </div>
                  <button
                    onClick={() => setShowGenerateReportModal(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
                  >
                    <DocumentTextIcon className="w-5 h-5" />
                    Generate New Report
                  </button>
                </div>

                {/* Reports List */}
                {reportsQuery.isLoading && (
                  <div className="text-center py-12">
                    <ArrowPathIcon className="w-12 h-12 text-purple-500 animate-spin mx-auto mb-4" />
                    <p className="text-gray-600">Loading saved reports...</p>
                  </div>
                )}

                {/* Debug info */}
                {console.log('reportsQuery state:', {
                  isLoading: reportsQuery.isLoading,
                  isError: reportsQuery.isError,
                  data: reportsQuery.data,
                  dataLength: reportsQuery.data?.length,
                  isGeneratingReport
                })}

                {/* Report Generation Loading Indicator */}
                {isGeneratingReport && (
                  <div className="bg-purple-50 border border-purple-200 rounded-lg p-6">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <ArrowPathIcon className="w-8 h-8 text-purple-600 animate-spin" />
                        <div>
                          <p className="text-lg font-semibold text-purple-900">
                            Generating {selectedReportType === '90day' ? '90-day' : selectedReportType} report...
                          </p>
                          <p className="text-sm text-purple-700 mt-1">
                            Elapsed time: {formatTime(reportElapsedTime)} • Estimated: {
                              selectedReportType === 'weekly' ? '~30 seconds' :
                              selectedReportType === 'monthly' ? '~2 minutes' :
                              '~5 minutes'
                            }
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {reportsQuery.data && reportsQuery.data.length === 0 && !isGeneratingReport && (
                  <div className="text-center py-12 bg-gray-50 rounded-lg">
                    <DocumentTextIcon className="w-12 h-12 text-gray-400 mx-auto mb-2" />
                    <p className="text-gray-600">No saved reports yet. Generate your first report!</p>
                  </div>
                )}

                {reportsQuery.data && reportsQuery.data.length > 0 && (
                  <div className="grid grid-cols-1 gap-4">
                    {reportsQuery.data.map((report) => (
                      <div
                        key={report.id}
                        onClick={() => {
                          // Load this report's data into the query cache
                          queryClient.setQueryData(
                            ['proposal-followups', daysBack, noResponseDays, forceRefresh],
                            report.result
                          );
                          // Switch to unanswered tab to show the analysis
                          setSelectedTab('unanswered');
                          setHasStarted(true);
                        }}
                        className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 cursor-pointer hover:shadow-md hover:border-purple-300 transition-all"
                      >
                        <div className="flex justify-between items-start mb-4">
                          <div>
                            <h3 className="text-lg font-semibold text-gray-900">
                              {report.report_type === '90day' && '90-Day Report'}
                              {report.report_type === 'monthly' && 'Monthly Report'}
                              {report.report_type === 'weekly' && 'Weekly Report'}
                            </h3>
                            <p className="text-sm text-gray-600">
                              Period: {report.report_period} • Generated: {formatDate(report.created_at)}
                            </p>
                          </div>
                          <span className="px-3 py-1 text-sm font-medium rounded-full bg-purple-100 text-purple-800">
                            {report.report_type}
                          </span>
                        </div>

                        {/* Report Summary */}
                        <div className="grid grid-cols-3 gap-4 mb-4">
                          <div className="bg-orange-50 rounded-lg p-3">
                            <p className="text-xs text-orange-600 font-medium">Unanswered</p>
                            <p className="text-2xl font-bold text-orange-700">{report.result?.summary?.unanswered_count || 0}</p>
                          </div>
                          <div className="bg-blue-50 rounded-lg p-3">
                            <p className="text-xs text-blue-600 font-medium">Pending Proposals</p>
                            <p className="text-2xl font-bold text-blue-700">{report.result?.summary?.pending_proposals_count || 0}</p>
                          </div>
                          <div className="bg-purple-50 rounded-lg p-3">
                            <p className="text-xs text-purple-600 font-medium">Total</p>
                            <p className="text-2xl font-bold text-purple-700">{report.result?.summary?.total_count || 0}</p>
                          </div>
                        </div>

                        {/* Report Parameters */}
                        <div className="text-xs text-gray-500 space-x-4">
                          <span>Lookback: {report.parameters.days_back} days</span>
                          <span>•</span>
                          <span>No Response: {report.parameters.no_response_days} days</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Generate Report Modal */}
      {showGenerateReportModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Generate New Report</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Report Type
                </label>
                <select
                  value={selectedReportType}
                  onChange={(e) => setSelectedReportType(e.target.value as '90day' | 'monthly' | 'weekly')}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  <option value="weekly">Weekly Report (7 days)</option>
                  <option value="monthly">Monthly Report (30 days)</option>
                  <option value="90day">90-Day Report</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  No Response Threshold (days)
                </label>
                <input
                  type="number"
                  value={noResponseDays}
                  onChange={(e) => setNoResponseDays(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  min="1"
                  max="14"
                />
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowGenerateReportModal(false)}
                disabled={isGeneratingReport}
                className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  const estimatedTimes = {
                    weekly: 30,
                    monthly: 120,
                    '90day': 300
                  };
                  const estimatedSeconds = estimatedTimes[selectedReportType];

                  setIsGeneratingReport(true);
                  setReportGenerationStartTime(Date.now());
                  setShowGenerateReportModal(false);

                  try {
                    await toast.promise(
                      api.generateReport({
                        report_type: selectedReportType,
                        no_response_days: noResponseDays,
                        engage_email: 'automated.response@prezlab.com'
                      }),
                      {
                        loading: `Generating ${selectedReportType} report... (estimated ${Math.floor(estimatedSeconds / 60)}${estimatedSeconds >= 60 ? ` min` : ` sec`})`,
                        success: 'Report generated successfully!',
                        error: 'Failed to generate report'
                      }
                    );
                    await reportsQuery.refetch();
                  } catch (error) {
                    console.error('Error generating report:', error);
                  } finally {
                    setIsGeneratingReport(false);
                    setReportGenerationStartTime(null);
                  }
                }}
                disabled={isGeneratingReport}
                className="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Generate Report
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Draft Email Modal */}
      {showDraftModal && selectedThread && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-3xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Email Draft</h3>
                <p className="text-sm text-gray-600 mt-1">
                  To: {selectedThread.external_email} • Subject: {selectedThread.subject}
                </p>
              </div>
              <button
                onClick={() => {
                  setShowDraftModal(false);
                  setDraftEmail('');
                  setSelectedThread(null);
                  setEditPrompt('');
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
                <p className="text-gray-600">Generating draft email...</p>
              </div>
            )}

            {/* Draft Editor */}
            {!isGeneratingDraft && (
              <>
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Email Draft (editable)
                  </label>
                  <textarea
                    value={draftEmail}
                    onChange={(e) => setDraftEmail(e.target.value)}
                    rows={12}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md font-sans text-sm"
                    placeholder="Draft email will appear here..."
                  />
                </div>

                {/* AI Refinement */}
                <div className="mb-4 bg-gray-50 rounded-lg p-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    ✨ Refine with AI
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={editPrompt}
                      onChange={(e) => setEditPrompt(e.target.value)}
                      placeholder="e.g., Make it shorter, Add urgency, More professional..."
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm"
                      onKeyPress={(e) => {
                        if (e.key === 'Enter') {
                          handleRefineDraft();
                        }
                      }}
                    />
                    <button
                      onClick={handleRefineDraft}
                      disabled={isRefiningDraft || !editPrompt.trim()}
                      className="px-4 py-2 bg-purple-600 text-white text-sm rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                    >
                      {isRefiningDraft ? (
                        <>
                          <ArrowPathIcon className="w-4 h-4 animate-spin" />
                          Refining...
                        </>
                      ) : (
                        <>
                          <SparklesIcon className="w-4 h-4" />
                          Refine
                        </>
                      )}
                    </button>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    Tell the AI how to improve the draft
                  </p>
                </div>

                {/* Action Buttons */}
                <div className="flex gap-3">
                  <button
                    onClick={() => {
                      setShowDraftModal(false);
                      setDraftEmail('');
                      setSelectedThread(null);
                      setEditPrompt('');
                    }}
                    className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                  >
                    Cancel
                  </button>

                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(draftEmail);
                      toast.success('Draft copied to clipboard!');
                    }}
                    disabled={!draftEmail.trim()}
                    className="flex-1 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Copy to Clipboard
                  </button>

                  <button
                    onClick={handleSendEmail}
                    disabled={isSendingEmail || !draftEmail.trim()}
                    className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {isSendingEmail ? (
                      <>
                        <ArrowPathIcon className="w-4 h-4 animate-spin" />
                        Sending...
                      </>
                    ) : (
                      <>
                        <EnvelopeIcon className="w-4 h-4" />
                        Send Email
                      </>
                    )}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Assign Lead Modal */}
      {selectedLeadForAssignment && (
        <AssignLeadModal
          isOpen={assignModalOpen}
          onClose={() => {
            setAssignModalOpen(false);
            setSelectedLeadForAssignment(null);
          }}
          lead={{
            conversation_id: selectedLeadForAssignment.conversation_id,
            external_email: selectedLeadForAssignment.external_email,
            subject: selectedLeadForAssignment.subject,
            lead_data: selectedLeadForAssignment,
          }}
          users={mockUsers}
        />
      )}
    </div>
  );
};

export default ProposalFollowupsPage;
