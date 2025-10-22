import axios from 'axios';

// Create axios instance with base configuration

export const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_BASE || 'http://localhost:8000',
  timeout: 600000, // 10 minutes for long operations
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Add authentication token if available
    const token = localStorage.getItem('auth_token');
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
      // Handle unauthorized - redirect to login if needed
      localStorage.removeItem('auth_token');
      // window.location.href = '/login';
    } else if (error.response?.status === 500) {
      console.error('Server error:', error.response.data);
    }
    
    return Promise.reject(error);
  }
);

// API helper functions
export const api = {
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

  // Dashboard
  getDashboardSummary: (params?: { engage_email?: string }) =>
    apiClient.get('/dashboard/summary', { params }),

  // Proposal follow-ups
  getProposalFollowups: (params?: { days_back?: number; no_response_days?: number; engage_email?: string; force_refresh?: boolean }) =>
    apiClient.get('/proposal-followups', { params }),
  analyzeFollowupThread: (threadData: any) => apiClient.post('/proposal-followups/analyze-thread', threadData),

  // Proposal follow-up reports
  getSavedReports: (params?: { report_type?: '90day' | 'monthly' | 'weekly' }) =>
    apiClient.get('/proposal-followups/reports', { params }),
  generateReport: (data: { report_type: '90day' | 'monthly' | 'weekly'; days_back?: number; no_response_days?: number; engage_email?: string }) =>
    apiClient.post('/proposal-followups/reports/generate', data),
  markFollowupComplete: (data: { thread_id: string; conversation_id: string; notes?: string }) =>
    apiClient.post(`/proposal-followups/${data.thread_id}/mark-complete`, data),
  generateDraft: (data: { thread_data: any }) =>
    apiClient.post('/proposal-followups/generate-draft', data),
  refineDraft: (data: { current_draft: string; edit_prompt: string }) =>
    apiClient.post('/proposal-followups/refine-draft', data),
  sendFollowupEmail: (data: { conversation_id: string; draft_body: string; subject: string; reply_to_message_id?: string }) =>
    apiClient.post('/proposal-followups/send-email', data),

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
