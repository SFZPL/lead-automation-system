import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiClient, api } from '../utils/api';

// Unique storage keys to avoid conflicts with other Teams apps
const PREZLAB_AUTH_TOKEN_KEY = 'prezlab_auth_token';
const PREZLAB_REFRESH_TOKEN_KEY = 'prezlab_refresh_token';

interface User {
  id: number;
  email: string;
  name: string;
  role: string;
}

interface AuthContextType {
  isAuthenticated: boolean;
  user: User | null;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isTeamsEnvironment, setIsTeamsEnvironment] = useState<boolean>(false);

  // Detect if running in Microsoft Teams
  useEffect(() => {
    const detectTeams = () => {
      // Check for Teams context
      const inIframe = window.self !== window.top;
      const userAgent = navigator.userAgent.toLowerCase();
      const isTeams = userAgent.includes('teams') ||
                      (inIframe && (
                        window.location.ancestorOrigins?.[0]?.includes('teams.microsoft.com') ||
                        document.referrer.includes('teams.microsoft.com')
                      ));

      setIsTeamsEnvironment(isTeams);

      if (isTeams) {
        console.log('Running in Microsoft Teams environment');
      }
    };

    detectTeams();
  }, []);

  // Check if user is authenticated on mount and when tab becomes visible
  useEffect(() => {
    const checkAuth = async () => {
      // Try to get access token
      let token = localStorage.getItem(PREZLAB_AUTH_TOKEN_KEY) || sessionStorage.getItem(PREZLAB_AUTH_TOKEN_KEY);

      if (token) {
        try {
          const response = await apiClient.get('/auth/me');
          setUser(response.data);
          setIsAuthenticated(true);
          setLoading(false);
          return;
        } catch (error) {
          // Access token expired or invalid, try refresh token
          console.log('Access token expired, trying refresh token');
        }
      }

      // Try to get refresh token for persistent login
      const refreshToken = localStorage.getItem(PREZLAB_REFRESH_TOKEN_KEY) || sessionStorage.getItem(PREZLAB_REFRESH_TOKEN_KEY);

      if (refreshToken) {
        try {
          console.log('Using refresh token to get new access token');
          const response = await api.refreshToken(refreshToken);
          const { access_token, refresh_token, user } = response.data;

          // Store tokens with unique keys
          localStorage.setItem(PREZLAB_AUTH_TOKEN_KEY, access_token);
          localStorage.setItem(PREZLAB_REFRESH_TOKEN_KEY, refresh_token);

          if (isTeamsEnvironment) {
            sessionStorage.setItem(PREZLAB_AUTH_TOKEN_KEY, access_token);
            sessionStorage.setItem(PREZLAB_REFRESH_TOKEN_KEY, refresh_token);
          }

          setUser(user);
          setIsAuthenticated(true);
          console.log('Successfully refreshed auth session');
        } catch (error) {
          console.error('Refresh token invalid or expired:', error);
          // Both tokens invalid, need to log in again
          localStorage.removeItem(PREZLAB_AUTH_TOKEN_KEY);
          localStorage.removeItem(PREZLAB_REFRESH_TOKEN_KEY);
          sessionStorage.removeItem(PREZLAB_AUTH_TOKEN_KEY);
          sessionStorage.removeItem(PREZLAB_REFRESH_TOKEN_KEY);
          setIsAuthenticated(false);
          setUser(null);
        }
      }

      setLoading(false);
    };

    checkAuth();

    // Auto-refresh auth check every 6 hours to keep session alive
    const refreshInterval = setInterval(() => {
      checkAuth();
    }, 6 * 60 * 60 * 1000); // 6 hours

    // Re-check auth when tab becomes visible (for Teams tab switching)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        checkAuth();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      clearInterval(refreshInterval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [isTeamsEnvironment]);

  const login = async (email: string, password: string): Promise<boolean> => {
    try {
      const response = await api.login(email, password);
      const { access_token, refresh_token, user: userData } = response.data;

      // Store tokens with unique keys for Teams compatibility
      localStorage.setItem(PREZLAB_AUTH_TOKEN_KEY, access_token);
      localStorage.setItem(PREZLAB_REFRESH_TOKEN_KEY, refresh_token);

      if (isTeamsEnvironment) {
        sessionStorage.setItem(PREZLAB_AUTH_TOKEN_KEY, access_token);
        sessionStorage.setItem(PREZLAB_REFRESH_TOKEN_KEY, refresh_token);
      }

      setUser(userData);
      setIsAuthenticated(true);
      console.log('Login successful - refresh token will persist across sessions');
      return true;
    } catch (error) {
      return false;
    }
  };

  const logout = () => {
    localStorage.removeItem(PREZLAB_AUTH_TOKEN_KEY);
    localStorage.removeItem(PREZLAB_REFRESH_TOKEN_KEY);
    sessionStorage.removeItem(PREZLAB_AUTH_TOKEN_KEY);
    sessionStorage.removeItem(PREZLAB_REFRESH_TOKEN_KEY);
    setIsAuthenticated(false);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};
