import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import toast from 'react-hot-toast';
import {
  HeartIcon,
  TrashIcon,
  ClockIcon,
  UserCircleIcon,
  BuildingOfficeIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import api from '../utils/api';

interface SharedAnalysis {
  id: string;
  lead_id: number;
  title: string;
  analysis_data: Record<string, any>;
  created_by_user_id: number;
  created_at: string;
  lead_name?: string;
  company_name?: string;
}

const ReEngagePage: React.FC = () => {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  // Fetch shared analyses
  const { data: analyses = [], isLoading, refetch } = useQuery<SharedAnalysis[]>(
    'shared-analyses',
    async () => {
      const response = await api.get('/re-engage/analyses');
      return response.data;
    },
    {
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

  if (isLoading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="flex items-center gap-3 text-gray-600">
          <ArrowPathIcon className="h-6 w-6 animate-spin" />
          <span>Loading saved analyses...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Re-engage</h1>
            <p className="mt-2 text-sm text-gray-600">
              Saved lost lead analyses from your team. Review insights and plan re-engagement strategies.
            </p>
          </div>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
          >
            <ArrowPathIcon className="h-4 w-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
        <div className="overflow-hidden rounded-lg bg-white px-4 py-5 shadow sm:p-6">
          <dt className="truncate text-sm font-medium text-gray-500">Total Saved</dt>
          <dd className="mt-1 text-3xl font-semibold tracking-tight text-gray-900">
            {analyses.length}
          </dd>
        </div>
        <div className="overflow-hidden rounded-lg bg-white px-4 py-5 shadow sm:p-6">
          <dt className="truncate text-sm font-medium text-gray-500">This Week</dt>
          <dd className="mt-1 text-3xl font-semibold tracking-tight text-gray-900">
            {analyses.filter((a) => {
              const weekAgo = new Date();
              weekAgo.setDate(weekAgo.getDate() - 7);
              return new Date(a.created_at) > weekAgo;
            }).length}
          </dd>
        </div>
        <div className="overflow-hidden rounded-lg bg-white px-4 py-5 shadow sm:p-6">
          <dt className="truncate text-sm font-medium text-gray-500">Ready to Re-engage</dt>
          <dd className="mt-1 text-3xl font-semibold tracking-tight text-green-600">
            {analyses.length}
          </dd>
        </div>
      </div>

      {/* Analyses List */}
      {analyses.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-gray-300 bg-white p-12 text-center">
          <HeartIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No saved analyses</h3>
          <p className="mt-1 text-sm text-gray-500">
            When you save a lost lead analysis, it will appear here for the whole team to review.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {analyses.map((analysis) => (
            <div
              key={analysis.id}
              className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm transition-shadow hover:shadow-md"
            >
              {/* Header */}
              <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-gray-900">
                      {analysis.title || `Analysis #${analysis.id.slice(0, 8)}`}
                    </h3>
                    <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-gray-600">
                      {analysis.lead_name && (
                        <div className="flex items-center gap-1.5">
                          <UserCircleIcon className="h-4 w-4" />
                          <span>{analysis.lead_name}</span>
                        </div>
                      )}
                      {analysis.company_name && (
                        <div className="flex items-center gap-1.5">
                          <BuildingOfficeIcon className="h-4 w-4" />
                          <span>{analysis.company_name}</span>
                        </div>
                      )}
                      <div className="flex items-center gap-1.5">
                        <ClockIcon className="h-4 w-4" />
                        <span>{formatDate(analysis.created_at)}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setExpandedId(expandedId === analysis.id ? null : analysis.id)}
                      className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                    >
                      {expandedId === analysis.id ? 'Collapse' : 'View Details'}
                    </button>
                    <button
                      onClick={() => {
                        if (window.confirm('Are you sure you want to delete this analysis?')) {
                          deleteMutation.mutate(analysis.id);
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
              {expandedId === analysis.id && (
                <div className="space-y-6 px-6 py-6">
                  {/* Lead Info */}
                  {analysis.analysis_data.lead && (
                    <div>
                      <h4 className="text-sm font-semibold text-gray-900">Lead Information</h4>
                      <div className="mt-3 grid gap-3 text-sm lg:grid-cols-2">
                        {Object.entries(analysis.analysis_data.lead).map(([key, value]) => (
                          <div key={key} className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                            <div className="font-medium text-gray-700">{key}</div>
                            <div className="mt-1 text-gray-900">{String(value || 'N/A')}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Analysis */}
                  {analysis.analysis_data.analysis && (
                    <div>
                      <h4 className="text-sm font-semibold text-gray-900">AI Analysis</h4>
                      <div className="mt-3 space-y-3">
                        {Object.entries(analysis.analysis_data.analysis).map(([key, value]) => (
                          <div key={key} className="rounded-lg border border-blue-200 bg-blue-50 p-4">
                            <div className="font-medium text-blue-900">{key}</div>
                            <div className="mt-2 whitespace-pre-wrap text-sm text-blue-800">
                              {String(value)}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Internal Notes */}
                  {analysis.analysis_data.internal_notes &&
                    analysis.analysis_data.internal_notes.length > 0 && (
                      <div>
                        <h4 className="text-sm font-semibold text-gray-900">Internal Notes</h4>
                        <div className="mt-3 space-y-3">
                          {analysis.analysis_data.internal_notes.map((note: any, idx: number) => (
                            <div key={idx} className="rounded-lg border border-gray-200 bg-white p-4">
                              <div className="flex items-center justify-between text-xs text-gray-500">
                                <span>{note.author || 'Unknown'}</span>
                                <span>{note.formatted_date || note.date}</span>
                              </div>
                              <div className="mt-2 whitespace-pre-wrap text-sm text-gray-700">
                                {note.body}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                  {/* Emails */}
                  {analysis.analysis_data.emails && analysis.analysis_data.emails.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-gray-900">Email History</h4>
                      <div className="mt-3 space-y-3">
                        {analysis.analysis_data.emails.map((email: any, idx: number) => (
                          <div key={idx} className="rounded-lg border border-gray-200 bg-white p-4">
                            <div className="flex items-center justify-between text-xs text-gray-500">
                              <span>{email.author || 'Unknown'}</span>
                              <span>{email.formatted_date || email.date}</span>
                            </div>
                            {email.subject && (
                              <div className="mt-2 font-medium text-gray-900">{email.subject}</div>
                            )}
                            <div className="mt-2 whitespace-pre-wrap text-sm text-gray-700">
                              {email.body}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ReEngagePage;
