import React from 'react';
import { Tab } from '@headlessui/react';
import {
  EnvelopeIcon,
  PhoneIcon,
  ChartBarIcon
} from '@heroicons/react/24/outline';
import ProposalFollowupsPage from './ProposalFollowupsPage';
import ApolloFollowUpsPage from './ApolloFollowUpsPage';

function classNames(...classes: string[]) {
  return classes.filter(Boolean).join(' ');
}

export default function FollowupsHubPage() {
  const tabs = [
    {
      name: 'Proposal Follow-ups',
      icon: EnvelopeIcon,
      component: ProposalFollowupsPage,
      description: 'Track unanswered emails and pending proposals from engage@prezlab.com'
    },
    {
      name: 'Unanswered Calls',
      icon: PhoneIcon,
      component: ApolloFollowUpsPage,
      description: 'Follow up on unanswered calls from Apollo'
    },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="flex items-center justify-center h-10 w-10 rounded-lg bg-indigo-600">
            <ChartBarIcon className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Follow-ups Hub</h1>
            <p className="text-sm text-gray-600">
              Manage all your follow-up activities in one place
            </p>
          </div>
        </div>
      </div>

      <Tab.Group>
        <Tab.List className="flex space-x-1 rounded-xl bg-indigo-50 p-1 mb-6">
          {tabs.map((tab) => (
            <Tab
              key={tab.name}
              className={({ selected }) =>
                classNames(
                  'w-full rounded-lg py-3 px-4 text-sm font-medium leading-5 transition-all',
                  'focus:outline-none focus:ring-2 ring-offset-2 ring-offset-indigo-50 ring-white ring-opacity-60',
                  selected
                    ? 'bg-white text-indigo-700 shadow'
                    : 'text-indigo-600 hover:bg-white/50 hover:text-indigo-800'
                )
              }
            >
              <div className="flex items-center justify-center gap-2">
                <tab.icon className="h-5 w-5" />
                <span>{tab.name}</span>
              </div>
            </Tab>
          ))}
        </Tab.List>

        <Tab.Panels>
          {tabs.map((tab, idx) => (
            <Tab.Panel
              key={idx}
              className="rounded-xl bg-white focus:outline-none"
            >
              <tab.component />
            </Tab.Panel>
          ))}
        </Tab.Panels>
      </Tab.Group>
    </div>
  );
}
