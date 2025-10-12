import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from 'react-query';
import toast from 'react-hot-toast';
import {
  ArrowPathIcon,
  ClipboardDocumentIcon,
  ClipboardDocumentCheckIcon,
  EnvelopeIcon,
  SparklesIcon,
  ClockIcon,
  PhoneIcon,
  BuildingOfficeIcon,
  UserCircleIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline';

const API_BASE_URL = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

type ActionType = 'email' | 'note';

interface PostContactCall {
  id?: string;
  disposition?: string;
  duration_seconds?: number;
  last_called_at?: string;
  notes?: string;
}

interface PostContactLead {
  id?: number;
  name?: string;
  company?: string;
  stage_name?: string;
  salesperson?: string;
  phone?: string;
}

export interface PostContactAction {
  action_type: ActionType;
  contact_email: string;
  odoo_lead_id: number;
  subject?: string;
  body?: string;
  note_body?: string;
  transcription?: string;
  call?: PostContactCall | null;
  odoo_lead?: PostContactLead | null;
}

interface PostContactActionsResponse {
  count: number;
  actions: PostContactAction[];
}

interface ExecuteActionResponse {
  success: boolean;
  message?: string;
}

const fetchActions = async (limit: number, lookbackHours?: number): Promise<PostContactActionsResponse> => {
  const params = new URLSearchParams();
  params.set('limit', Math.max(1, limit).toString());
  if (lookbackHours && Number.isFinite(lookbackHours)) {
    params.set('lookback_hours', Math.max(1, Math.floor(lookbackHours)).toString());
  }

  const response = await fetch(`${API_BASE_URL}/post-contact/actions?${params.toString()}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }
  return response.json();
};

const executeAction = async (payload: PostContactAction): Promise<ExecuteActionResponse> => {
  const response = await fetch(`${API_BASE_URL}/post-contact/execute`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Execution failed with status ${response.status}`);
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

const buildActionKey = (action: PostContactAction) => {
  const suffix = action.action_type === 'email' ? action.subject ?? '' : action.note_body ?? '';
  return `${action.action_type}:${action.contact_email}:${suffix.slice(0, 32)}`;
};

const PostContactAutomationPage: React.FC = () => {
  const [limit, setLimit] = useState<number>(5);
  const [lookback, setLookback] = useState<string>('');
  const [executingKey, setExecutingKey] = useState<string | null>(null);
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

  const queryClient = useQueryClient();

  const actionsQuery = useQuery(
    ['post-contact-actions', limit, normalizedLookback ?? null],
    () => fetchActions(limit, normalizedLookback),
    {
      keepPreviousData: true,
      onError: (error: any) => {
        const message = error?.message || 'Unable to fetch post-contact actions';
        toast.error(message);
      },
    }
  );

  const mutation = useMutation(executeAction, {
    onSuccess: (data, variables) => {
      const message =
        data?.message ||
        (variables.action_type === 'email' ? 'Email dispatched successfully.' : 'Internal note added in Odoo.');
      toast.success(message);
      queryClient.invalidateQueries(['post-contact-actions']);
    },
    onError: (error: any) => {
      const message = error?.message || 'Action could not be completed';
      toast.error(message);
    },
  });

  const { data, isFetching, isLoading, refetch } = actionsQuery;
  const actions = data?.actions ?? [];

  const handleLimitChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = Number(event.target.value);
    if (Number.isNaN(value)) {
      setLimit(1);
      return;
    }
    setLimit(Math.min(Math.max(1, Math.floor(value)), 50));
  };

  const handleExecute = async (action: PostContactAction) => {
    const key = buildActionKey(action);
    setExecutingKey(key);
    try {
      await mutation.mutateAsync(action);
    } finally {
      setExecutingKey(null);
    }
  };

  const handleCopy = async (content: string, key: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedKey(key);
      toast.success('Copied to clipboard');
      setTimeout(() => setCopiedKey((current) => (current === key ? null : current)), 2000);
    } catch (error) {
      toast.error('Unable to copy to clipboard');
    }
  };

  const handleOpenEmail = (action: PostContactAction) => {
    const params = new URLSearchParams();
    params.set('subject', action.subject ?? 'Follow-up');
    params.set('body', action.body ?? '');
    window.open(`mailto:${action.contact_email}?${params.toString()}`, '_blank');
  };

  return (
    <div className="space-y-6 px-4 sm:px-6 lg:px-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.2em] text-primary-600">
            <SparklesIcon className="h-4 w-4" />
            Post-Contact Workflow
          </div>
          <h1 className="mt-2 text-2xl font-semibold text-gray-900">Automation After First Contact</h1>
          <p className="mt-2 max-w-3xl text-sm text-gray-600">
            Review AI-assisted follow-ups: preview emails for no-answer calls or upload Maqsam call notes directly into
            Odoo. Confirm each action before it is sent.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 shadow-sm">
            <label htmlFor="limit" className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Max Items
            </label>
            <input
              id="limit"
              type="number"
              min={1}
              max={50}
              value={limit}
              onChange={handleLimitChange}
              className="w-16 rounded-md border border-gray-300 px-2 py-1 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </div>
          <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 shadow-sm">
            <label htmlFor="lookback" className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Lookback (hrs)
            </label>
            <input
              id="lookback"
              type="number"
              min={1}
              placeholder="72"
              value={lookback}
              onChange={(event) => setLookback(event.target.value)}
              className="w-20 rounded-md border border-gray-300 px-2 py-1 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </div>
          <button
            type="button"
            onClick={() => refetch()}
            className="inline-flex items-center rounded-md border border-transparent bg-primary-600 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
          >
            <ArrowPathIcon className={`mr-2 h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-primary-100 bg-white/70 p-4 text-sm text-primary-900 shadow-sm">
        <p className="font-medium">
          How it works:
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-6 text-gray-600">
          <li>Actions marked as <strong>Email</strong> generate a personalized follow-up using the latest Odoo context.</li>
          <li><strong>Internal Note</strong> items capture Maqsam transcriptions and push them into the Odoo chatter.</li>
          <li>Each action is optional—review the details and confirm when you are ready.</li>
        </ul>
      </div>

  <div className="space-y-6">
        {isLoading ? (
          <div className="flex items-center justify-center rounded-xl border border-dashed border-gray-300 bg-white/60 py-16 text-gray-500">
            <ArrowPathIcon className="mr-3 h-5 w-5 animate-spin" />
            Loading post-contact actions...
          </div>
        ) : actions.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-300 bg-white/60 p-10 text-center text-gray-500">
            <SparklesIcon className="mx-auto h-10 w-10 text-gray-400" />
            <p className="mt-3 text-base font-medium text-gray-700">You are all caught up!</p>
            <p className="mt-1 text-sm text-gray-500">No post-contact actions are required right now.</p>
          </div>
        ) : (
          actions.map((action) => {
            const key = buildActionKey(action);
            const call = action.call ?? {};
            const lead = action.odoo_lead ?? {};
            const isEmail = action.action_type === 'email';
            const primaryDisabled = executingKey === key || mutation.isLoading;

            const copyPayload =
              isEmail && action.subject && action.body
                ? `To: ${action.contact_email}\nSubject: ${action.subject}\n\n${action.body}`
                : action.note_body ?? '';

            return (
              <div key={key} className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
                <div className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-4 sm:px-6">
                  <div className="flex items-center gap-3">
                    <span
                      className={`flex h-10 w-10 items-center justify-center rounded-xl border ${
                        isEmail
                          ? 'border-primary-100 bg-primary-50 text-primary-600'
                          : 'border-indigo-100 bg-indigo-50 text-indigo-600'
                      }`}
                    >
                      {isEmail ? (
                        <EnvelopeIcon className="h-5 w-5" />
                      ) : (
                        <ClipboardDocumentCheckIcon className="h-5 w-5" />
                      )}
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">
                        {isEmail ? 'Follow-up Email' : 'Internal Note'}
                      </p>
                      <p className="text-xs text-gray-500">
                        {action.contact_email} • Lead #{action.odoo_lead_id}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {copyPayload && (
                      <button
                        type="button"
                        onClick={() => handleCopy(copyPayload, key)}
                        className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
                      >
                        {copiedKey === key ? (
                          <ClipboardDocumentCheckIcon className="mr-2 h-4 w-4 text-primary-600" />
                        ) : (
                          <ClipboardDocumentIcon className="mr-2 h-4 w-4 text-gray-400" />
                        )}
                        Copy
                      </button>
                    )}
                    {isEmail && (
                      <button
                        type="button"
                        onClick={() => handleOpenEmail(action)}
                        className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
                      >
                        <ArrowTopRightOnSquareIcon className="mr-2 h-4 w-4" />
                        Open Email Client
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => handleExecute(action)}
                      disabled={primaryDisabled}
                      className={`inline-flex items-center rounded-md border border-transparent px-4 py-2 text-sm font-semibold text-white shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 ${
                        isEmail
                          ? 'bg-primary-600 hover:bg-primary-700 focus:ring-primary-500'
                          : 'bg-indigo-600 hover:bg-indigo-700 focus:ring-indigo-500'
                      } ${primaryDisabled ? 'cursor-not-allowed opacity-60' : ''}`}
                    >
                      <ArrowPathIcon className={`mr-2 h-4 w-4 ${primaryDisabled ? 'animate-spin' : ''}`} />
                      {isEmail ? 'Send Email' : 'Upload Note'}
                    </button>
                  </div>
                </div>

                <div className="px-4 py-5 sm:px-6">
                  <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                    <div className="space-y-4 lg:col-span-2">
                      {isEmail ? (
                        <>
                          <div>
                            <h3 className="text-sm font-medium text-gray-700">Email Subject</h3>
                            <p className="mt-1 rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-800">
                              {action.subject}
                            </p>
                          </div>
                          <div>
                            <h3 className="text-sm font-medium text-gray-700">Email Body</h3>
                            <div className="mt-2 min-h-[120px] rounded-md border border-gray-200 bg-white p-4 text-sm text-gray-800 whitespace-pre-wrap">
                              {action.body}
                            </div>
                          </div>
                        </>
                      ) : (
                        <>
                          <div>
                            <h3 className="text-sm font-medium text-gray-700">Internal Note</h3>
                            <div className="mt-2 min-h-[120px] rounded-md border border-gray-200 bg-white p-4 text-sm text-gray-800 whitespace-pre-wrap">
                              {action.note_body}
                            </div>
                          </div>
                          {action.transcription && (
                            <div>
                              <h3 className="text-sm font-medium text-gray-700">Maqsam Transcription</h3>
                              <div className="mt-2 rounded-md border border-gray-200 bg-gray-50 p-4 text-sm text-gray-700 whitespace-pre-wrap">
                                {action.transcription}
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </div>

                    <div className="space-y-4">
                      <div className="rounded-md border border-gray-200 p-4">
                        <h4 className="text-sm font-semibold text-gray-700">Call Context</h4>
                        <dl className="mt-3 space-y-2 text-sm text-gray-600">
                          <div className="flex items-center">
                            <ClockIcon className="mr-2 h-4 w-4 text-gray-400" />
                            <span>{formatDateTime(call.last_called_at)}</span>
                          </div>
                          {call.disposition && (
                            <div className="flex items-center">
                              <SparklesIcon className="mr-2 h-4 w-4 text-gray-400" />
                              <span className="capitalize">{call.disposition}</span>
                            </div>
                          )}
                          {call.duration_seconds != null && (
                            <div className="flex items-center">
                              <PhoneIcon className="mr-2 h-4 w-4 text-gray-400" />
                              <span>{call.duration_seconds} seconds</span>
                            </div>
                          )}
                          {call.notes && (
                            <p className="mt-2 rounded bg-gray-100 p-2 text-xs text-gray-600">{call.notes}</p>
                          )}
                        </dl>
                      </div>
                      <div className="rounded-md border border-gray-200 p-4">
                        <h4 className="text-sm font-semibold text-gray-700">Lead Details</h4>
                        <dl className="mt-3 space-y-2 text-sm text-gray-600">
                          {lead.name && (
                            <div className="flex items-center">
                              <UserCircleIcon className="mr-2 h-4 w-4 text-gray-400" />
                              <span>{lead.name}</span>
                            </div>
                          )}
                          {lead.company && (
                            <div className="flex items-center">
                              <BuildingOfficeIcon className="mr-2 h-4 w-4 text-gray-400" />
                              <span>{lead.company}</span>
                            </div>
                          )}
                          {lead.stage_name && (
                            <div className="flex items-center">
                              <SparklesIcon className="mr-2 h-4 w-4 text-gray-400" />
                              <span>{lead.stage_name}</span>
                            </div>
                          )}
                          {lead.phone && (
                            <div className="flex items-center">
                              <PhoneIcon className="mr-2 h-4 w-4 text-gray-400" />
                              <span>{lead.phone}</span>
                            </div>
                          )}
                          {lead.salesperson && (
                            <p className="text-xs uppercase tracking-wide text-gray-500">
                              Owner: {lead.salesperson}
                            </p>
                          )}
                        </dl>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default PostContactAutomationPage;

