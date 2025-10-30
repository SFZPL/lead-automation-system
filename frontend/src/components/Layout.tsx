import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  CogIcon,
  Bars3Icon,
  XMarkIcon,
  EnvelopeIcon,
  ClipboardDocumentListIcon,
  ArrowRightOnRectangleIcon,
  HomeIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  SparklesIcon,
  HeartIcon,
  DocumentTextIcon,
} from '@heroicons/react/24/outline';
import { useAuth } from '../contexts/AuthContext';

interface LayoutProps {
  children: React.ReactNode;
}

const navigation = [
  { name: 'Dashboard', href: '/', icon: HomeIcon },
  { name: 'Unenriched Leads', href: '/enrichment', icon: SparklesIcon },
  { name: 'Lost Lead Insights', href: '/lost-leads', icon: ClipboardDocumentListIcon },
  { name: 'Follow-ups Hub', href: '/followups', icon: EnvelopeIcon },
  { name: 'Pre-discovery Call Flow', href: '/call-flow', icon: ClipboardDocumentListIcon },
  { name: 'Knowledge Base', href: '/knowledge-base', icon: DocumentTextIcon },
  { name: 'Settings', href: '/settings', icon: CogIcon },
];

export default function Layout({ children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

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
            <Sidebar collapsed={false} onToggleCollapse={() => {}} />
          </motion.div>
        </div>
      )}

      {/* Static sidebar for desktop */}
      <div className={`hidden lg:fixed lg:inset-y-0 lg:flex lg:flex-col transition-all duration-300 ${sidebarCollapsed ? 'lg:w-20' : 'lg:w-64'}`}>
        <Sidebar collapsed={sidebarCollapsed} onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)} />
      </div>

      {/* Main content */}
      <div className={`flex flex-1 flex-col transition-all duration-300 ${sidebarCollapsed ? 'lg:pl-20' : 'lg:pl-64'}`}>
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

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
}

function Sidebar({ collapsed, onToggleCollapse }: SidebarProps) {
  const location = useLocation();
  const { logout } = useAuth();

  return (
    <div className="flex min-h-0 flex-1 flex-col border-r border-gray-200 bg-white">
      <div className="flex flex-1 flex-col overflow-y-auto pt-5 pb-4">
        {/* Brand and Collapse Toggle */}
        <div className={`px-4 flex items-start ${collapsed ? 'justify-center' : 'justify-between'}`}>
          {!collapsed && (
            <div className="flex-1">
              <div className="rounded-xl border border-primary-100 bg-white/95 p-4 shadow-sm">
                <div className="space-y-1">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-primary-600">PrezLab</p>
                  <h1 className="text-base font-semibold leading-tight text-gray-900">Lead Automation Hub</h1>
                </div>
              </div>
            </div>
          )}

          {/* Collapse Toggle Button */}
          <button
            onClick={onToggleCollapse}
            className={`flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200 text-gray-400 hover:border-gray-300 hover:bg-gray-50 hover:text-gray-600 transition-colors flex-shrink-0 ${!collapsed ? 'ml-2 mt-1' : ''}`}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? (
              <ChevronRightIcon className="h-4 w-4" />
            ) : (
              <ChevronLeftIcon className="h-4 w-4" />
            )}
          </button>
        </div>

        {/* Navigation */}
        <nav className="mt-8 flex-1 space-y-1 px-2">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href;
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`relative group flex items-center ${collapsed ? 'justify-center' : 'gap-3'} rounded-xl px-3 py-2 text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? 'bg-primary-50 text-primary-900 shadow-sm ring-1 ring-primary-100'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
                title={collapsed ? item.name : undefined}
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
                {!collapsed && <span>{item.name}</span>}
                {isActive && !collapsed && (
                  <motion.span
                    layoutId="activeTab"
                    className="absolute inset-y-1 left-0 w-1 rounded-full bg-primary-500"
                  />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Logout button */}
        <div className="px-2 pb-4">
          <button
            onClick={logout}
            className={`relative group flex w-full items-center ${collapsed ? 'justify-center' : 'gap-3'} rounded-xl px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 hover:text-gray-900 transition-all duration-200`}
            title={collapsed ? 'Logout' : undefined}
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200 text-gray-400 group-hover:border-gray-300 group-hover:text-gray-500 transition-colors">
              <ArrowRightOnRectangleIcon className="h-5 w-5" />
            </span>
            {!collapsed && <span>Logout</span>}
          </button>
        </div>
      </div>

    </div>
  );
}

