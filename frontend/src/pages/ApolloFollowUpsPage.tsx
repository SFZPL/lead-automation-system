import React, { useMemo, useState } from 'react';
import { useQuery } from 'react-query';
import toast from 'react-hot-toast';
import {
  ArrowPathIcon,
  ClipboardDocumentIcon,
  CheckIcon,
  EnvelopeIcon,
  ArrowTopRightOnSquareIcon,
  ClockIcon,
  PhoneIcon,
  BuildingOfficeIcon,
  UserCircleIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';

const API_BASE_URL = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

interface FollowUpCall {
  id?: string;
  disposition?: string;
  direction?: string;
  duration_seconds?: number;
  last_called_at?: string;
  notes?: string;
}

interface FollowUpLead {
  id?: number;
  name?: string;
  stage_name?: string;
  salesperson?: string;
  phone?: string;
  company?: string;
}

interface FollowUpItem {
  email: string;
  subject: string;
  body: string;
  call: FollowUpCall;
  odoo_lead: FollowUpLead;
}

interface FollowUpResponse {
  count: number;
  items: FollowUpItem[];
}

const fetchFollowUps = async (limit: number, lookbackHours?: number): Promise<FollowUpResponse> => {
  const params = new URLSearchParams();
  params.set('limit', Math.max(1, limit).toString());
  if (lookbackHours && Number.isFinite(lookbackHours)) {
    params.set('lookback_hours', Math.max(1, Math.floor(lookbackHours)).toString());
  }

  const response = await fetch(`${API_BASE_URL}/apollo/followups?${params.toString()}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  return response.json();
};

const formatDateTime = (value?: string) => {
  if (!value) {
    return 'Not available';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
};

const ApolloFollowUpsPage: React.FC = () => {
  const [limit, setLimit] = useState<number>(5);
  const [lookback, setLookback] = useState<string>('');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const normalizedLookback = useMemo(() => {
    const trimmed = lookback.trim();
    if (!trimmed) {
      return undefined;
    }
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      return undefined;
    }
    return parsed;
  }, [lookback]);

  const followUpQuery = useQuery(
    ['apollo-followups', limit, normalizedLookback ?? null],
    () => fetchFollowUps(limit, normalizedLookback),
    {
      keepPreviousData: true,
      onError: (error: any) => {
        const message = error?.message || 'Unable to fetch follow-up emails';
        toast.error(message);
      },
    }
  );

  const { data, isFetching, isLoading, refetch } = followUpQuery;
  const followUps = data?.items ?? [];
  const totalCount = data?.count ?? 0;

  const handleLimitChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = Number(event.target.value);
    if (Number.isNaN(value)) {
      setLimit(1);
      return;
    }
    setLimit(Math.min(Math.max(1, Math.floor(value)), 50));
  };

  const handleCopyEmail = async (item: FollowUpItem) => {
    try {
      await navigator.clipboard.writeText(`Subject: ${item.subject}\n\n${item.body}`);
      const key = `${item.email}|${item.subject}`;
      setCopiedKey(key);
      toast.success('Email copied to clipboard');
      setTimeout(() => setCopiedKey((current) => (current === key ? null : current)), 2000);
    } catch (error) {
      toast.error('Unable to copy email to clipboard');
    }
  };

  const handleOpenMail = (item: FollowUpItem) => {
    const mailto = `mailto:${encodeURIComponent(item.email)}?subject=${encodeURIComponent(item.subject)}&body=${encodeURIComponent(item.body)}`;
    window.open(mailto, '_blank');
  };

  return (
    <div className="px-4 sm:px-6 lg:px-8">
      <div className="sm:flex sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Apollo Follow-up Emails</h1>
          <p className="mt-1 text-sm text-gray-600">
            Generate personalized follow-ups for Apollo calls where the contact did not answer.
          </p>
        </div>
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="mt-4 inline-flex items-center rounded-md border border-transparent bg-primary-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-60"
        >
          <ArrowPathIcon className={`mr-2 h-5 w-5 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="mt-6 bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label htmlFor="limit" className="block text-sm font-medium text-gray-700">
                Max Emails
              </label>
              <input
                id="limit"
                type="number"
                min={1}
                max={50}
                value={limit}
                onChange={handleLimitChange}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              />
              <p className="mt-1 text-xs text-gray-500">Limits results to prevent overload (max 50).</p>
            </div>
            <div>
              <label htmlFor="lookback" className="block text-sm font-medium text-gray-700">
                Lookback (hours)
              </label>
              <input
                id="lookback"
                type="number"
                min={1}
                placeholder="Defaults to config"
                value={lookback}
                onChange={(event) => setLookback(event.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              />
              <p className="mt-1 text-xs text-gray-500">Leave blank to use the server default.</p>
            </div>
            <div className="bg-gray-50 rounded-md p-4 border border-gray-200">
              <div className="flex items-center text-sm text-gray-700">
                <InformationCircleIcon className="h-5 w-5 text-primary-500" />
                <span className="ml-2 font-medium">Summary</span>
              </div>
              <dl className="mt-3 grid grid-cols-2 gap-3 text-xs text-gray-600">
                <div>
                  <dt className="uppercase tracking-wide text-gray-500">Available</dt>
                  <dd className="text-base font-semibold text-gray-900">{totalCount}</dd>
                </div>
                <div>
                  <dt className="uppercase tracking-wide text-gray-500">Showing</dt>
                  <dd className="text-base font-semibold text-gray-900">{followUps.length}</dd>
                </div>
              </dl>
              {normalizedLookback && (
                <p className="mt-3 text-xs text-gray-500">
                  Filtering calls from the past {normalizedLookback} hour{normalizedLookback === 1 ? '' : 's'}.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-6">
        {isLoading ? (
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="animate-pulse rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
                <div className="h-4 w-1/3 rounded bg-gray-200" />
                <div className="mt-4 h-3 w-full rounded bg-gray-200" />
                <div className="mt-2 h-3 w-2/3 rounded bg-gray-200" />
                <div className="mt-6 h-24 w-full rounded bg-gray-100" />
              </div>
            ))}
          </div>
        ) : followUps.length === 0 ? (
          <div className="rounded-lg border border-dashed border-gray-300 bg-white p-12 text-center">
            <EnvelopeIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">No leads without answer found</h3>
            <p className="mt-1 text-sm text-gray-500">
              Once Apollo logs new missed or no-answer calls, refresh this page to prepare the personalized follow-up emails.
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {followUps.map((item) => {
              const key = `${item.email}|${item.subject}`;
              return (
                <div key={key} className="rounded-lg border border-gray-200 bg-white shadow-sm">
                  <div className="border-b border-gray-200 px-4 py-5 sm:px-6">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <p className="text-sm uppercase tracking-wide text-gray-500">Recipient</p>
                        <p className="text-lg font-semibold text-gray-900">{item.email}</p>
                        <p className="mt-1 text-sm text-gray-600">Subject: {item.subject}</p>
                      </div>
                      <div className="flex gap-3">
                        <button
                          type="button"
                          onClick={() => handleCopyEmail(item)}
                          className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
                        >
                          {copiedKey === key ? (
                            <CheckIcon className="mr-2 h-5 w-5 text-primary-600" />
                          ) : (
                            <ClipboardDocumentIcon className="mr-2 h-5 w-5 text-gray-400" />
                          )}
                          Copy Email
                        </button>
                        <button
                          type="button"
                          onClick={() => handleOpenMail(item)}
                          className="inline-flex items-center rounded-md border border-transparent bg-primary-600 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
                        >
                          <ArrowTopRightOnSquareIcon className="mr-2 h-5 w-5" />
                          Open in Email
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="px-4 py-5 sm:px-6">
                    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                      <div className="lg:col-span-2">
                        <h3 className="text-sm font-medium text-gray-700">Email Body</h3>
                        <div className="mt-2 rounded-md border border-gray-200 bg-gray-50 p-4 text-sm text-gray-800 whitespace-pre-wrap">
                          {item.body}
                        </div>
                      </div>
                      <div className="space-y-4">
                        <div className="rounded-md border border-gray-200 p-4">
                          <h4 className="text-sm font-semibold text-gray-700">Call Details</h4>
                          <dl className="mt-3 space-y-2 text-sm text-gray-600">
                            <div className="flex items-center">
                              <ClockIcon className="mr-2 h-4 w-4 text-gray-400" />
                              <span>{formatDateTime(item.call.last_called_at)}</span>
                            </div>
                            {item.call.disposition && (
                              <div className="flex items-center">
                                <InformationCircleIcon className="mr-2 h-4 w-4 text-gray-400" />
                                <span className="capitalize">{item.call.disposition}</span>
                              </div>
                            )}
                            {item.call.duration_seconds != null && (
                              <div className="flex items-center">
                                <PhoneIcon className="mr-2 h-4 w-4 text-gray-400" />
                                <span>{item.call.duration_seconds} seconds</span>
                              </div>
                            )}
                            {item.call.notes && (
                              <p className="mt-2 rounded bg-gray-100 p-2 text-xs text-gray-600">{item.call.notes}</p>
                            )}
                          </dl>
                        </div>
                        <div className="rounded-md border border-gray-200 p-4">
                          <h4 className="text-sm font-semibold text-gray-700">Odoo Lead Context</h4>
                          <dl className="mt-3 space-y-2 text-sm text-gray-600">
                            {item.odoo_lead.name && (
                              <div className="flex items-center">
                                <UserCircleIcon className="mr-2 h-4 w-4 text-gray-400" />
                                <span>{item.odoo_lead.name}</span>
                              </div>
                            )}
                            {item.odoo_lead.company && (
                              <div className="flex items-center">
                                <BuildingOfficeIcon className="mr-2 h-4 w-4 text-gray-400" />
                                <span>{item.odoo_lead.company}</span>
                              </div>
                            )}
                            {item.odoo_lead.stage_name && (
                              <div className="flex items-center">
                                <InformationCircleIcon className="mr-2 h-4 w-4 text-gray-400" />
                                <span>{item.odoo_lead.stage_name}</span>
                              </div>
                            )}
                            {item.odoo_lead.phone && (
                              <div className="flex items-center">
                                <PhoneIcon className="mr-2 h-4 w-4 text-gray-400" />
                                <span>{item.odoo_lead.phone}</span>
                              </div>
                            )}
                            {item.odoo_lead.salesperson && (
                              <div className="flex items-center">
                                <UserCircleIcon className="mr-2 h-4 w-4 text-gray-400" />
                                <span className="text-xs uppercase tracking-wide text-gray-500">
                                  Owned by {item.odoo_lead.salesperson}
                                </span>
                              </div>
                            )}
                          </dl>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default ApolloFollowUpsPage;
