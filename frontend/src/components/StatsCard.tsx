import React from 'react';
import { motion } from 'framer-motion';

interface StatsCardProps {
  title: string;
  value: string | number;
  icon: React.ComponentType<any>;
  color: 'blue' | 'green' | 'purple' | 'indigo' | 'red' | 'yellow';
  trend?: string;
  description?: string;
}

const colorClasses = {
  blue: {
    bg: 'bg-blue-500',
    text: 'text-blue-600',
    bgLight: 'bg-blue-50',
  },
  green: {
    bg: 'bg-green-500',
    text: 'text-green-600',
    bgLight: 'bg-green-50',
  },
  purple: {
    bg: 'bg-purple-500',
    text: 'text-purple-600',
    bgLight: 'bg-purple-50',
  },
  indigo: {
    bg: 'bg-indigo-500',
    text: 'text-indigo-600',
    bgLight: 'bg-indigo-50',
  },
  red: {
    bg: 'bg-red-500',
    text: 'text-red-600',
    bgLight: 'bg-red-50',
  },
  yellow: {
    bg: 'bg-yellow-500',
    text: 'text-yellow-600',
    bgLight: 'bg-yellow-50',
  },
};

export default function StatsCard({ 
  title, 
  value, 
  icon: Icon, 
  color, 
  trend, 
  description 
}: StatsCardProps) {
  const colors = colorClasses[color];
  
  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      className="card overflow-hidden hover:shadow-lg transition-shadow duration-200"
    >
      <div className="card-body">
        <div className="flex items-center">
          <div className="flex-shrink-0">
            <div className={`inline-flex items-center justify-center p-3 rounded-md ${colors.bgLight}`}>
              <Icon className={`h-6 w-6 ${colors.text}`} />
            </div>
          </div>
          <div className="ml-5 w-0 flex-1">
            <dl>
              <dt className="text-sm font-medium text-gray-500 truncate">
                {title}
              </dt>
              <dd className="flex items-baseline">
                <div className="text-2xl font-semibold text-gray-900">
                  {value}
                </div>
                {trend && (
                  <div className={`ml-2 flex items-baseline text-sm font-semibold ${
                    trend.startsWith('+') ? 'text-green-600' : 
                    trend.startsWith('-') ? 'text-red-600' : 'text-gray-600'
                  }`}>
                    {trend}
                  </div>
                )}
              </dd>
              {description && (
                <dd className="text-sm text-gray-600 mt-1">
                  {description}
                </dd>
              )}
            </dl>
          </div>
        </div>
      </div>
    </motion.div>
  );
}