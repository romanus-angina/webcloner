'use client';

import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { Loading } from '@/components/ui/Loading';
import { CheckCircle, XCircle, Clock, AlertCircle } from 'lucide-react';
import { type ProgressStep, type CloneStatus } from '@/services/api';
import { formatDuration } from '@/utils/helpers';

interface ProgressTrackerProps {
  steps: ProgressStep[];
  currentStatus: CloneStatus;
  sessionId?: string;
  estimatedCompletion?: string;
  startTime?: string;
}

const statusIcons: Record<CloneStatus, React.ComponentType<{ className?: string }>> = {
  pending: Clock,
  analyzing: Loading,
  scraping: Loading,
  generating: Loading,
  refining: Loading,
  completed: CheckCircle,
  failed: XCircle,
};

const statusColors: Record<CloneStatus, string> = {
  pending: 'text-gray-600',
  analyzing: 'text-blue-600',
  scraping: 'text-blue-600',
  generating: 'text-blue-600',
  refining: 'text-blue-600',
  completed: 'text-green-600',
  failed: 'text-red-600',
};

const statusLabels: Record<CloneStatus, string> = {
  pending: 'Pending',
  analyzing: 'Analyzing Website',
  scraping: 'Scraping Content',
  generating: 'Generating HTML',
  refining: 'Refining Output',
  completed: 'Completed',
  failed: 'Failed',
};

export function ProgressTracker({ 
  steps, 
  currentStatus, 
  sessionId,
  estimatedCompletion,
  startTime 
}: ProgressTrackerProps) {
  const overallProgress = steps.length > 0 
    ? steps.reduce((sum, step) => sum + step.progress_percentage, 0) / steps.length
    : 0;

  const StatusIcon = statusIcons[currentStatus];
  const statusColor = statusColors[currentStatus];
  const statusLabel = statusLabels[currentStatus];

  const getElapsedTime = () => {
    if (!startTime) return null;
    const elapsed = (Date.now() - new Date(startTime).getTime()) / 1000;
    return formatDuration(elapsed);
  };

  const getEstimatedRemaining = () => {
    if (!estimatedCompletion) return null;
    const remaining = (new Date(estimatedCompletion).getTime() - Date.now()) / 1000;
    return remaining > 0 ? formatDuration(remaining) : null;
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <StatusIcon className={`w-5 h-5 ${statusColor}`} />
            <span className="text-gray-900 font-bold">Cloning Progress</span>
          </div>
          {sessionId && (
            <span className="text-sm font-medium text-gray-700">
              ID: {sessionId.slice(0, 8)}...
            </span>
          )}
        </CardTitle>
      </CardHeader>
      
      <CardContent className="space-y-6">
        {/* Overall Progress */}
        <div>
          <div className="flex justify-between items-center mb-2">
            <span className={`font-bold text-base ${statusColor}`}>{statusLabel}</span>
            <span className="text-sm font-semibold text-gray-800">
              {Math.round(overallProgress)}%
            </span>
          </div>
          <ProgressBar value={overallProgress} showPercentage={false} />
        </div>

        {/* Time Information */}
        {(getElapsedTime() || getEstimatedRemaining()) && (
          <div className="grid grid-cols-2 gap-4 text-sm">
            {getElapsedTime() && (
              <div>
                <span className="text-gray-700 font-semibold">Elapsed:</span>
                <div className="font-bold text-gray-900 text-base">{getElapsedTime()}</div>
              </div>
            )}
            {getEstimatedRemaining() && (
              <div>
                <span className="text-gray-700 font-semibold">Remaining:</span>
                <div className="font-bold text-gray-900 text-base">{getEstimatedRemaining()}</div>
              </div>
            )}
          </div>
        )}

        {/* Step Details */}
        {steps.length > 0 && (
          <div className="space-y-3">
            <h4 className="font-bold text-gray-900">Detailed Steps</h4>
            <div className="space-y-2">
              {steps.map((step, index) => (
                <StepIndicator key={index} step={step} />
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface StepIndicatorProps {
  step: ProgressStep;
}

function StepIndicator({ step }: StepIndicatorProps) {
  const getStepIcon = () => {
    switch (step.status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-600" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-600" />;
      case 'pending':
        return <Clock className="w-4 h-4 text-gray-500" />;
      default:
        return <Loading size="sm" className="text-blue-600" />;
    }
  };

  const getStepColor = () => {
    switch (step.status) {
      case 'completed':
        return 'text-green-800 bg-green-50 border-green-200';
      case 'failed':
        return 'text-red-800 bg-red-50 border-red-200';
      case 'pending':
        return 'text-gray-700 bg-gray-50 border-gray-200';
      default:
        return 'text-blue-800 bg-blue-50 border-blue-200';
    }
  };

  return (
    <div className={`p-4 rounded-lg border ${getStepColor()}`}>
      <div className="flex items-center gap-3">
        {getStepIcon()}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <span className="font-bold text-base">{step.step_name}</span>
            <span className="text-sm font-semibold">{Math.round(step.progress_percentage)}%</span>
          </div>
          {step.message && (
            <p className="text-sm font-medium mt-1">{step.message}</p>
          )}
          {step.error && (
            <p className="text-sm text-red-700 font-medium mt-1 flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              {step.error}
            </p>
          )}
        </div>
      </div>
      {step.progress_percentage > 0 && (
        <div className="mt-3">
          <ProgressBar 
            value={step.progress_percentage} 
            showPercentage={false}
            className="h-2"
          />
        </div>
      )}
    </div>
  );
}