import React, { useState } from 'react';
import { useQuery } from 'react-query';
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
} from '@heroicons/react/24/outline';
import api from '../utils/api';

interface ProposalFollowupSummary {
  unanswered_count: number;
  pending_proposals_count: number;
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
}

const ProposalFollowupsPage: React.FC = () => {
  const [daysBack, setDaysBack] = useState<number>(3);
  const [noResponseDays, setNoResponseDays] = useState<number>(3);
  const [selectedTab, setSelectedTab] = useState<'unanswered' | 'pending'>('unanswered');
  const [expandedThread, setExpandedThread] = useState<string | null>(null);
  const [hasStarted, setHasStarted] = useState<boolean>(false);
  const [startTime, setStartTime] = useState<number | null>(null);
  const [elapsedTime, setElapsedTime] = useState<number>(0);
  const [forceRefresh, setForceRefresh] = useState<boolean>(false);
  const [showLeadsOnly, setShowLeadsOnly] = useState<boolean>(false);

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

            {/* Draft Email Toggle */}
            {thread.analysis.draft_email && (
              <div>
                <button
                  onClick={() => setExpandedThread(isExpanded ? null : thread.conversation_id)}
                  className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 font-medium"
                >
                  <DocumentTextIcon className="w-4 h-4" />
                  {isExpanded ? 'Hide' : 'Show'} Draft Email
                </button>

                {isExpanded && (
                  <div className="mt-2 bg-gray-50 rounded-md p-3 border border-gray-200">
                    <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans">
                      {thread.analysis.draft_email}
                    </pre>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(thread.analysis!.draft_email);
                        toast.success('Draft email copied to clipboard!');
                      }}
                      className="mt-2 px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700"
                    >
                      Copy to Clipboard
                    </button>
                  </div>
                )}
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
      {hasStarted && (
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
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
          </nav>
        </div>
      )}

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
          </div>
        )}
      </div>
    </div>
  );
};

export default ProposalFollowupsPage;
