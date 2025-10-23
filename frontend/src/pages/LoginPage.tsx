import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { SparklesIcon } from '@heroicons/react/24/outline';

const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const success = await login(email, password);
      if (!success) {
        setError('Invalid email or password');
        setPassword('');
      }
    } catch (err) {
      setError('An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-navy-900 via-navy-800 to-primary-900 relative overflow-hidden">
      {/* Decorative background elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary-500 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-pulse-slow"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-coral-500 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-pulse-slow" style={{animationDelay: '1s'}}></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-yellow-500 rounded-full mix-blend-multiply filter blur-xl opacity-10 animate-pulse-slow" style={{animationDelay: '2s'}}></div>
      </div>

      <div className="relative max-w-md w-full mx-4">
        {/* Login Card */}
        <div className="bg-white rounded-2xl shadow-2xl overflow-hidden">
          {/* Header with gradient */}
          <div className="bg-gradient-to-r from-primary-600 to-primary-500 px-8 py-6 text-center">
            <div className="flex items-center justify-center gap-3">
              <div className="bg-white rounded-lg p-2 shadow-md">
                <SparklesIcon className="h-6 w-6 text-primary-600" />
              </div>
              <div className="text-left">
                <h1 className="text-xl font-bold text-white">PREZLAB</h1>
                <p className="text-primary-100 text-xs">Lead Automation Hub</p>
              </div>
            </div>
          </div>

          {/* Form */}
          <div className="px-8 py-8">
            <div className="text-center mb-6">
              <h2 className="text-xl font-semibold text-gray-900">Welcome back</h2>
              <p className="mt-1 text-sm text-gray-600">Sign in to access your dashboard</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
                  Email Address
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  required
                  className="appearance-none block w-full px-4 py-3 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition duration-150"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
                  Password
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  required
                  className="appearance-none block w-full px-4 py-3 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition duration-150"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>

              <div className="flex items-center">
                <input
                  id="remember-me"
                  name="remember-me"
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded cursor-pointer"
                />
                <label htmlFor="remember-me" className="ml-2 block text-sm text-gray-700 cursor-pointer">
                  Remember me
                </label>
              </div>

              {error && (
                <div className="rounded-lg bg-coral-50 border border-coral-200 p-4">
                  <p className="text-sm font-medium text-coral-800">{error}</p>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full flex justify-center items-center gap-2 py-3 px-4 border border-transparent rounded-lg text-sm font-semibold text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition duration-150 shadow-lg hover:shadow-xl"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span>Signing in...</span>
                  </>
                ) : (
                  <>
                    <SparklesIcon className="h-5 w-5" />
                    <span>Sign in</span>
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Footer */}
          <div className="px-8 py-6 bg-gray-50 border-t border-gray-100">
            <p className="text-xs text-center text-gray-500">
              Secure access to your PrezLab Lead Automation tools
            </p>
          </div>
        </div>

        {/* Bottom tagline */}
        <p className="mt-6 text-center text-sm text-white opacity-80">
          Powered by PrezLab Intelligence
        </p>
      </div>
    </div>
  );
};

export default LoginPage;
