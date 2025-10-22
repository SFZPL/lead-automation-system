import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiClient } from '../utils/api';

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
      // Try localStorage first, then sessionStorage (for Teams tab switching)
      let token = localStorage.getItem('auth_token');
      if (!token && isTeamsEnvironment) {
        token = sessionStorage.getItem('auth_token');
        if (token) {
          // Restore to localStorage for consistency
          localStorage.setItem('auth_token', token);
        }
      }

      if (token) {
        try {
          const response = await apiClient.get('/auth/me');
          setUser(response.data);
          setIsAuthenticated(true);
        } catch (error) {
          // Token invalid or expired
          localStorage.removeItem('auth_token');
          sessionStorage.removeItem('auth_token');
          setIsAuthenticated(false);
          setUser(null);
        }
      }
      setLoading(false);
    };

    checkAuth();

    // Re-check auth when tab becomes visible (for Teams tab switching)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && isTeamsEnvironment) {
        checkAuth();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [isTeamsEnvironment]);

  const login = async (email: string, password: string): Promise<boolean> => {
    try {
      const response = await apiClient.post('/auth/login', { email, password });
      const { access_token, user: userData } = response.data;

      // Store in both localStorage and sessionStorage for Teams persistence
      localStorage.setItem('auth_token', access_token);
      if (isTeamsEnvironment) {
        sessionStorage.setItem('auth_token', access_token);
      }

      setUser(userData);
      setIsAuthenticated(true);
      return true;
    } catch (error) {
      return false;
    }
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    sessionStorage.removeItem('auth_token');
    setIsAuthenticated(false);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};
