import React, { useEffect, useState } from 'react';
import { useMutation, useQuery } from 'react-query';
import toast from 'react-hot-toast';
import {
  EnvelopeIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import api from '../utils/api';

interface EmailAuthStatus {
  authorized: boolean;
  user_email?: string;
  user_name?: string;
  expires_soon?: boolean;
}

const EmailSettingsPage: React.FC = () => {
  const [userIdentifier, setUserIdentifier] = useState<string>('');
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  // Load user identifier from localStorage or use email input
  useEffect(() => {
    const savedIdentifier = localStorage.getItem('email_user_identifier');
    if (savedIdentifier) {
      setUserIdentifier(savedIdentifier);
    }
  }, []);

  // Check authorization status
  const authStatusQuery = useQuery(
    ['email-auth-status', userIdentifier],
    async () => {
      if (!userIdentifier.trim()) return null;
      const response = await api.getEmailAuthStatus(userIdentifier.trim());
      return response.data as EmailAuthStatus;
    },
    {
      enabled: !!userIdentifier.trim(),
      refetchInterval: 30000, // Refresh every 30 seconds
    }
  );

  // Start OAuth flow
  const startAuthMutation = useMutation(
    async () => {
      if (!userIdentifier.trim()) {
        throw new Error('Please enter your email address');
      }

      // Save identifier for later
      localStorage.setItem('email_user_identifier', userIdentifier.trim());

      const response = await api.startOutlookAuth();
      return response.data;
    },
    {
      onSuccess: (data) => {
        setIsAuthenticating(true);
        // Open Microsoft authorization page in new window
        const authWindow = window.open(
          data.authorization_url,
          'outlook-auth',
          'width=600,height=700,scrollbars=yes'
        );

        // Poll for completion
        const pollInterval = setInterval(() => {
          if (authWindow?.closed) {
            clearInterval(pollInterval);
            setIsAuthenticating(false);
            authStatusQuery.refetch();
          }
        }, 1000);
      },
      onError: (error: any) => {
        toast.error(error?.response?.data?.detail || 'Failed to start authorization');
        setIsAuthenticating(false);
      },
    }
  );

  // Revoke authorization
  const revokeMutation = useMutation(
    async () => {
      if (!userIdentifier.trim()) return;
      await api.revokeEmailAuth(userIdentifier.trim());
    },
    {
      onSuccess: () => {
        toast.success('Email authorization revoked');
        authStatusQuery.refetch();
      },
      onError: (error: any) => {
        toast.error(error?.response?.data?.detail || 'Failed to revoke authorization');
      },
    }
  );

  const authStatus = authStatusQuery.data;
  const isAuthorized = authStatus?.authorized ?? false;

  return (
    <div className="space-y-6 px-4 sm:px-6 lg:px-8">
      <header>
        <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.2em] text-primary-600">
          <EnvelopeIcon className="h-4 w-4" />
          Email Integration
        </div>
        <h1 className="mt-2 text-2xl font-semibold text-gray-900">Outlook / Microsoft 365</h1>
        <p className="mt-2 max-w-3xl text-sm text-gray-600">
          Connect your Microsoft email account to enable email search in lost lead analysis. Your credentials are
          stored securely and you can revoke access at any time.
        </p>
      </header>

      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900">Authorization Status</h2>
        <div className="mt-4 space-y-4">
          {/* Email Input */}
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700">
              Your Email Address
            </label>
            <input
              id="email"
              type="email"
              value={userIdentifier}
              onChange={(e) => setUserIdentifier(e.target.value)}
              placeholder="your.email@company.com"
              disabled={isAuthorized}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:bg-gray-100"
            />
            <p className="mt-1 text-xs text-gray-500">
              This identifier is used to store your credentials. Use your Microsoft/Outlook email address.
            </p>
          </div>

          {/* Status Display */}
          {authStatusQuery.isLoading && (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <ArrowPathIcon className="h-4 w-4 animate-spin" />
              Checking authorization status...
            </div>
          )}

          {!authStatusQuery.isLoading && isAuthorized && authStatus && (
            <div className="rounded-lg border border-green-200 bg-green-50 p-4">
              <div className="flex items-start gap-3">
                <CheckCircleIcon className="h-5 w-5 text-green-600" />
                <div className="flex-1">
                  <h3 className="text-sm font-semibold text-green-900">Connected</h3>
                  <p className="mt-1 text-sm text-green-700">
                    {authStatus.user_name && <span className="font-medium">{authStatus.user_name}</span>}
                    {authStatus.user_email && (
                      <span className="ml-2 text-green-600">({authStatus.user_email})</span>
                    )}
                  </p>
                  {authStatus.expires_soon && (
                    <p className="mt-2 text-xs text-amber-600">
                      ⚠️ Your access token will expire soon. Click "Reconnect" to refresh.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {!authStatusQuery.isLoading && !isAuthorized && userIdentifier.trim() && (
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
              <div className="flex items-start gap-3">
                <XCircleIcon className="h-5 w-5 text-gray-400" />
                <div>
                  <h3 className="text-sm font-semibold text-gray-900">Not Connected</h3>
                  <p className="mt-1 text-sm text-gray-600">
                    Click "Connect Email" below to authorize access to your Microsoft email.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-3">
            {!isAuthorized ? (
              <button
                type="button"
                onClick={() => startAuthMutation.mutate()}
                disabled={!userIdentifier.trim() || isAuthenticating || startAuthMutation.isLoading}
                className="inline-flex items-center rounded-md border border-transparent bg-primary-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isAuthenticating ? (
                  <>
                    <ArrowPathIcon className="mr-2 h-4 w-4 animate-spin" />
                    Waiting for authorization...
                  </>
                ) : (
                  <>
                    <EnvelopeIcon className="mr-2 h-4 w-4" />
                    Connect Email
                  </>
                )}
              </button>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => startAuthMutation.mutate()}
                  disabled={isAuthenticating || startAuthMutation.isLoading}
                  className="inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
                >
                  <ArrowPathIcon className="mr-2 h-4 w-4" />
                  Reconnect
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (window.confirm('Are you sure you want to revoke email access?')) {
                      revokeMutation.mutate();
                    }
                  }}
                  disabled={revokeMutation.isLoading}
                  className="inline-flex items-center rounded-md border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 shadow-sm hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
                >
                  <TrashIcon className="mr-2 h-4 w-4" />
                  Revoke Access
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Information Section */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900">How It Works</h2>
        <div className="mt-4 space-y-3 text-sm text-gray-600">
          <div className="flex gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-600">
              1
            </span>
            <p>
              Click "Connect Email" and sign in with your Microsoft/Outlook account. You'll be asked to grant
              permission to read your emails.
            </p>
          </div>
          <div className="flex gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-600">
              2
            </span>
            <p>
              Your credentials are stored securely on this server. We never store your password, only OAuth tokens that
              can be revoked anytime.
            </p>
          </div>
          <div className="flex gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-600">
              3
            </span>
            <p>
              When analyzing lost leads, the system will automatically search your emails for relevant conversations
              with that contact or company.
            </p>
          </div>
          <div className="flex gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-600">
              4
            </span>
            <p>
              You can revoke access at any time by clicking "Revoke Access". This will delete all stored tokens.
            </p>
          </div>
        </div>
      </div>

      {/* Permissions Section */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900">Required Permissions</h2>
        <div className="mt-4 space-y-2 text-sm text-gray-600">
          <div className="flex items-center gap-2">
            <CheckCircleIcon className="h-4 w-4 text-green-600" />
            <span className="font-medium">Mail.Read</span> - Read your email messages
          </div>
          <div className="flex items-center gap-2">
            <CheckCircleIcon className="h-4 w-4 text-green-600" />
            <span className="font-medium">User.Read</span> - Read your profile information
          </div>
          <div className="flex items-center gap-2">
            <CheckCircleIcon className="h-4 w-4 text-green-600" />
            <span className="font-medium">offline_access</span> - Maintain access without re-authentication
          </div>
        </div>
      </div>
    </div>
  );
};

export default EmailSettingsPage;
