import React, { useState } from 'react';
import { useQuery } from 'react-query';
import {
  ChartBarIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  FunnelIcon,
} from '@heroicons/react/24/outline';
import api from '../utils/api';

interface ResponseMetrics {
  total_responses: number;
  responses_per_day: number;
  period_days: number;
  avg_first_contact_hours: number | null;
  median_first_contact_hours: number | null;
  response_within_24h_pct: number;
  response_within_48h_pct: number;
  response_within_72h_pct: number;
  avg_reply_hours: number | null;
  median_reply_hours: number | null;
  total_reply_pairs: number;
}

interface StageMetrics {
  total_leads: number;
  stage_distribution: Array<{
    stage: string;
    count: number;
    percentage: number;
    total_value: number;
  }>;
  conversion_rates: Record<string, number>;
  avg_stage_score: number;
}

interface WinLossMetrics {
  total_leads: number;
  won_count: number;
  lost_count: number;
  active_count: number;
  win_rate_pct: number;
  loss_rate_pct: number;
  total_value: number;
  won_value: number;
  lost_value: number;
  value_win_rate_pct: number;
  lost_reasons: Record<string, number>;
}

interface VelocityMetrics {
  leads_per_week: number;
  progressing_per_week: number;
  progression_rate_pct: number;
  avg_days_to_stage_change: number | null;
}

interface ImpactReport {
  generated_at: string;
  deployment_date: string;
  periods: {
    before: { start: string; end: string; days: number };
    after: { start: string; end: string; days: number };
  };
  source_filter: string | null;
  summary: {
    before_lead_count: number;
    after_lead_count: number;
    key_improvements: Record<string, number | null>;
  };
  response_metrics: {
    before: ResponseMetrics;
    after: ResponseMetrics;
  };
  stage_metrics: {
    before: StageMetrics;
    after: StageMetrics;
  };
  win_loss_metrics: {
    before: WinLossMetrics;
    after: WinLossMetrics;
  };
  velocity_metrics: {
    before: VelocityMetrics;
    after: VelocityMetrics;
  };
}

const MetricCard: React.FC<{
  title: string;
  beforeValue: string | number;
  afterValue: string | number;
  delta?: number | null;
  unit?: string;
  inverse?: boolean; // If true, lower is better
}> = ({ title, beforeValue, afterValue, delta, unit = '', inverse = false }) => {
  const getDeltaColor = () => {
    if (delta === null || delta === undefined) return 'text-gray-500';
    const isPositive = inverse ? delta < 0 : delta > 0;
    return isPositive ? 'text-green-600' : 'text-red-600';
  };

  const getDeltaIcon = () => {
    if (delta === null || delta === undefined) return null;
    const isPositive = inverse ? delta < 0 : delta > 0;
    return isPositive ? (
      <ArrowTrendingUpIcon className="w-4 h-4" />
    ) : (
      <ArrowTrendingDownIcon className="w-4 h-4" />
    );
  };

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h4 className="text-sm font-medium text-gray-500 mb-2">{title}</h4>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-gray-400 uppercase">Before</p>
          <p className="text-lg font-semibold text-gray-700">
            {beforeValue}{unit}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-400 uppercase">After</p>
          <p className="text-lg font-semibold text-gray-900">
            {afterValue}{unit}
          </p>
        </div>
      </div>
      {delta !== null && delta !== undefined && (
        <div className={`flex items-center gap-1 mt-2 ${getDeltaColor()}`}>
          {getDeltaIcon()}
          <span className="text-sm font-medium">
            {delta > 0 ? '+' : ''}{delta.toFixed(1)}%
          </span>
        </div>
      )}
    </div>
  );
};

const ToolImpactPage: React.FC = () => {
  const [beforeDays, setBeforeDays] = useState(90);
  const [sourceFilter, setSourceFilter] = useState<string>('');

  const { data: reportData, isLoading, error, refetch } = useQuery(
    ['tool-impact', beforeDays, sourceFilter],
    async () => {
      const params = new URLSearchParams();
      params.append('before_days', beforeDays.toString());
      if (sourceFilter) params.append('source_filter', sourceFilter);

      const response = await api.get(`/analytics/tool-impact?${params.toString()}`);
      return response.data;
    },
    {
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000, // 5 minutes
    }
  );

  const { data: sourcesData } = useQuery(
    'lead-sources',
    async () => {
      const response = await api.get('/analytics/lead-sources');
      return response.data;
    },
    { staleTime: Infinity }
  );

  const report: ImpactReport | undefined = reportData?.report;
  const sources: string[] = sourcesData?.sources || [];

  const formatDate = (isoString: string) => {
    return new Date(isoString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const formatHours = (hours: number | null) => {
    if (hours === null) return 'N/A';
    if (hours < 1) return `${Math.round(hours * 60)} min`;
    if (hours < 24) return `${hours.toFixed(1)} hrs`;
    return `${(hours / 24).toFixed(1)} days`;
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-AE', {
      style: 'currency',
      currency: 'AED',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="flex flex-col items-center gap-4">
          <ArrowPathIcon className="w-8 h-8 text-green-600 animate-spin" />
          <p className="text-gray-600">Analyzing tool impact...</p>
          <p className="text-sm text-gray-400">This may take a minute as we fetch data from Odoo</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">Error loading impact report: {(error as Error).message}</p>
          <button
            onClick={() => refetch()}
            className="mt-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="p-6">
        <p className="text-gray-600">No report data available</p>
      </div>
    );
  }

  const { response_metrics, stage_metrics, win_loss_metrics, velocity_metrics, summary } = report;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <ChartBarIcon className="w-7 h-7 text-green-600" />
          Tool Impact Analysis
        </h1>
        <p className="text-gray-600 mt-1">
          Comparing performance before and after tool deployment (Nov 23, 2025)
        </p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Before Period (days)
            </label>
            <select
              value={beforeDays}
              onChange={(e) => setBeforeDays(Number(e.target.value))}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
            >
              <option value={30}>30 days</option>
              <option value={60}>60 days</option>
              <option value={90}>90 days</option>
              <option value={180}>180 days</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              <FunnelIcon className="w-4 h-4 inline mr-1" />
              Lead Source Filter
            </label>
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
            >
              <option value="">All Sources</option>
              {sources.map((source) => (
                <option key={source} value={source}>
                  {source}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={() => refetch()}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2"
          >
            <ArrowPathIcon className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Period Info */}
      <div className="bg-gray-50 rounded-lg p-4 mb-6 grid grid-cols-2 gap-4">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-gray-400 rounded-full"></div>
          <div>
            <p className="text-sm font-medium text-gray-700">Before Period</p>
            <p className="text-xs text-gray-500">
              {formatDate(report.periods.before.start)} - {formatDate(report.periods.before.end)}
              <span className="ml-2">({report.periods.before.days} days, {summary.before_lead_count} leads)</span>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-green-500 rounded-full"></div>
          <div>
            <p className="text-sm font-medium text-gray-700">After Period</p>
            <p className="text-xs text-gray-500">
              {formatDate(report.periods.after.start)} - {formatDate(report.periods.after.end)}
              <span className="ml-2">({report.periods.after.days} days, {summary.after_lead_count} leads)</span>
            </p>
          </div>
        </div>
      </div>

      {/* Key Improvements Summary */}
      <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-lg p-6 mb-6">
        <h2 className="text-lg font-semibold text-green-900 mb-4">Key Improvements</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {summary.key_improvements.avg_first_contact_hours !== null && (
            <div className="text-center">
              <p className={`text-2xl font-bold ${summary.key_improvements.avg_first_contact_hours > 0 ? 'text-green-600' : 'text-red-600'}`}>
                {summary.key_improvements.avg_first_contact_hours > 0 ? '+' : ''}{summary.key_improvements.avg_first_contact_hours}%
              </p>
              <p className="text-sm text-gray-600">Response Speed</p>
            </div>
          )}
          {summary.key_improvements.response_within_24h !== null && (
            <div className="text-center">
              <p className={`text-2xl font-bold ${summary.key_improvements.response_within_24h > 0 ? 'text-green-600' : 'text-red-600'}`}>
                {summary.key_improvements.response_within_24h > 0 ? '+' : ''}{summary.key_improvements.response_within_24h}%
              </p>
              <p className="text-sm text-gray-600">24h Response</p>
            </div>
          )}
          {summary.key_improvements.win_rate !== null && (
            <div className="text-center">
              <p className={`text-2xl font-bold ${summary.key_improvements.win_rate > 0 ? 'text-green-600' : 'text-red-600'}`}>
                {summary.key_improvements.win_rate > 0 ? '+' : ''}{summary.key_improvements.win_rate}%
              </p>
              <p className="text-sm text-gray-600">Win Rate</p>
            </div>
          )}
          {summary.key_improvements.progression_rate !== null && (
            <div className="text-center">
              <p className={`text-2xl font-bold ${summary.key_improvements.progression_rate > 0 ? 'text-green-600' : 'text-red-600'}`}>
                {summary.key_improvements.progression_rate > 0 ? '+' : ''}{summary.key_improvements.progression_rate}%
              </p>
              <p className="text-sm text-gray-600">Progression Rate</p>
            </div>
          )}
        </div>
      </div>

      {/* Response Metrics */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <ClockIcon className="w-5 h-5 text-blue-600" />
          Response Metrics
        </h2>

        {/* First Contact Time - Lead creation to first email */}
        <h3 className="text-sm font-medium text-gray-600 mb-2">
          Time to First Contact
          <span className="text-xs font-normal text-gray-400 ml-2">
            (Lead created → First outbound email)
          </span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <MetricCard
            title="First Contacts per Day"
            beforeValue={response_metrics.before.responses_per_day}
            afterValue={response_metrics.after.responses_per_day}
            delta={summary.key_improvements.responses_per_day}
          />
          <MetricCard
            title="Avg Time to First Email"
            beforeValue={formatHours(response_metrics.before.avg_first_contact_hours)}
            afterValue={formatHours(response_metrics.after.avg_first_contact_hours)}
            delta={summary.key_improvements.avg_first_contact_hours}
            inverse={true}
          />
          <MetricCard
            title="First Contact Within 24h"
            beforeValue={response_metrics.before.response_within_24h_pct}
            afterValue={response_metrics.after.response_within_24h_pct}
            delta={summary.key_improvements.response_within_24h}
            unit="%"
          />
          <MetricCard
            title="First Contact Within 48h"
            beforeValue={response_metrics.before.response_within_48h_pct}
            afterValue={response_metrics.after.response_within_48h_pct}
            unit="%"
          />
        </div>

        {/* Email Reply Time - Customer email to our reply */}
        <h3 className="text-sm font-medium text-gray-600 mb-2">
          Email Reply Speed
          <span className="text-xs font-normal text-gray-400 ml-2">
            (Customer email → Our reply)
          </span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <MetricCard
            title="Avg Reply Time"
            beforeValue={formatHours(response_metrics.before.avg_reply_hours)}
            afterValue={formatHours(response_metrics.after.avg_reply_hours)}
            inverse={true}
          />
          <MetricCard
            title="Median Reply Time"
            beforeValue={formatHours(response_metrics.before.median_reply_hours)}
            afterValue={formatHours(response_metrics.after.median_reply_hours)}
            inverse={true}
          />
          <MetricCard
            title="Email Conversations"
            beforeValue={response_metrics.before.total_reply_pairs}
            afterValue={response_metrics.after.total_reply_pairs}
          />
        </div>
      </div>

      {/* Stage Conversion Metrics */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <ChartBarIcon className="w-5 h-5 text-purple-600" />
          Stage Conversion Rates
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="text-sm font-medium text-gray-500 mb-3">Before</h3>
            <div className="space-y-2">
              {stage_metrics.before.stage_distribution.slice(0, 5).map((stage) => (
                <div key={stage.stage} className="flex items-center justify-between">
                  <span className="text-sm text-gray-700">{stage.stage}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-32 bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-gray-500 h-2 rounded-full"
                        style={{ width: `${stage.percentage}%` }}
                      ></div>
                    </div>
                    <span className="text-sm text-gray-600 w-12 text-right">
                      {stage.percentage}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-400 mt-3">
              Avg Stage Score: {stage_metrics.before.avg_stage_score}
            </p>
          </div>

          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="text-sm font-medium text-gray-500 mb-3">After</h3>
            <div className="space-y-2">
              {stage_metrics.after.stage_distribution.slice(0, 5).map((stage) => (
                <div key={stage.stage} className="flex items-center justify-between">
                  <span className="text-sm text-gray-700">{stage.stage}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-32 bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-green-500 h-2 rounded-full"
                        style={{ width: `${stage.percentage}%` }}
                      ></div>
                    </div>
                    <span className="text-sm text-gray-600 w-12 text-right">
                      {stage.percentage}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-400 mt-3">
              Avg Stage Score: {stage_metrics.after.avg_stage_score}
            </p>
          </div>
        </div>
      </div>

      {/* Win/Loss Metrics */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <CheckCircleIcon className="w-5 h-5 text-green-600" />
          Win/Loss Analysis
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            title="Win Rate"
            beforeValue={win_loss_metrics.before.win_rate_pct}
            afterValue={win_loss_metrics.after.win_rate_pct}
            delta={summary.key_improvements.win_rate}
            unit="%"
          />
          <MetricCard
            title="Loss Rate"
            beforeValue={win_loss_metrics.before.loss_rate_pct}
            afterValue={win_loss_metrics.after.loss_rate_pct}
            delta={summary.key_improvements.loss_rate}
            unit="%"
            inverse={true}
          />
          <MetricCard
            title="Won Value"
            beforeValue={formatCurrency(win_loss_metrics.before.won_value)}
            afterValue={formatCurrency(win_loss_metrics.after.won_value)}
          />
          <MetricCard
            title="Value Win Rate"
            beforeValue={win_loss_metrics.before.value_win_rate_pct}
            afterValue={win_loss_metrics.after.value_win_rate_pct}
            unit="%"
          />
        </div>
      </div>

      {/* Velocity Metrics */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <ArrowTrendingUpIcon className="w-5 h-5 text-orange-600" />
          Lead Velocity
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            title="Leads per Week"
            beforeValue={velocity_metrics.before.leads_per_week}
            afterValue={velocity_metrics.after.leads_per_week}
          />
          <MetricCard
            title="Progressing per Week"
            beforeValue={velocity_metrics.before.progressing_per_week}
            afterValue={velocity_metrics.after.progressing_per_week}
          />
          <MetricCard
            title="Progression Rate"
            beforeValue={velocity_metrics.before.progression_rate_pct}
            afterValue={velocity_metrics.after.progression_rate_pct}
            delta={summary.key_improvements.progression_rate}
            unit="%"
          />
          <MetricCard
            title="Avg Days to Stage Change"
            beforeValue={velocity_metrics.before.avg_days_to_stage_change ?? 'N/A'}
            afterValue={velocity_metrics.after.avg_days_to_stage_change ?? 'N/A'}
            inverse={true}
          />
        </div>
      </div>

      {/* Lost Reasons Comparison */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <XCircleIcon className="w-5 h-5 text-red-600" />
          Lost Reasons Breakdown
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="text-sm font-medium text-gray-500 mb-3">Before ({win_loss_metrics.before.lost_count} lost)</h3>
            <div className="space-y-2">
              {Object.entries(win_loss_metrics.before.lost_reasons).slice(0, 5).map(([reason, count]) => (
                <div key={reason} className="flex items-center justify-between text-sm">
                  <span className="text-gray-700">{reason}</span>
                  <span className="text-gray-500">{count}</span>
                </div>
              ))}
              {Object.keys(win_loss_metrics.before.lost_reasons).length === 0 && (
                <p className="text-sm text-gray-400">No lost leads in this period</p>
              )}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="text-sm font-medium text-gray-500 mb-3">After ({win_loss_metrics.after.lost_count} lost)</h3>
            <div className="space-y-2">
              {Object.entries(win_loss_metrics.after.lost_reasons).slice(0, 5).map(([reason, count]) => (
                <div key={reason} className="flex items-center justify-between text-sm">
                  <span className="text-gray-700">{reason}</span>
                  <span className="text-gray-500">{count}</span>
                </div>
              ))}
              {Object.keys(win_loss_metrics.after.lost_reasons).length === 0 && (
                <p className="text-sm text-gray-400">No lost leads in this period</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="text-center text-sm text-gray-400">
        Report generated at {new Date(report.generated_at).toLocaleString()}
      </div>
    </div>
  );
};

export default ToolImpactPage;
