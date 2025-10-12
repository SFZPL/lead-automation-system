import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircleIcon, XCircleIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import api from '../utils/api';

const EmailCallbackPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState<string>('Processing authorization...');

  useEffect(() => {
    const handleCallback = async () => {
      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const error = searchParams.get('error');
      const errorDescription = searchParams.get('error_description');

      // Check for OAuth errors
      if (error) {
        setStatus('error');
        setMessage(errorDescription || `Authorization failed: ${error}`);
        setTimeout(() => {
          window.close(); // Close popup window if opened in popup
          navigate('/email-settings');
        }, 3000);
        return;
      }

      // Check for missing parameters
      if (!code || !state) {
        setStatus('error');
        setMessage('Missing authorization code or state parameter');
        setTimeout(() => navigate('/email-settings'), 3000);
        return;
      }

      try {
        // Get user identifier from localStorage
        const userIdentifier = localStorage.getItem('email_user_identifier');

        // Exchange code for tokens
        const response = await api.outlookAuthCallback({
          code,
          state,
          user_identifier: userIdentifier || undefined,
        });

        setStatus('success');
        setMessage(`Successfully connected: ${response.data.user_email}`);

        // Close window after 2 seconds
        setTimeout(() => {
          // If in popup, close it; parent window will detect closure
          if (window.opener) {
            window.close();
          } else {
            navigate('/email-settings');
          }
        }, 2000);
      } catch (err: any) {
        console.error('Callback error:', err);
        setStatus('error');
        setMessage(
          err?.response?.data?.detail || 'Failed to complete authorization. Please try again.'
        );
        setTimeout(() => {
          if (window.opener) {
            window.close();
          } else {
            navigate('/email-settings');
          }
        }, 3000);
      }
    };

    handleCallback();
  }, [searchParams, navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
        <div className="flex flex-col items-center text-center">
          {status === 'loading' && (
            <>
              <ArrowPathIcon className="h-12 w-12 animate-spin text-primary-600" />
              <h2 className="mt-4 text-xl font-semibold text-gray-900">
                Completing Authorization
              </h2>
              <p className="mt-2 text-sm text-gray-600">{message}</p>
            </>
          )}

          {status === 'success' && (
            <>
              <CheckCircleIcon className="h-12 w-12 text-green-600" />
              <h2 className="mt-4 text-xl font-semibold text-gray-900">Success!</h2>
              <p className="mt-2 text-sm text-gray-600">{message}</p>
              <p className="mt-4 text-xs text-gray-500">
                {window.opener ? 'This window will close automatically...' : 'Redirecting...'}
              </p>
            </>
          )}

          {status === 'error' && (
            <>
              <XCircleIcon className="h-12 w-12 text-red-600" />
              <h2 className="mt-4 text-xl font-semibold text-gray-900">Authorization Failed</h2>
              <p className="mt-2 text-sm text-gray-600">{message}</p>
              <button
                onClick={() => navigate('/email-settings')}
                className="mt-6 inline-flex items-center rounded-md border border-transparent bg-primary-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
              >
                Back to Settings
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default EmailCallbackPage;
