import React from 'react';
import { cn } from '@/utils/helpers';

interface ProgressBarProps {
  value: number; // 0-100
  className?: string;
  showPercentage?: boolean;
  label?: string;
}

const ProgressBar: React.FC<ProgressBarProps> = ({ 
  value, 
  className, 
  showPercentage = true,
  label = "Progress"
}) => {
  const clampedValue = Math.min(Math.max(value, 0), 100);

  return (
    <div className={cn("w-full", className)}>
      {showPercentage && (
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm font-bold text-gray-900">{label}</span>
          <span className="text-sm font-bold text-gray-800">{Math.round(clampedValue)}%</span>
        </div>
      )}
      <div className="w-full bg-gray-200 rounded-full h-3 border border-gray-300">
        <div
          className="bg-blue-600 h-full rounded-full transition-all duration-300 ease-out shadow-sm"
          style={{ width: `${clampedValue}%` }}
        />
      </div>
    </div>
  );
};

export { ProgressBar };
