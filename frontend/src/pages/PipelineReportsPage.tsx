import React, { useState } from 'react';
import { useQuery } from 'react-query';
import toast from 'react-hot-toast';
import {
  ChartBarIcon,
  ArrowPathIcon,
  CalendarIcon,
  ChatBubbleLeftRightIcon,
  UserGroupIcon,
  ExclamationTriangleIcon,
  TrophyIcon,
} from '@heroicons/react/24/outline';
import api from '../utils/api';

interface WeekOverview {
  new_leads: number;
  qualified_leads: number;
  proposals_sent: number;
  deals_closed: number;
  closed_value: number;
  deals_lost: number;
  lost_reasons: Record<string, number>;
}

interface PipelineStage {
  stage_name: string;
  count: number;
  avg_age_days: number;
  total_value: number;
  top_clients: string[];
}

interface Opportunity {
  opportunity_name: string;
  company: string;
  stage: string;
  potential_value: number;
  owner: string;
  days_since_last_activity: number;
}

interface AtRiskLead {
  lead_name: string;
  company: string;
  stage: string;
  owner: string;
  value: number;
  days_inactive: number;
}

interface PipelineReport {
  week_start: string;
  week_end: string;
  salesperson_filter?: string;
  overview: WeekOverview;
  pipeline_stages: PipelineStage[];
  top_opportunities: Opportunity[];
  at_risk_leads: AtRiskLead[];
  generated_at: string;
}

const PipelineReportsPage: React.FC = () => {
  const [weekStart, setWeekStart] = useState<string>('');
  const [weekEnd, setWeekEnd] = useState<string>('');
  const [salespersonFilter, setSalespersonFilter] = useState<string>('');
  const [isSendingToTeams, setIsSendingToTeams] = useState<boolean>(false);

  // Calculate last week's Monday-Sunday by default
  React.useEffect(() => {
    const today = new Date();
    const daysSinceMonday = (today.getDay() + 6) % 7;
    const lastMonday = new Date(today);
    lastMonday.setDate(today.getDate() - daysSinceMonday - 7);
    const lastSunday = new Date(lastMonday);
    lastSunday.setDate(lastMonday.getDate() + 6);

    setWeekStart(lastMonday.toISOString().split('T')[0]);
    setWeekEnd(lastSunday.toISOString().split('T')[0]);
  }, []);

  const reportQuery = useQuery<PipelineReport>(
    ['pipeline-report', weekStart, weekEnd, salespersonFilter],
    async () => {
      const params = new URLSearchParams();
      if (weekStart) params.append('week_start', weekStart);
      if (weekEnd) params.append('week_end', weekEnd);
      if (salespersonFilter) params.append('salesperson_filter', salespersonFilter);

      const response = await api.get(`/pipeline/weekly-report?${params.toString()}`);
      return response.data;
    },
    {
      enabled: !!weekStart && !!weekEnd,
      staleTime: 60000, // 1 minute
    }
  );

  const handleRefresh = () => {
    reportQuery.refetch();
  };

  const handleSendToTeams = async () => {
    if (!reportQuery.data) {
      toast.error('No report data to send');
      return;
    }

    setIsSendingToTeams(true);
    try {
      const chatId = '19:e53c2cecd4aa4581b6f417a95c0116df@thread.v2';

      await api.post('/pipeline/send-to-teams', {
        chat_id: chatId,
        report_data: reportQuery.data,
      });

      toast.success('Report sent to Teams successfully!');
    } catch (error: any) {
      console.error('Error sending to Teams:', error);
      toast.error(error.response?.data?.detail || 'Failed to send report to Teams');
    } finally {
      setIsSendingToTeams(false);
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-AE', {
      style: 'currency',
      currency: 'AED',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <ChartBarIcon className="h-8 w-8 text-primary-600" />
          Weekly Pipeline Performance Report
        </h1>
        <p className="mt-2 text-sm text-gray-600">
          Comprehensive weekly pipeline metrics and insights
        </p>
      </div>

      {/* Controls */}
      <div className="mb-6 bg-white rounded-lg shadow p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Week Start
            </label>
            <input
              type="date"
              value={weekStart}
              onChange={(e) => setWeekStart(e.target.value)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Week End
            </label>
            <input
              type="date"
              value={weekEnd}
              onChange={(e) => setWeekEnd(e.target.value)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Salesperson (Optional)
            </label>
            <input
              type="text"
              value={salespersonFilter}
              onChange={(e) => setSalespersonFilter(e.target.value)}
              placeholder="Filter by name..."
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            />
          </div>

          <div className="flex items-end gap-2">
            <button
              onClick={handleRefresh}
              disabled={reportQuery.isLoading}
              className="flex-1 inline-flex items-center justify-center gap-2 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
            >
              <ArrowPathIcon className={`h-4 w-4 ${reportQuery.isLoading ? 'animate-spin' : ''}`} />
              {reportQuery.isLoading ? 'Loading...' : 'Generate'}
            </button>

            <button
              onClick={handleSendToTeams}
              disabled={isSendingToTeams || !reportQuery.data}
              className="flex-1 inline-flex items-center justify-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              <ChatBubbleLeftRightIcon className="h-4 w-4" />
              {isSendingToTeams ? 'Sending...' : 'Send to Teams'}
            </button>
          </div>
        </div>
      </div>

      {/* Report Content */}
      {reportQuery.isLoading && (
        <div className="text-center py-12">
          <ArrowPathIcon className="h-12 w-12 text-primary-600 animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Generating pipeline report...</p>
        </div>
      )}

      {reportQuery.error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">
            Error loading report: {(reportQuery.error as any).message}
          </p>
        </div>
      )}

      {reportQuery.data && (
        <div className="space-y-6">
          {/* Week Overview */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <CalendarIcon className="h-5 w-5 text-gray-500" />
                Week Overview
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                {reportQuery.data.week_start} to {reportQuery.data.week_end}
              </p>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                <div className="bg-blue-50 rounded-lg p-4">
                  <p className="text-sm text-gray-600">New Leads</p>
                  <p className="text-2xl font-bold text-blue-600">
                    {reportQuery.data.overview.new_leads}
                  </p>
                </div>
                <div className="bg-green-50 rounded-lg p-4">
                  <p className="text-sm text-gray-600">Qualified</p>
                  <p className="text-2xl font-bold text-green-600">
                    {reportQuery.data.overview.qualified_leads}
                  </p>
                </div>
                <div className="bg-purple-50 rounded-lg p-4">
                  <p className="text-sm text-gray-600">Proposals</p>
                  <p className="text-2xl font-bold text-purple-600">
                    {reportQuery.data.overview.proposals_sent}
                  </p>
                </div>
                <div className="bg-emerald-50 rounded-lg p-4">
                  <p className="text-sm text-gray-600">Closed</p>
                  <p className="text-2xl font-bold text-emerald-600">
                    {reportQuery.data.overview.deals_closed}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {formatCurrency(reportQuery.data.overview.closed_value)}
                  </p>
                </div>
                <div className="bg-red-50 rounded-lg p-4">
                  <p className="text-sm text-gray-600">Lost</p>
                  <p className="text-2xl font-bold text-red-600">
                    {reportQuery.data.overview.deals_lost}
                  </p>
                </div>
              </div>

              {Object.keys(reportQuery.data.overview.lost_reasons).length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <p className="text-sm font-medium text-gray-700 mb-2">Lost Reasons:</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(reportQuery.data.overview.lost_reasons).map(([reason, count]) => (
                      <span
                        key={reason}
                        className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800"
                      >
                        {reason}: {count}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Pipeline by Stage */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <UserGroupIcon className="h-5 w-5 text-gray-500" />
                Pipeline by Stage
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Stage
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Count
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Avg Age (days)
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Total Value
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Top Clients
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {reportQuery.data.pipeline_stages.map((stage, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {stage.stage_name}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                        {stage.count}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                        {stage.avg_age_days}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                        {formatCurrency(stage.total_value)}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {stage.top_clients.slice(0, 3).join(', ')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Top Opportunities */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <TrophyIcon className="h-5 w-5 text-yellow-500" />
                Top 5 Opportunities
              </h2>
            </div>
            <div className="p-6">
              {reportQuery.data.top_opportunities.length === 0 ? (
                <p className="text-gray-500 text-sm italic">No active opportunities found.</p>
              ) : (
                <div className="space-y-3">
                  {reportQuery.data.top_opportunities.map((opp, idx) => (
                    <div key={idx} className="border border-gray-200 rounded-lg p-4 hover:border-primary-300 transition-colors">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <p className="font-semibold text-gray-900">{opp.opportunity_name}</p>
                          {opp.company && opp.company !== opp.opportunity_name && (
                            <p className="text-sm text-gray-600">{opp.company}</p>
                          )}
                          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-500">
                            <span>Stage: <span className="font-medium">{opp.stage}</span></span>
                            <span>Owner: <span className="font-medium">{opp.owner}</span></span>
                            <span>Last activity: <span className="font-medium">{opp.days_since_last_activity} days ago</span></span>
                          </div>
                        </div>
                        <div className="ml-4 text-right flex-shrink-0">
                          <p className="text-lg font-bold text-primary-600">
                            {formatCurrency(opp.potential_value)}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* At-Risk Leads */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <ExclamationTriangleIcon className="h-5 w-5 text-red-500" />
                At Risk Leads (10+ Days No Activity)
              </h2>
            </div>
            <div className="p-6">
              {reportQuery.data.at_risk_leads.length === 0 ? (
                <p className="text-green-600 text-sm flex items-center gap-2">
                  ✅ No leads at risk - great job staying on top of follow-ups!
                </p>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm text-gray-600 mb-4">
                    <strong>{reportQuery.data.at_risk_leads.length}</strong> leads at risk
                  </p>
                  {reportQuery.data.at_risk_leads.slice(0, 10).map((lead, idx) => (
                    <div key={idx} className="border border-red-200 rounded-lg p-4 bg-red-50">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <p className="font-semibold text-gray-900">{lead.lead_name}</p>
                          <p className="text-sm text-gray-600">
                            {lead.stage} {lead.company && `• ${lead.company}`}
                          </p>
                          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-600">
                            <span>Owner: <span className="font-medium">{lead.owner}</span></span>
                            <span className="text-red-600 font-medium">Inactive: {lead.days_inactive} days</span>
                          </div>
                        </div>
                        <div className="ml-4 text-right flex-shrink-0">
                          <p className="text-sm font-semibold text-gray-700">
                            {formatCurrency(lead.value)}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Report timestamp */}
          <div className="text-center text-xs text-gray-500">
            Report generated at {new Date(reportQuery.data.generated_at).toLocaleString()}
          </div>
        </div>
      )}
    </div>
  );
};

export default PipelineReportsPage;
