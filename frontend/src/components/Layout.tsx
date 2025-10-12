import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  UserGroupIcon,
  CogIcon,
  Bars3Icon,
  XMarkIcon,
  GlobeAltIcon,
  EnvelopeIcon,
  SparklesIcon,
  ClipboardDocumentListIcon,
} from '@heroicons/react/24/outline';

interface LayoutProps {
  children: React.ReactNode;
}

const navigation = [
  { name: 'Perplexity Enrichment', href: '/', icon: GlobeAltIcon },
  { name: 'Lost Lead Insights', href: '/lost-leads', icon: ClipboardDocumentListIcon },
  { name: 'Unanswered Calls Follow-ups', href: '/followups', icon: EnvelopeIcon },
  { name: 'Pre-discovery Call Flow', href: '/call-flow', icon: ClipboardDocumentListIcon },
  { name: 'Email Settings', href: '/email-settings', icon: EnvelopeIcon },
  { name: 'Settings', href: '/config', icon: CogIcon },
];

export default function Layout({ children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div className="fixed inset-0 bg-gray-900/60" onClick={() => setSidebarOpen(false)} />
          <motion.div
            initial={{ x: -300 }}
            animate={{ x: 0 }}
            exit={{ x: -300 }}
            className="relative flex w-full max-w-xs flex-col bg-white"
          >
            <div className="absolute right-0 top-0 -mr-12 pt-2">
              <button
                type="button"
                className="ml-1 flex h-10 w-10 items-center justify-center rounded-full focus:outline-none focus:ring-2 focus:ring-inset focus:ring-white"
                onClick={() => setSidebarOpen(false)}
              >
                <XMarkIcon className="h-6 w-6 text-white" />
              </button>
            </div>
            <Sidebar />
          </motion.div>
        </div>
      )}

      {/* Static sidebar for desktop */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col">
        <Sidebar />
      </div>

      {/* Main content */}
      <div className="flex flex-1 flex-col lg:pl-64">
        {/* Top bar */}
        <div className="sticky top-0 z-10 border-b border-gray-200 bg-gray-50 pl-1 pt-1 sm:pl-3 sm:pt-3 lg:hidden">
          <button
            type="button"
            className="inline-flex h-12 w-12 items-center justify-center rounded-md text-gray-500 hover:text-gray-900 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary-500"
            onClick={() => setSidebarOpen(true)}
          >
            <Bars3Icon className="h-6 w-6" />
          </button>
        </div>

        {/* Page content */}
        <main className="flex-1">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="py-6"
          >
            {children}
          </motion.div>
        </main>
      </div>
    </div>
  );
}

function Sidebar() {
  const location = useLocation();

  return (
    <div className="flex min-h-0 flex-1 flex-col border-r border-gray-200 bg-white">
      <div className="flex flex-1 flex-col overflow-y-auto pt-5 pb-4">
        {/* Brand */}
        <div className="px-4">
          <div className="rounded-xl border border-primary-100 bg-white/95 p-4 shadow-sm">
            <div className="space-y-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-primary-600">PrezLab</p>
              <h1 className="text-base font-semibold leading-tight text-gray-900">Lead Automation Hub</h1>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-gray-600">
              Streamline enrichment and follow-ups without leaving your workspace.
            </p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="mt-8 flex-1 space-y-1 px-2">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href;
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`relative group flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? 'bg-primary-50 text-primary-900 shadow-sm ring-1 ring-primary-100'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                <span
                  className={`flex h-8 w-8 items-center justify-center rounded-lg border transition-colors ${
                    isActive
                      ? 'border-primary-100 bg-primary-100 text-primary-700'
                      : 'border-gray-200 text-gray-400 group-hover:border-gray-300 group-hover:text-gray-500'
                  }`}
                >
                  <item.icon className="h-5 w-5" />
                </span>
                <span>{item.name}</span>
                {isActive && (
                  <motion.span
                    layoutId="activeTab"
                    className="absolute inset-y-1 left-0 w-1 rounded-full bg-primary-500"
                  />
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* System status */}
      <div className="border-t border-gray-200 px-4 py-4">
        <div className="flex items-center justify-between rounded-xl bg-gray-50 px-3 py-2">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-success-400" />
            <span className="text-sm font-medium text-gray-700">System Online</span>
          </div>
          <span className="text-xs text-gray-500">Updated just now</span>
        </div>
      </div>
    </div>
  );
}

