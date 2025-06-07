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
  pending: 'text-gray-500',
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
            <span>Cloning Progress</span>
          </div>
          {sessionId && (
            <span className="text-sm font-normal text-gray-500">
              ID: {sessionId.slice(0, 8)}...
            </span>
          )}
        </CardTitle>
      </CardHeader>
      
      <CardContent className="space-y-6">
        {/* Overall Progress */}
        <div>
          <div className="flex justify-between items-center mb-2">
            <span className={`font-medium ${statusColor}`}>{statusLabel}</span>
            <span className="text-sm text-gray-500">
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
                <span className="text-gray-500">Elapsed:</span>
                <div className="font-medium">{getElapsedTime()}</div>
              </div>
            )}
            {getEstimatedRemaining() && (
              <div>
                <span className="text-gray-500">Remaining:</span>
                <div className="font-medium">{getEstimatedRemaining()}</div>
              </div>
            )}
          </div>
        )}

        {/* Step Details */}
        {steps.length > 0 && (
          <div className="space-y-3">
            <h4 className="font-medium text-gray-700">Detailed Steps</h4>
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
        return <Clock className="w-4 h-4 text-gray-400" />;
      default:
        return <Loading size="sm" className="text-blue-600" />;
    }
  };

  const getStepColor = () => {
    switch (step.status) {
      case 'completed':
        return 'text-green-700 bg-green-50 border-green-200';
      case 'failed':
        return 'text-red-700 bg-red-50 border-red-200';
      case 'pending':
        return 'text-gray-600 bg-gray-50 border-gray-200';
      default:
        return 'text-blue-700 bg-blue-50 border-blue-200';
    }
  };

  return (
    <div className={`p-3 rounded-lg border ${getStepColor()}`}>
      <div className="flex items-center gap-3">
        {getStepIcon()}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <span className="font-medium">{step.step_name}</span>
            <span className="text-sm">{Math.round(step.progress_percentage)}%</span>
          </div>
          {step.message && (
            <p className="text-sm opacity-75 mt-1">{step.message}</p>
          )}
          {step.error && (
            <p className="text-sm text-red-600 mt-1 flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              {step.error}
            </p>
          )}
        </div>
      </div>
      {step.progress_percentage > 0 && (
        <div className="mt-2">
          <ProgressBar 
            value={step.progress_percentage} 
            showPercentage={false}
            className="h-1"
          />
        </div>
      )}
    </div>
  );
}
