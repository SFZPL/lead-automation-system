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
  TrashIcon,
  ArrowDownTrayIcon,
  StarIcon,
  ChatBubbleLeftRightIcon,
} from '@heroicons/react/24/outline';
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid';
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
  web_link?: string;
  odoo_lead?: OdooLead | null;
  analysis?: ThreadAnalysis;
  classification?: EmailClassification;
  is_favorited?: boolean;
  last_internal_sender?: string;
  last_internal_sender_email?: string;
  last_internal_email_date?: string;
}

interface ProposalFollowupData {
  summary: ProposalFollowupSummary;
  unanswered: ProposalFollowupThread[];
  pending_proposals: ProposalFollowupThread[];
  filtered?: ProposalFollowupThread[];
}

interface SavedReport {
  id: string;  // UUID from Supabase
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
  const [selectedTab, setSelectedTab] = useState<'unanswered' | 'pending' | 'reports'>(() => {
    // Always restore from localStorage, even after Teams tab switch
    const stored = getStoredState('selectedTab', 'reports');
    return stored;
  });
  const [expandedThread, setExpandedThread] = useState<string | null>(() => getStoredState('expandedThread', null));
  const [hasStarted, setHasStarted] = useState<boolean>(true);
  const [startTime, setStartTime] = useState<number | null>(null);
  const [elapsedTime, setElapsedTime] = useState<number>(0);
  const [forceRefresh, setForceRefresh] = useState<boolean>(false);
  const [showLeadsOnly, setShowLeadsOnly] = useState<boolean>(() => getStoredState('showLeadsOnly', false));
  const [showFilteredEmails, setShowFilteredEmails] = useState<boolean>(() => getStoredState('showFilteredEmails', false));
  const [assignModalOpen, setAssignModalOpen] = useState<boolean>(false);
  const [selectedLeadForAssignment, setSelectedLeadForAssignment] = useState<ProposalFollowupThread | null>(null);
  const [showGenerateReportModal, setShowGenerateReportModal] = useState<boolean>(false);
  const [showDraftModal, setShowDraftModal] = useState<boolean>(false);
  const [selectedThread, setSelectedThread] = useState<ProposalFollowupThread | null>(null);
  const [showThreadUrlModal, setShowThreadUrlModal] = useState<boolean>(false);
  const [threadSearchUrl, setThreadSearchUrl] = useState<string>('');
  const [draftEmail, setDraftEmail] = useState<string>('');
  const [draftSubject, setDraftSubject] = useState<string>('');
  const [draftCc, setDraftCc] = useState<string>('engage@prezlab.com');
  const [editPrompt, setEditPrompt] = useState<string>('');
  const [isGeneratingDraft, setIsGeneratingDraft] = useState<boolean>(false);
  const [isRefiningDraft, setIsRefiningDraft] = useState<boolean>(false);
  const [isSendingEmail, setIsSendingEmail] = useState<boolean>(false);
  const [isGeneratingReport, setIsGeneratingReport] = useState<boolean>(false);
  const [reportGenerationStartTime, setReportGenerationStartTime] = useState<number | null>(null);
  const [showThreadViewerModal, setShowThreadViewerModal] = useState<boolean>(false);
  const [threadMessages, setThreadMessages] = useState<any[]>([]);
  const [isLoadingThread, setIsLoadingThread] = useState<boolean>(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<boolean>(false);
  const [reportToDelete, setReportToDelete] = useState<string | null>(null);
  const [expandedReport, setExpandedReport] = useState<string | null>(null);
  const [hasAutoExpanded, setHasAutoExpanded] = useState<boolean>(false);

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
      enabled: false, // Disabled - only use Saved Reports
      refetchOnWindowFocus: false,
      refetchOnMount: false,
      refetchOnReconnect: false,
      retry: 1,
      staleTime: Infinity,
      onSuccess: () => {
        if (!hasStarted) {
          setHasStarted(true);
        }
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
      refetchOnWindowFocus: true,
      staleTime: 10 * 1000, // 10 seconds - shorter to pick up completion changes quickly
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

  // Debug: Log reports query state
  React.useEffect(() => {
    console.log('reportsQuery state:', {
      isLoading: reportsQuery.isLoading,
      isError: reportsQuery.isError,
      data: reportsQuery.data,
      dataLength: reportsQuery.data?.length,
      isGeneratingReport,
      selectedTab
    });
  }, [reportsQuery.isLoading, reportsQuery.data, isGeneratingReport, selectedTab]);

  React.useEffect(() => {
    localStorage.setItem('proposalFollowups_showFilteredEmails', JSON.stringify(showFilteredEmails));
  }, [showFilteredEmails]);

  // Auto-expand the latest saved report on load
  React.useEffect(() => {
    if (!hasAutoExpanded && reportsQuery.data && reportsQuery.data.length > 0 && selectedTab === 'reports') {
      const latestReport = reportsQuery.data[0]; // Reports are sorted by created_at desc
      setExpandedReport(latestReport.id);
      setHasAutoExpanded(true);
    }
  }, [reportsQuery.data, selectedTab, hasAutoExpanded]);

  // On mount/refresh, check if we have cached data and validate completed threads are filtered
  React.useEffect(() => {
    const cachedData = queryClient.getQueryData<ProposalFollowupData>(['proposal-followups', daysBack, noResponseDays, forceRefresh]);

    if (cachedData && (cachedData.unanswered.length > 0 || cachedData.pending_proposals.length > 0)) {
      // Fetch fresh completions list from backend to ensure cache is accurate
      api.get('/proposal-followups/completions').then((response) => {
        const completedIds = new Set(response.data.map((c: any) => c.conversation_id));

        // Check if any threads in cache are now completed
        const hasStaleData =
          cachedData.unanswered.some(t => completedIds.has(t.conversation_id)) ||
          cachedData.pending_proposals.some(t => completedIds.has(t.conversation_id));

        if (hasStaleData) {
          // Cache has completed threads, filter them out
          const updatedData = {
            ...cachedData,
            unanswered: cachedData.unanswered.filter(t => !completedIds.has(t.conversation_id)),
            pending_proposals: cachedData.pending_proposals.filter(t => !completedIds.has(t.conversation_id)),
          };
          updatedData.summary.unanswered_count = updatedData.unanswered.length;
          updatedData.summary.pending_proposals_count = updatedData.pending_proposals.length;
          updatedData.summary.total_count = updatedData.unanswered.length + updatedData.pending_proposals.length;

          queryClient.setQueryData(['proposal-followups', daysBack, noResponseDays, forceRefresh], updatedData);
        }
      }).catch(err => {
        console.error('Error fetching completions:', err);
      });
    }
  }, []); // Only run once on mount

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
    setDraftSubject(`Re: ${thread.subject}`);
    setDraftCc('engage@prezlab.com');
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
    if (!selectedThread || !draftEmail.trim() || !draftSubject.trim()) {
      toast.error('Please fill in subject and email body');
      return;
    }

    setIsSendingEmail(true);
    try {
      await api.sendFollowupEmail({
        conversation_id: selectedThread.conversation_id,
        draft_body: draftEmail,
        subject: draftSubject
      });
      toast.success('Email sent successfully and marked as complete!');
      setShowDraftModal(false);
      setDraftEmail('');
      setDraftSubject('');
      setDraftCc('engage@prezlab.com');
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
      const response = await api.markFollowupComplete({
        thread_id: thread.conversation_id,
        conversation_id: thread.conversation_id,
        notes: 'Manually marked as complete'
      });

      // Check if already completed
      if (response.data?.message) {
        toast.success(response.data.message);
      } else {
        toast.success('Follow-up marked as complete!');
      }

      // Get current cached data
      const currentData = queryClient.getQueryData<ProposalFollowupData>(['proposal-followups', daysBack, noResponseDays, forceRefresh]);

      if (currentData) {
        // Remove the thread from the cached data immediately
        const updatedData = {
          ...currentData,
          unanswered: currentData.unanswered.filter(t => t.conversation_id !== thread.conversation_id),
          pending_proposals: currentData.pending_proposals.filter(t => t.conversation_id !== thread.conversation_id),
          summary: {
            ...currentData.summary,
            unanswered_count: currentData.unanswered.filter(t => t.conversation_id !== thread.conversation_id).length,
            pending_proposals_count: currentData.pending_proposals.filter(t => t.conversation_id !== thread.conversation_id).length,
          }
        };
        updatedData.summary.total_count = updatedData.summary.unanswered_count + updatedData.summary.pending_proposals_count;

        // Update the cache with the filtered data
        queryClient.setQueryData(['proposal-followups', daysBack, noResponseDays, forceRefresh], updatedData);
      }

      // Invalidate saved reports so they reload
      await queryClient.invalidateQueries(['saved-reports']);
      await reportsQuery.refetch();
    } catch (error) {
      console.error('Error marking complete:', error);
      toast.error('Failed to mark as complete');
    }
  };

  const handleToggleFavorite = async (thread: ProposalFollowupThread) => {
    try {
      if (thread.is_favorited) {
        await api.unfavoriteFollowup(thread.conversation_id);
        toast.success('Removed from favorites');
      } else {
        await api.favoriteFollowup({
          thread_id: thread.conversation_id,
          conversation_id: thread.conversation_id
        });
        toast.success('Added to favorites');
      }

      // Invalidate and refetch to get updated list
      await queryClient.invalidateQueries(['proposal-followups', daysBack, noResponseDays, false]);
      await followupsQuery.refetch();
    } catch (error) {
      console.error('Error toggling favorite:', error);
      toast.error('Failed to update favorite');
    }
  };

  const handleViewThread = async (thread: ProposalFollowupThread) => {
    setSelectedThread(thread);
    setIsLoadingThread(true);
    setShowThreadViewerModal(true);
    setThreadMessages([]);

    try {
      const response = await api.get(`/outlook/conversation/${thread.conversation_id}`);
      setThreadMessages(response.data.messages || []);
    } catch (error: any) {
      console.error('Error fetching thread:', error);
      if (error.response?.status === 401) {
        toast.error('Please authenticate your Outlook account in Settings');
      } else {
        toast.error('Failed to load thread messages');
      }
    } finally {
      setIsLoadingThread(false);
    }
  };

  const handleOpenInOutlook = (thread: ProposalFollowupThread) => {
    // Extract core subject for search (remove RE:, FW:, FYI: prefixes and clean up)
    let cleanSubject = thread.subject
      .replace(/^(RE:|FW:|FWD:|For Your Information:)\s*/gi, '')
      .trim();

    // Take only first 50 chars to avoid overly specific searches
    if (cleanSubject.length > 50) {
      cleanSubject = cleanSubject.substring(0, 50);
    }

    // Build search query - just search by subject keywords without quotes for better matching
    const searchQuery = encodeURIComponent(`${cleanSubject} from:engage@prezlab.com`);

    // Use general Outlook mail search
    const outlookUrl = `https://outlook.office.com/mail/?search=${searchQuery}`;

    // Open in new tab
    window.open(outlookUrl, '_blank');
    toast.success('Searching for thread in Outlook...');
  };

  const handleDeleteReport = async (reportId: string, event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent triggering the card click
    setReportToDelete(reportId);
    setShowDeleteConfirm(true);
  };

  const confirmDelete = async () => {
    if (!reportToDelete) return;

    try {
      await api.deleteReport(reportToDelete);
      toast.success('Report deleted successfully!');
      setShowDeleteConfirm(false);
      setReportToDelete(null);
      // Refresh the reports list
      reportsQuery.refetch();
    } catch (error) {
      console.error('Error deleting report:', error);
      toast.error('Failed to delete report');
    }
  };

  const handleSendToTeams = async (reportData: any, event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent triggering the card click

    // Teams chat ID from the provided URL
    // https://teams.microsoft.com/l/chat/19:e53c2cecd4aa4581b6f417a95c0116df@thread.v2/conversations
    const chatId = '19:e53c2cecd4aa4581b6f417a95c0116df@thread.v2';

    try {
      const loadingToast = toast.loading('Sending report to Teams...');

      await api.sendReportToTeams({
        chat_id: chatId,
        report_data: reportData
      });

      toast.dismiss(loadingToast);
      toast.success('Report sent to Teams successfully!');
    } catch (error: any) {
      console.error('Error sending to Teams:', error);
      if (error.response?.status === 401) {
        toast.error('Please connect your Microsoft account in Settings first');
      } else {
        toast.error('Failed to send report to Teams');
      }
    }
  };

  const handleExportReport = async (reportId: string, event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent triggering the card click

    try {
      toast.loading('Generating PDF report...');

      const response = await api.exportReport(reportId);

      // Create blob from response
      const blob = new Blob([response.data], { type: 'application/pdf' });

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `follow-up-report-${reportId}.pdf`;
      document.body.appendChild(link);
      link.click();

      // Cleanup
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      toast.dismiss();
      toast.success('Report exported successfully!');
    } catch (error) {
      console.error('Error exporting report:', error);
      toast.dismiss();
      toast.error('Failed to export report');
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
              {thread.last_internal_sender && (
                <div className="flex items-center gap-1">
                  <UserCircleIcon className="w-4 h-4 text-purple-600" />
                  <span className="text-xs text-purple-700 font-medium">Last from: {thread.last_internal_sender}</span>
                </div>
              )}
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
                <div>Value: AED {thread.odoo_lead.expected_revenue.toLocaleString()}</div>
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
            onClick={() => handleToggleFavorite(thread)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              thread.is_favorited
                ? 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
            title={thread.is_favorited ? 'Remove from favorites' : 'Add to favorites'}
          >
            {thread.is_favorited ? (
              <StarIconSolid className="w-4 h-4 text-yellow-500" />
            ) : (
              <StarIcon className="w-4 h-4" />
            )}
            {thread.is_favorited ? 'Favorited' : 'Favorite'}
          </button>

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

          <button
            onClick={() => handleOpenInOutlook(thread)}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
            title="Open in Outlook with search"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M7.88 12.04q0 .45-.11.87-.1.41-.33.74-.22.33-.58.52-.37.2-.87.2t-.85-.2q-.35-.21-.57-.55-.22-.33-.33-.75-.1-.42-.1-.86t.1-.87q.1-.43.34-.76.22-.34.59-.54.36-.2.87-.2t.86.2q.35.21.57.55.22.34.31.77.1.43.1.88zM24 12v9.38q0 .46-.33.8-.33.32-.8.32H7.13q-.46 0-.8-.33-.32-.33-.32-.8V18H1.6q-.33 0-.57-.24-.23-.23-.23-.57V6.8q0-.33.22-.57.22-.23.58-.23h4.5v-.1q0-.46.33-.8.33-.32.8-.32h12.87q.47 0 .8.33.34.33.34.8z"/>
            </svg>
            Open in Outlook
          </button>

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
        {/* Removed "Ready to Analyze" section - now defaults to Saved Reports tab */}

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
                Estimated time: up to 20 minutes
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

        {/* Unanswered and Pending tabs require followupsQuery.data */}
        {followupsQuery.data && (selectedTab === 'unanswered' || selectedTab === 'pending') && (
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

          </div>
        )}

        {/* Reports tab is independent of followupsQuery */}
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

            {/* Report Generation Loading Indicator */}
            {isGeneratingReport && (
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <ArrowPathIcon className="w-8 h-8 text-purple-600 animate-spin" />
                    <div>
                      <p className="text-lg font-semibold text-purple-900">
                        Generating complete report...
                      </p>
                      <p className="text-sm text-purple-700 mt-1">
                        Elapsed time: {formatTime(reportElapsedTime)} • Estimated: up to 20 minutes
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
                {reportsQuery.data.map((report) => {
                  const isExpanded = expandedReport === report.id;
                  return (
                  <div
                    key={report.id}
                    className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden transition-all"
                  >
                    <div
                      onClick={() => {
                        if (isExpanded) {
                          setExpandedReport(null);
                        } else {
                          // Load this report's data into the query cache
                          queryClient.setQueryData(
                            ['proposal-followups', daysBack, noResponseDays, forceRefresh],
                            report.result
                          );
                          setExpandedReport(report.id);
                          setHasStarted(true);
                        }
                      }}
                      className="p-6 cursor-pointer hover:bg-gray-50 transition-all"
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
                      <div className="flex items-center gap-2">
                        <span className="px-3 py-1 text-sm font-medium rounded-full bg-purple-100 text-purple-800">
                          {report.report_type}
                        </span>
                        <button
                          onClick={(e) => handleSendToTeams(report.result, e)}
                          className="p-2 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                          title="Send to Teams"
                        >
                          <ChatBubbleLeftRightIcon className="w-5 h-5" />
                        </button>
                        <button
                          onClick={(e) => handleExportReport(report.id, e)}
                          className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                          title="Export PDF"
                        >
                          <ArrowDownTrayIcon className="w-5 h-5" />
                        </button>
                        <button
                          onClick={(e) => handleDeleteReport(report.id, e)}
                          className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          title="Delete report"
                        >
                          <TrashIcon className="w-5 h-5" />
                        </button>
                      </div>
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

                    {/* Expanded Content */}
                    {isExpanded && (
                      <div className="border-t border-gray-200 p-6 bg-gray-50">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            queryClient.setQueryData(
                              ['proposal-followups', daysBack, noResponseDays, forceRefresh],
                              report.result
                            );
                            setSelectedTab('unanswered');
                          }}
                          className="w-full px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-medium transition-colors"
                        >
                          View Full Report Details
                        </button>
                      </div>
                    )}
                  </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Generate Report Modal */}
      {showGenerateReportModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Generate Complete Follow-up Report</h3>

            <div className="space-y-4">
              <p className="text-sm text-gray-600">
                This will analyze all emails from engage@prezlab.com to identify unanswered emails and pending proposals.
              </p>
              <p className="text-sm text-gray-500 italic">
                Estimated time: up to 20 minutes
              </p>
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
                  setIsGeneratingReport(true);
                  setReportGenerationStartTime(Date.now());
                  setShowGenerateReportModal(false);

                  try {
                    await toast.promise(
                      api.generateReport({
                        report_type: 'complete',
                        no_response_days: noResponseDays,
                        engage_email: 'automated.response@prezlab.com'
                      }),
                      {
                        loading: 'Generating complete report... (estimated up to 20 minutes)',
                        success: 'Report generated successfully!',
                        error: 'Failed to generate report'
                      }
                    );
                    // Invalidate and refetch reports query to show the new report
                    await queryClient.invalidateQueries(['saved-reports']);
                    // Switch to reports tab to view the new report
                    setSelectedTab('reports');
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
                  setDraftSubject('');
                  setDraftCc('engage@prezlab.com');
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
                      setDraftSubject('');
                      setDraftCc('engage@prezlab.com');
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
                    disabled={isSendingEmail || !draftEmail.trim() || !draftSubject.trim()}
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

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Delete Report</h3>
            <p className="text-gray-600 mb-6">
              Are you sure you want to delete this report? This action cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setReportToDelete(null);
                }}
                className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Thread Viewer Modal */}
      {showThreadViewerModal && selectedThread && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col">
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">Email Thread</h3>
                  <p className="text-sm text-gray-600 mt-1">{selectedThread.subject}</p>
                  <p className="text-xs text-gray-500 mt-1">From: {selectedThread.external_email}</p>
                </div>
                <button
                  onClick={() => setShowThreadViewerModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <XCircleIcon className="w-6 h-6" />
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {isLoadingThread ? (
                <div className="flex items-center justify-center py-12">
                  <ArrowPathIcon className="w-8 h-8 animate-spin text-blue-600" />
                  <span className="ml-2 text-gray-600">Loading messages...</span>
                </div>
              ) : threadMessages.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  No messages found in this thread
                </div>
              ) : (
                threadMessages.map((message, index) => (
                  <div
                    key={message.id}
                    className="bg-gray-50 rounded-lg p-4 border border-gray-200"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <div className="font-semibold text-gray-900">
                          {message.from.name}
                        </div>
                        <div className="text-sm text-gray-600">{message.from.email}</div>
                      </div>
                      <div className="text-xs text-gray-500">
                        {new Date(message.receivedDateTime).toLocaleString()}
                      </div>
                    </div>

                    {message.to && message.to.length > 0 && (
                      <div className="text-xs text-gray-600 mb-2">
                        <span className="font-medium">To:</span>{' '}
                        {message.to.map((r: any) => r.email).join(', ')}
                      </div>
                    )}

                    {message.cc && message.cc.length > 0 && (
                      <div className="text-xs text-gray-600 mb-2">
                        <span className="font-medium">CC:</span>{' '}
                        {message.cc.map((r: any) => r.email).join(', ')}
                      </div>
                    )}

                    <div className="mt-3 text-sm text-gray-700">
                      {message.body ? (
                        <div
                          className="prose prose-sm max-w-none"
                          dangerouslySetInnerHTML={{ __html: message.body }}
                        />
                      ) : (
                        <div className="text-gray-500 italic">{message.bodyPreview}</div>
                      )}
                    </div>

                    {message.hasAttachments && (
                      <div className="mt-2 text-xs text-gray-500">
                        📎 Has attachments
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>

            <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={() => setShowThreadViewerModal(false)}
                className="px-6 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors font-medium"
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

export default ProposalFollowupsPage;
