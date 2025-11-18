import axios from 'axios';

// Unique storage keys to avoid conflicts with other Teams apps
const PREZLAB_AUTH_TOKEN_KEY = 'prezlab_auth_token';

// Create axios instance with base configuration

export const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_BASE || 'http://localhost:8000',
  timeout: 0, // No timeout for long-running operations like 90-day reports
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Add authentication token if available (try both storages)
    const token = localStorage.getItem(PREZLAB_AUTH_TOKEN_KEY) || sessionStorage.getItem(PREZLAB_AUTH_TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // Handle common errors
    if (error.response?.status === 401) {
      // Token expired - will be handled by AuthContext refresh logic
      console.log('401 error - auth token may have expired');
      // Don't remove tokens here - let AuthContext handle refresh
    } else if (error.response?.status === 500) {
      console.error('Server error:', error.response.data);
    }

    return Promise.reject(error);
  }
);

// API helper functions
export const api = {
  // Authentication
  login: (email: string, password: string) => apiClient.post('/auth/login', { email, password }),
  refreshToken: (refresh_token: string) => apiClient.post('/auth/refresh', { refresh_token }),

  // Configuration
  getConfig: () => apiClient.get('/api/config'),
  validateConfig: () => apiClient.post('/api/validate-config'),

  // Leads
  getLeads: () => apiClient.get('/api/leads'),
  getLeadsCount: () => apiClient.get('/api/leads/count'),

  // Operations
  extractLeads: (data?: any) => apiClient.post('/api/operations/extract-leads', data),
  enrichLeads: (data?: any) => apiClient.post('/api/operations/enrich-leads', data),
  runFullPipeline: (data?: any) => apiClient.post('/api/operations/full-pipeline', data),
  getOperation: (operationId: string) => apiClient.get(`/api/operations/${operationId}`),
  getAllOperations: () => apiClient.get('/api/operations'),
  cancelOperation: (operationId: string) => apiClient.delete(`/api/operations/${operationId}`),

  // Apollo Follow-ups
  getApolloFollowUps: (params?: { limit?: number; lookback_hours?: number }) => apiClient.get('/apollo/followups', { params }),

  // Lost lead insights
  getLostLeads: (params?: { limit?: number; salesperson?: string; type_filter?: string }) => apiClient.get('/lost-leads', { params }),
  analyzeLostLead: (leadId: number, data?: { user_identifier?: string; include_outlook_emails?: boolean }) =>
    apiClient.post(`/lost-leads/${leadId}/analysis`, data),
  generateLostLeadDraft: (data: { lead_data: any; analysis_data: any }) =>
    apiClient.post('/lost-leads/generate-draft', data),
  generateLostLeadsReport: (params?: { limit?: number; salesperson?: string; type_filter?: string; date_from?: string; date_to?: string; include_pattern_analysis?: boolean }) =>
    apiClient.post('/lost-leads/generate-report', null, { params }),

  // Dashboard
  getDashboardSummary: (params?: { engage_email?: string }) =>
    apiClient.get('/dashboard/summary', { params }),

  // Proposal follow-ups
  getProposalFollowups: (params?: { days_back?: number; no_response_days?: number; engage_email?: string; force_refresh?: boolean }) =>
    apiClient.get('/proposal-followups', { params }),
  analyzeFollowupThread: (threadData: any) => apiClient.post('/proposal-followups/analyze-thread', threadData),

  // Proposal follow-up reports
  getSavedReports: (params?: { report_type?: '90day' | 'monthly' | 'weekly' | 'complete' }) =>
    apiClient.get('/proposal-followups/reports', { params }),
  generateReport: (data: { report_type: '90day' | 'monthly' | 'weekly' | 'complete'; days_back?: number; no_response_days?: number; engage_email?: string }) =>
    apiClient.post('/proposal-followups/reports/generate', data),
  deleteReport: (reportId: string) =>
    apiClient.delete(`/proposal-followups/reports/${reportId}`),
  exportReport: (reportId: string) =>
    apiClient.get(`/proposal-followups/reports/${reportId}/export`, { responseType: 'blob' }),
  sendReportToTeams: (data: { chat_id: string; report_data: any }) =>
    apiClient.post('/proposal-followups/send-to-teams', data),
  sendDailyDigest: () =>
    apiClient.post('/proposal-followups/daily-digest/send'),
  sendIndividualDigests: () =>
    apiClient.post('/proposal-followups/daily-digest/send-individual'),
  markFollowupComplete: (data: { thread_id: string; conversation_id: string; notes?: string }) =>
    apiClient.post(`/proposal-followups/${data.thread_id}/mark-complete`, data),
  favoriteFollowup: (data: { thread_id: string; conversation_id: string }) =>
    apiClient.post(`/proposal-followups/${data.thread_id}/favorite`, data),
  unfavoriteFollowup: (thread_id: string) =>
    apiClient.delete(`/proposal-followups/${thread_id}/favorite`),
  generateDraft: (data: { thread_data: any }) =>
    apiClient.post('/proposal-followups/generate-draft', data),
  refineDraft: (data: { current_draft: string; edit_prompt: string }) =>
    apiClient.post('/proposal-followups/refine-draft', data),
  sendFollowupEmail: (data: { conversation_id: string; draft_body: string; subject: string; reply_to_message_id?: string }) =>
    apiClient.post('/proposal-followups/send-email', data),

  // NDA Analysis
  uploadNDA: (formData: FormData) =>
    apiClient.post('/nda/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }),
  getNDADocuments: (limit?: number) =>
    apiClient.get('/nda/documents', { params: { limit } }),
  getNDADocument: (ndaId: string) =>
    apiClient.get(`/nda/documents/${ndaId}`),
  deleteNDADocument: (ndaId: string) =>
    apiClient.delete(`/nda/documents/${ndaId}`),

  // Lead assignments
  createLeadAssignment: (data: {
    conversation_id: string;
    external_email: string;
    subject: string;
    assigned_to_user_id: number;
    lead_data: any;
    notes?: string;
    analysis_cache_id?: string;
  }) => apiClient.post('/lead-assignments', data),
  getReceivedAssignments: (params?: { status?: 'pending' | 'accepted' | 'completed' | 'rejected' }) =>
    apiClient.get('/lead-assignments/received', { params }),
  getSentAssignments: (params?: { status?: 'pending' | 'accepted' | 'completed' | 'rejected' }) =>
    apiClient.get('/lead-assignments/sent', { params }),
  updateAssignment: (assignmentId: string, data: { status: 'accepted' | 'completed' | 'rejected'; notes?: string }) =>
    apiClient.patch(`/lead-assignments/${assignmentId}`, data),

  // Email / Outlook OAuth
  startOutlookAuth: () => apiClient.get('/auth/outlook/start'),
  outlookAuthCallback: (data: { code: string; state: string; user_identifier?: string }) =>
    apiClient.post('/auth/outlook/callback', data),
  getEmailAuthStatus: (userIdentifier: string) => apiClient.get(`/auth/outlook/status/${userIdentifier}`),
  revokeEmailAuth: (userIdentifier: string) => apiClient.delete(`/auth/outlook/${userIdentifier}`),
  listAuthorizedUsers: () => apiClient.get('/auth/outlook/users'),

  // System Email OAuth (for automated.response@prezlab.com)
  startSystemOutlookAuth: () => apiClient.get('/auth/outlook/system/start'),
  systemOutlookAuthCallback: (data: { code: string; state: string }) =>
    apiClient.post('/auth/outlook/system/callback', data),
  getSystemEmailAuthStatus: () => apiClient.get('/auth/outlook/system/status'),
  revokeSystemEmailAuth: () => apiClient.delete('/auth/outlook/system'),

  // Microsoft Teams Integration
  getTeamsMembers: () => apiClient.get('/teams/members'),
  sendTeamsAssignmentNotification: (data: {
    assignee_user_id: string;
    assignee_name: string;
    lead_subject: string;
    lead_email: string;
    lead_company?: string;
    notes?: string;
  }) => apiClient.post('/teams/send-assignment-notification', data),

  // Export
  exportCSV: () => apiClient.get('/api/export/csv', { responseType: 'blob' }),

  // Health
  healthCheck: () => apiClient.get('/api/health'),

  // Generic HTTP methods for direct API access
  get: (url: string, config?: any) => apiClient.get(url, config),
  post: (url: string, data?: any, config?: any) => apiClient.post(url, data, config),
  put: (url: string, data?: any, config?: any) => apiClient.put(url, data, config),
  patch: (url: string, data?: any, config?: any) => apiClient.patch(url, data, config),
  delete: (url: string, config?: any) => apiClient.delete(url, config),
};

export default api;
