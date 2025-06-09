'use client';

import React from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { CheckCircle, XCircle, Clock, Download, Eye, Trash2, Zap } from 'lucide-react';
import { type CloneStatus } from '@/services/api';
import { truncateUrl } from '@/utils/helpers';

interface StatusCardProps {
  sessionId: string;
  url: string;
  status: CloneStatus;
  createdAt: string;
  onView?: () => void;
  onDownload?: () => void;
  onDelete?: () => void;
  similarityScore?: number;
  componentAnalysis?: {
    total_components: number;
    detection_time: number;
    components_replicated: Record<string, number>;
  };
}

export function StatusCard({
  sessionId,
  url,
  status,
  createdAt,
  onView,
  onDownload,
  onDelete,
  similarityScore,
  componentAnalysis
}: StatusCardProps) {
  const getStatusDisplay = () => {
    switch (status) {
      case 'completed':
        return {
          icon: CheckCircle,
          color: 'text-green-600',
          bgColor: 'bg-green-50',
          text: 'Completed'
        };
      case 'failed':
        return {
          icon: XCircle,
          color: 'text-red-600',
          bgColor: 'bg-red-50',
          text: 'Failed'
        };
      case 'pending':
      case 'analyzing':
      case 'scraping':
      case 'generating':
      case 'refining':
        return {
          icon: Clock,
          color: 'text-blue-600',
          bgColor: 'bg-blue-50',
          text: 'Processing'
        };
      default:
        return {
          icon: Clock,
          color: 'text-gray-600',
          bgColor: 'bg-gray-50',
          text: 'Unknown'
        };
    }
  };

  const statusDisplay = getStatusDisplay();
  const StatusIcon = statusDisplay.icon;

  return (
    <Card className="w-full">
      <CardContent className="p-4">
        <div className="space-y-4">
          {/* Header */}
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0">
              <h3 className="font-medium text-gray-900 truncate">
                {truncateUrl(url, 40)}
              </h3>
              <p className="text-sm text-gray-500">
                {new Date(createdAt).toLocaleString()}
              </p>
            </div>
            <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${statusDisplay.bgColor} ${statusDisplay.color}`}>
              <StatusIcon className="w-3 h-3" />
              {statusDisplay.text}
            </div>
          </div>

          {/* Metrics Grid */}
          {status === 'completed' && (
            <div className="grid grid-cols-2 gap-4 text-sm">
              {/* Similarity Score */}
              {similarityScore !== undefined && (
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <span className="text-gray-600">Similarity:</span>
                  <span className="font-medium text-green-600">
                    {Math.round(similarityScore)}%
                  </span>
                </div>
              )}

              {/* Component Analysis */}
              {componentAnalysis && (
                <div className="flex items-center gap-2">
                  <Zap className="w-3 h-3 text-blue-500" />
                  <span className="text-gray-600">Components:</span>
                  <span className="font-medium text-blue-600">
                    {componentAnalysis.total_components}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Component Breakdown */}
          {status === 'completed' && componentAnalysis?.components_replicated && (
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="text-xs font-medium text-gray-700 mb-2">Components Detected</div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(componentAnalysis.components_replicated).map(([type, count]) => (
                  <span 
                    key={type}
                    className="px-2 py-1 bg-white rounded text-xs text-gray-600 border"
                  >
                    {count} {type}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Session ID */}
          <div className="text-xs text-gray-400">
            Session: {sessionId.slice(0, 8)}...
          </div>

          {/* Actions */}
          <div className="flex gap-2 pt-2">
            {status === 'completed' && onView && (
              <Button size="sm" variant="outline" onClick={onView}>
                <Eye className="w-4 h-4 mr-1" />
                View
              </Button>
            )}
            {status === 'completed' && onDownload && (
              <Button size="sm" variant="outline" onClick={onDownload}>
                <Download className="w-4 h-4 mr-1" />
                Download
              </Button>
            )}
            {onDelete && (
              <Button 
                size="sm" 
                variant="outline" 
                onClick={onDelete}
                className="ml-auto text-red-600 hover:text-red-700 hover:bg-red-50"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}