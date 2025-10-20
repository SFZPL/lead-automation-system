import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import toast from 'react-hot-toast';
import {
  InboxIcon,
  PaperAirplaneIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  UserCircleIcon,
  EnvelopeIcon,
} from '@heroicons/react/24/outline';
import api from '../utils/api';

interface LeadAssignment {
  id: string;
  conversation_id: string;
  external_email: string;
  subject: string;
  assigned_from_user_id: number;
  assigned_to_user_id: number;
  lead_data: any;
  status: 'pending' | 'accepted' | 'completed' | 'rejected';
  notes?: string;
  assigned_at: string;
  updated_at: string;
  completed_at?: string;
}

const AssignedLeadsPage: React.FC = () => {
  const [selectedTab, setSelectedTab] = useState<'received' | 'sent'>('received');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [expandedAssignment, setExpandedAssignment] = useState<string | null>(null);
  const [actionNotes, setActionNotes] = useState<{ [key: string]: string }>({});
  const queryClient = useQueryClient();

  // Fetch received assignments
  const receivedQuery = useQuery(
    ['received-assignments', statusFilter === 'all' ? undefined : statusFilter],
    async () => {
      const response = await api.getReceivedAssignments({
        status: statusFilter === 'all' ? undefined : statusFilter as any,
      });
      return response.data;
    },
    { enabled: selectedTab === 'received' }
  );

  // Fetch sent assignments
  const sentQuery = useQuery(
    ['sent-assignments', statusFilter === 'all' ? undefined : statusFilter],
    async () => {
      const response = await api.getSentAssignments({
        status: statusFilter === 'all' ? undefined : statusFilter as any,
      });
      return response.data;
    },
    { enabled: selectedTab === 'sent' }
  );

  // Update assignment mutation
  const updateMutation = useMutation(
    async ({ assignmentId, status, notes }: { assignmentId: string; status: 'accepted' | 'completed' | 'rejected'; notes?: string }) => {
      return api.updateAssignment(assignmentId, { status, notes });
    },
    {
      onSuccess: (_, variables) => {
        toast.success(`Lead ${variables.status}!`);
        queryClient.invalidateQueries('received-assignments');
        queryClient.invalidateQueries('sent-assignments');
        setActionNotes({});
      },
      onError: (error: any) => {
        toast.error(error?.response?.data?.detail || 'Failed to update assignment');
      },
    }
  );

  const handleUpdateAssignment = (assignmentId: string, status: 'accepted' | 'completed' | 'rejected') => {
    const notes = actionNotes[assignmentId];
    updateMutation.mutate({ assignmentId, status, notes });
  };

  const activeQuery = selectedTab === 'received' ? receivedQuery : sentQuery;
  const assignments: LeadAssignment[] = activeQuery.data?.assignments || [];

  const getStatusBadge = (status: string) => {
    const styles = {
      pending: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      accepted: 'bg-blue-100 text-blue-800 border-blue-200',
      completed: 'bg-green-100 text-green-800 border-green-200',
      rejected: 'bg-red-100 text-red-800 border-red-200',
    };

    const icons = {
      pending: ClockIcon,
      accepted: CheckCircleIcon,
      completed: CheckCircleIcon,
      rejected: XCircleIcon,
    };

    const Icon = icons[status as keyof typeof icons];

    return (
      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium border ${styles[status as keyof typeof styles]}`}>
        <Icon className="w-3 h-3" />
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffHours = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60));

    if (diffHours < 24) {
      return `${diffHours}h ago`;
    } else {
      const diffDays = Math.floor(diffHours / 24);
      return `${diffDays}d ago`;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Lead Assignments</h1>
          <p className="text-gray-600">Manage leads assigned to you and track assignments you've sent</p>
        </div>

        {/* Tabs */}
        <div className="mb-6 border-b border-gray-200">
          <div className="flex gap-4">
            <button
              onClick={() => setSelectedTab('received')}
              className={`pb-3 px-4 flex items-center gap-2 font-medium transition-colors border-b-2 ${
                selectedTab === 'received'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
            >
              <InboxIcon className="w-5 h-5" />
              Received ({receivedQuery.data?.count || 0})
            </button>
            <button
              onClick={() => setSelectedTab('sent')}
              className={`pb-3 px-4 flex items-center gap-2 font-medium transition-colors border-b-2 ${
                selectedTab === 'sent'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
            >
              <PaperAirplaneIcon className="w-5 h-5" />
              Sent ({sentQuery.data?.count || 0})
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="mb-6 flex gap-4 items-center">
          <label className="text-sm font-medium text-gray-700">Filter by status:</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="all">All</option>
            <option value="pending">Pending</option>
            <option value="accepted">Accepted</option>
            <option value="completed">Completed</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>

        {/* Loading/Error States */}
        {activeQuery.isLoading && (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading assignments...</p>
          </div>
        )}

        {activeQuery.isError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
            Error loading assignments. Please try again.
          </div>
        )}

        {/* Assignments List */}
        {activeQuery.isSuccess && assignments.length === 0 && (
          <div className="text-center py-12 bg-white rounded-lg shadow">
            <InboxIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">No assignments found</p>
          </div>
        )}

        {activeQuery.isSuccess && assignments.length > 0 && (
          <div className="space-y-4">
            {assignments.map((assignment) => (
              <div key={assignment.id} className="bg-white rounded-lg shadow hover:shadow-md transition-shadow">
                {/* Assignment Header */}
                <div
                  className="p-4 cursor-pointer"
                  onClick={() => setExpandedAssignment(expandedAssignment === assignment.id ? null : assignment.id)}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <h3 className="font-semibold text-gray-900 mb-1">{assignment.subject}</h3>
                      <div className="flex items-center gap-4 text-sm text-gray-600">
                        <span className="flex items-center gap-1">
                          <EnvelopeIcon className="w-4 h-4" />
                          {assignment.external_email}
                        </span>
                        <span className="flex items-center gap-1">
                          <ClockIcon className="w-4 h-4" />
                          {formatDate(assignment.assigned_at)}
                        </span>
                      </div>
                    </div>
                    <div>{getStatusBadge(assignment.status)}</div>
                  </div>

                  {assignment.notes && (
                    <p className="text-sm text-gray-600 italic mt-2">&quot;{assignment.notes}&quot;</p>
                  )}
                </div>

                {/* Expanded Details */}
                {expandedAssignment === assignment.id && (
                  <div className="border-t border-gray-200 p-4 bg-gray-50">
                    {/* Lead Data Preview */}
                    {assignment.lead_data && (
                      <div className="mb-4">
                        <h4 className="text-sm font-medium text-gray-700 mb-2">Lead Details:</h4>
                        <div className="bg-white rounded p-3 text-sm">
                          <pre className="whitespace-pre-wrap text-gray-600 max-h-40 overflow-y-auto">
                            {JSON.stringify(assignment.lead_data, null, 2)}
                          </pre>
                        </div>
                      </div>
                    )}

                    {/* Actions for Received Assignments */}
                    {selectedTab === 'received' && assignment.status === 'pending' && (
                      <div className="space-y-3">
                        <textarea
                          placeholder="Add notes (optional)..."
                          value={actionNotes[assignment.id] || ''}
                          onChange={(e) => setActionNotes({ ...actionNotes, [assignment.id]: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                          rows={2}
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleUpdateAssignment(assignment.id, 'accepted')}
                            disabled={updateMutation.isLoading}
                            className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                          >
                            Accept
                          </button>
                          <button
                            onClick={() => handleUpdateAssignment(assignment.id, 'rejected')}
                            disabled={updateMutation.isLoading}
                            className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
                          >
                            Reject
                          </button>
                        </div>
                      </div>
                    )}

                    {selectedTab === 'received' && assignment.status === 'accepted' && (
                      <div className="space-y-3">
                        <textarea
                          placeholder="Add completion notes (optional)..."
                          value={actionNotes[assignment.id] || ''}
                          onChange={(e) => setActionNotes({ ...actionNotes, [assignment.id]: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                          rows={2}
                        />
                        <button
                          onClick={() => handleUpdateAssignment(assignment.id, 'completed')}
                          disabled={updateMutation.isLoading}
                          className="w-full px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50"
                        >
                          Mark as Completed
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default AssignedLeadsPage;
