import React from 'react';
import { motion } from 'framer-motion';

interface ProgressBarProps {
  progress: number;
  className?: string;
  color?: 'blue' | 'green' | 'purple' | 'red' | 'yellow';
  showLabel?: boolean;
}

const colorClasses = {
  blue: 'bg-blue-600',
  green: 'bg-green-600',
  purple: 'bg-purple-600',
  red: 'bg-red-600',
  yellow: 'bg-yellow-600',
};

export default function ProgressBar({ 
  progress, 
  className = '', 
  color = 'blue', 
  showLabel = false 
}: ProgressBarProps) {
  const clampedProgress = Math.max(0, Math.min(100, progress));

  return (
    <div className={`progress-bar ${className}`}>
      <motion.div
        className={`progress-fill ${colorClasses[color]}`}
        initial={{ width: 0 }}
        animate={{ width: `${clampedProgress}%` }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
      >
        {showLabel && (
          <div className="flex items-center justify-center h-full">
            <span className="text-xs font-medium text-white">
              {Math.round(clampedProgress)}%
            </span>
          </div>
        )}
      </motion.div>
    </div>
  );
}