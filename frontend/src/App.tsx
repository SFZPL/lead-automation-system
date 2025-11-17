import React from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Layout from './components/Layout';
import SettingsPage from './pages/SettingsPage';
import DashboardPage from './pages/DashboardPage';
import PerplexityPage from './pages/PerplexityPage';
import LostLeadsPage from './pages/LostLeadsPage';
import ReEngagePage from './pages/ReEngagePage';
import FollowupsHubPage from './pages/FollowupsHubPage';
import EmailCallbackPage from './pages/EmailCallbackPage';
import CallFlowPage from './pages/CallFlowPage';
import KnowledgeBasePage from './pages/KnowledgeBasePage';
import NDAAnalysisPage from './pages/NDAAnalysisPage';
import PipelineReportsPage from './pages/PipelineReportsPage';
import LoginPage from './pages/LoginPage';

// Detect Teams environment
const isTeamsEnvironment = () => {
  const inIframe = window.self !== window.top;
  const userAgent = navigator.userAgent.toLowerCase();
  return userAgent.includes('teams') ||
         (inIframe && (
           window.location.ancestorOrigins?.[0]?.includes('teams.microsoft.com') ||
           document.referrer.includes('teams.microsoft.com')
         ));
};

// Create a client with enhanced state preservation for Teams
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: isTeamsEnvironment() ? true : false, // Refetch when returning to Teams tab
      retry: 1,
      staleTime: isTeamsEnvironment() ? 60000 : 30000, // Longer stale time in Teams (1 minute)
      cacheTime: isTeamsEnvironment() ? 600000 : 300000, // Keep cache longer in Teams (10 minutes)
    },
  },
});

// Route persistence component for Teams environment
const RoutePersistence = ({ children }: { children: React.ReactNode }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const inTeams = isTeamsEnvironment();
  const [hasRestored, setHasRestored] = React.useState(false);

  // Restore route on mount (with slight delay to ensure DOM is ready)
  React.useEffect(() => {
    if (inTeams && !hasRestored) {
      const savedRoute = localStorage.getItem('teams_lastRoute');
      console.log('Teams environment detected. Current:', location.pathname, 'Saved:', savedRoute);

      if (savedRoute && savedRoute !== '/' && savedRoute !== location.pathname && savedRoute !== '/auth/outlook/callback') {
        console.log('Restoring route to:', savedRoute);
        setTimeout(() => {
          navigate(savedRoute, { replace: true });
        }, 100);
      }
      setHasRestored(true);
    }
  }, [inTeams, hasRestored, location.pathname, navigate]);

  // Save current route when it changes (but not on first mount)
  React.useEffect(() => {
    if (inTeams && hasRestored && location.pathname !== '/auth/outlook/callback') {
      console.log('Saving route:', location.pathname);
      localStorage.setItem('teams_lastRoute', location.pathname);
    }
  }, [location.pathname, inTeams, hasRestored]);

  return <>{children}</>;
};

const AppContent = () => {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <Router>
      <RoutePersistence>
        <div className="App">
          <Layout>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/enrichment" element={<PerplexityPage />} />
              <Route path="/lost-leads" element={<LostLeadsPage />} />
              <Route path="/re-engage" element={<ReEngagePage />} />
              <Route path="/followups" element={<FollowupsHubPage />} />
              <Route path="/call-flow" element={<CallFlowPage />} />
              <Route path="/knowledge-base" element={<KnowledgeBasePage />} />
              <Route path="/nda-analysis" element={<NDAAnalysisPage />} />
              <Route path="/pipeline-reports" element={<PipelineReportsPage />} />
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
      </RoutePersistence>
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




