import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import { Toaster } from 'react-hot-toast';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import ConfigPage from './pages/ConfigPage';
import PerplexityPage from './pages/PerplexityPage';
import ApolloFollowUpsPage from './pages/ApolloFollowUpsPage';
import LostLeadsPage from './pages/LostLeadsPage';
import EmailSettingsPage from './pages/EmailSettingsPage';
import EmailCallbackPage from './pages/EmailCallbackPage';
import CallFlowPage from './pages/CallFlowPage';

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

function App() {
  return (
    <QueryClientProvider client={queryClient}>
        <Router>
          <div className="App">
            <Layout>
              <Routes>
                <Route path="/" element={<PerplexityPage />} />
                <Route path="/lost-leads" element={<LostLeadsPage />} />
                <Route path="/followups" element={<ApolloFollowUpsPage />} />
                <Route path="/call-flow" element={<CallFlowPage />} />
                <Route path="/email-settings" element={<EmailSettingsPage />} />
                <Route path="/auth/outlook/callback" element={<EmailCallbackPage />} />
                <Route path="/config" element={<ConfigPage />} />
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
    </QueryClientProvider>
  );
}

export default App;




