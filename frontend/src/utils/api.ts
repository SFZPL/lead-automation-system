import axios from 'axios';

// Create axios instance with base configuration
export const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_BASE || 'http://localhost:8000',
  timeout: 300000, // 5 minutes for long operations
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

  // Export
  exportCSV: () => apiClient.get('/api/export/csv', { responseType: 'blob' }),

  // Health
  healthCheck: () => apiClient.get('/api/health'),
};

export default api;