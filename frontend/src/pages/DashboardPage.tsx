import React from 'react';
import { useQuery } from 'react-query';
import { Link } from 'react-router-dom';
import {
  ChartBarIcon,
  EnvelopeIcon,
  ClipboardDocumentListIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';
import api from '../utils/api';

interface DashboardSummary {
  high_priority_count: number;
  high_priority_items: Array<{
    type: string;
    subject: string;
    external_email: string;
    days_waiting: number;
    odoo_lead?: any;
    source: string;
  }>;
  stats: {
    unanswered_emails: number;
    pending_proposals: number;
    lost_leads: number;
    unenriched_leads: number;
    enriched_today?: number; // Keep for backward compatibility
    call_flows_generated?: number;
    last_updated?: string;
  };
  recent_activity: Array<{
    type: string;
    description: string;
    time: string;
    subject: string;
  }>;
}

const DashboardPage: React.FC = () => {
  const dashboardQuery = useQuery(
    ['dashboard-summary'],
    async () => {
      const response = await api.getDashboardSummary();
      return response.data as DashboardSummary;
    },
    {
      refetchOnWindowFocus: false,
      refetchInterval: 60000, // Refresh every minute
    }
  );

  const formatTimeAgo = (isoTime: string) => {
    if (!isoTime) return 'Unknown time';
    const date = new Date(isoTime);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
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

  const getUrgencyColor = (daysWaiting: number) => {
    if (daysWaiting >= 5) return 'text-red-600 bg-red-50';
    if (daysWaiting >= 3) return 'text-yellow-600 bg-yellow-50';
    return 'text-green-600 bg-green-50';
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'email':
        return <EnvelopeIcon className="h-5 w-5" />;
      case 'proposal':
        return <ClipboardDocumentListIcon className="h-5 w-5" />;
      case 'call':
        return <ClockIcon className="h-5 w-5" />;
      default:
        return <EnvelopeIcon className="h-5 w-5" />;
    }
  };

  if (dashboardQuery.isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (dashboardQuery.error) {
    return (
      <div className="rounded-md bg-red-50 p-4">
        <div className="flex">
          <ExclamationTriangleIcon className="h-5 w-5 text-red-400" />
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">Error loading dashboard</h3>
            <p className="mt-2 text-sm text-red-700">
              {dashboardQuery.error instanceof Error ? dashboardQuery.error.message : 'Unknown error'}
            </p>
          </div>
        </div>
      </div>
    );
  }

  const data = dashboardQuery.data!;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-6">
        {/* Welcome Header */}
        <div className="bg-white shadow rounded-lg p-6">
        <h1 className="text-2xl font-bold text-gray-900">Welcome back! 👋</h1>
        <p className="mt-1 text-sm text-gray-500">
          Here's what needs your attention today
        </p>
      </div>

      {/* High Priority Section */}
      {data.high_priority_count > 0 ? (
        <div className="bg-red-50 border-l-4 border-red-400 p-6 rounded-lg">
          <div className="flex items-start">
            <ExclamationTriangleIcon className="h-6 w-6 text-red-400 mt-0.5" />
            <div className="ml-3 flex-1">
              <h3 className="text-lg font-medium text-red-800">
                🔴 High Priority ({data.high_priority_count} {data.high_priority_count === 1 ? 'item' : 'items'})
              </h3>
              <div className="mt-4 space-y-3">
                {data.high_priority_items.map((item, index) => (
                  <div
                    key={index}
                    className="bg-white rounded-lg p-4 shadow-sm border border-red-200"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start space-x-3 flex-1">
                        <div className="flex-shrink-0 mt-1">
                          {getTypeIcon(item.type)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 truncate">
                            {item.subject || 'No subject'}
                          </p>
                          <p className="text-sm text-gray-500 mt-1">
                            From: {item.external_email}
                          </p>
                          {item.odoo_lead && (
                            <p className="text-xs text-gray-400 mt-1">
                              Lead: {item.odoo_lead.name || 'Unknown'}
                              {item.odoo_lead.expected_revenue && (
                                <span className="ml-2 text-green-600 font-medium">
                                  AED {item.odoo_lead.expected_revenue.toLocaleString()}
                                </span>
                              )}
                            </p>
                          )}
                        </div>
                      </div>
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getUrgencyColor(item.days_waiting)}`}>
                        {item.days_waiting} days
                      </span>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4">
                <Link
                  to="/followups"
                  className="text-sm font-medium text-red-700 hover:text-red-600"
                >
                  View All Follow-ups →
                </Link>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-green-50 border-l-4 border-green-400 p-6 rounded-lg">
          <div className="flex items-center">
            <CheckCircleIcon className="h-6 w-6 text-green-400" />
            <p className="ml-3 text-sm text-green-700">
              No high priority items! You're all caught up. Great job! 🎉
            </p>
          </div>
        </div>
      )}

      {/* Stats Cards */}
      <div>
        <h2 className="text-lg font-medium text-gray-900 mb-4">📊 Quick Stats</h2>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {/* Unanswered Emails */}
          <a
            href="/proposal-followups"
            className="bg-white overflow-hidden shadow rounded-lg hover:shadow-md transition-shadow"
          >
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <EnvelopeIcon className="h-6 w-6 text-orange-600" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">
                      Unanswered Emails
                    </dt>
                    <dd className="text-3xl font-semibold text-gray-900">
                      {data.stats.unanswered_emails}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
            <div className="bg-gray-50 px-5 py-3">
              <div className="text-sm">
                <span className="font-medium text-indigo-600 hover:text-indigo-500">
                  View details →
                </span>
              </div>
            </div>
          </a>

          {/* Pending Proposals */}
          <a
            href="/proposal-followups"
            className="bg-white overflow-hidden shadow rounded-lg hover:shadow-md transition-shadow"
          >
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <ClipboardDocumentListIcon className="h-6 w-6 text-blue-600" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">
                      Pending Proposals
                    </dt>
                    <dd className="text-3xl font-semibold text-gray-900">
                      {data.stats.pending_proposals}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
            <div className="bg-gray-50 px-5 py-3">
              <div className="text-sm">
                <span className="font-medium text-indigo-600 hover:text-indigo-500">
                  View details →
                </span>
              </div>
            </div>
          </a>

          {/* Lost Leads */}
          <a
            href="/lost-leads"
            className="bg-white overflow-hidden shadow rounded-lg hover:shadow-md transition-shadow"
          >
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <ExclamationTriangleIcon className="h-6 w-6 text-red-600" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">
                      Lost Leads
                    </dt>
                    <dd className="text-3xl font-semibold text-gray-900">
                      {data.stats.lost_leads}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
            <div className="bg-gray-50 px-5 py-3">
              <div className="text-sm">
                <span className="font-medium text-indigo-600 hover:text-indigo-500">
                  View analysis →
                </span>
              </div>
            </div>
          </a>

          {/* Unenriched Leads */}
          <a
            href="/perplexity"
            className="bg-white overflow-hidden shadow rounded-lg hover:shadow-md transition-shadow"
          >
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <ChartBarIcon className="h-6 w-6 text-yellow-600" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">
                      Unenriched Leads
                    </dt>
                    <dd className="text-3xl font-semibold text-gray-900">
                      {data.stats.unenriched_leads}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
            <div className="bg-gray-50 px-5 py-3">
              <div className="text-sm">
                <span className="font-medium text-indigo-600 hover:text-indigo-500">
                  View enrichment →
                </span>
              </div>
            </div>
          </a>
        </div>
        {data.stats.last_updated && (
          <p className="text-sm text-gray-500 mt-3 text-center">
            Last updated: {formatLastUpdated(data.stats.last_updated)}
          </p>
        )}
      </div>

      {/* Recent Activity */}
      {data.recent_activity.length > 0 && (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">📋 Recent Activity</h2>
          <div className="flow-root">
            <ul role="list" className="-mb-8">
              {data.recent_activity.map((activity, index) => (
                <li key={index}>
                  <div className="relative pb-8">
                    {index !== data.recent_activity.length - 1 && (
                      <span
                        className="absolute top-4 left-4 -ml-px h-full w-0.5 bg-gray-200"
                        aria-hidden="true"
                      />
                    )}
                    <div className="relative flex space-x-3">
                      <div>
                        <span className="h-8 w-8 rounded-full bg-indigo-500 flex items-center justify-center ring-8 ring-white">
                          <EnvelopeIcon className="h-5 w-5 text-white" />
                        </span>
                      </div>
                      <div className="flex min-w-0 flex-1 justify-between space-x-4 pt-1.5">
                        <div>
                          <p className="text-sm text-gray-500">
                            {activity.description}
                          </p>
                          {activity.subject && (
                            <p className="text-xs text-gray-400 mt-0.5 truncate max-w-md">
                              {activity.subject}
                            </p>
                          )}
                        </div>
                        <div className="whitespace-nowrap text-right text-sm text-gray-500">
                          {formatTimeAgo(activity.time)}
                        </div>
                      </div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
      </div>
    </div>
  );
};

export default DashboardPage;
