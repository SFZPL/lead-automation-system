import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Layout from './components/Layout';
import SettingsPage from './pages/SettingsPage';
import DashboardPage from './pages/DashboardPage';
import PerplexityPage from './pages/PerplexityPage';
import LostLeadsPage from './pages/LostLeadsPage';
import FollowupsHubPage from './pages/FollowupsHubPage';
import EmailCallbackPage from './pages/EmailCallbackPage';
import CallFlowPage from './pages/CallFlowPage';
import LoginPage from './pages/LoginPage';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30000, // 30 seconds
    },
  },
});

const AppContent = () => {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <Router>
      <div className="App">
        <Layout>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/enrichment" element={<PerplexityPage />} />
            <Route path="/lost-leads" element={<LostLeadsPage />} />
            <Route path="/followups" element={<FollowupsHubPage />} />
            <Route path="/call-flow" element={<CallFlowPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/auth/outlook/callback" element={<EmailCallbackPage />} />
          </Routes>
        </Layout>
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: '#363636',
              color: '#fff',
            },
            success: {
              style: {
                background: '#10b981',
              },
            },
            error: {
              style: {
                background: '#ef4444',
              },
            },
          }}
        />
      </div>
    </Router>
  );
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;




