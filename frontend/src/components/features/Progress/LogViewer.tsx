'use client';

import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { ChevronDown, ChevronUp, Info, AlertTriangle, XCircle } from 'lucide-react';

interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error';
  message: string;
  details?: string;
}

interface LogViewerProps {
  logs: LogEntry[];
  maxHeight?: string;
}

export function LogViewer({ logs, maxHeight = '300px' }: LogViewerProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedLevel, setSelectedLevel] = useState<'all' | 'info' | 'warning' | 'error'>('all');

  const filteredLogs = logs.filter(log => 
    selectedLevel === 'all' || log.level === selectedLevel
  );

  const getLevelIcon = (level: LogEntry['level']) => {
    switch (level) {
      case 'info':
        return <Info className="w-4 h-4 text-blue-600" />;
      case 'warning':
        return <AlertTriangle className="w-4 h-4 text-yellow-600" />;
      case 'error':
        return <XCircle className="w-4 h-4 text-red-600" />;
    }
  };

  const getLevelColor = (level: LogEntry['level']) => {
    switch (level) {
      case 'info':
        return 'text-blue-600';
      case 'warning':
        return 'text-yellow-600';
      case 'error':
        return 'text-red-600';
    }
  };

  if (logs.length === 0) {
    return null;
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Process Logs</CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? (
              <>
                <ChevronUp className="w-4 h-4 mr-1" />
                Collapse
              </>
            ) : (
              <>
                <ChevronDown className="w-4 h-4 mr-1" />
                View Logs ({logs.length})
              </>
            )}
          </Button>
        </div>
      </CardHeader>
      
      {isExpanded && (
        <CardContent className="space-y-4">
          {/* Filter Buttons */}
          <div className="flex gap-2">
            {['all', 'info', 'warning', 'error'].map((level) => (
              <Button
                key={level}
                size="sm"
                variant={selectedLevel === level ? 'default' : 'outline'}
                onClick={() => setSelectedLevel(level as any)}
              >
                {level.charAt(0).toUpperCase() + level.slice(1)}
                {level !== 'all' && (
                  <span className="ml-1 text-xs">
                    ({logs.filter(log => log.level === level).length})
                  </span>
                )}
              </Button>
            ))}
          </div>

          {/* Log Entries */}
          <div 
            className="space-y-2 overflow-y-auto border rounded-md p-3 bg-gray-50"
            style={{ maxHeight }}
          >
            {filteredLogs.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">
                No logs for selected level
              </p>
            ) : (
              filteredLogs.map((log, index) => (
                <div key={index} className="flex gap-3 text-sm">
                  {getLevelIcon(log.level)}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </span>
                      <span className={`font-medium ${getLevelColor(log.level)}`}>
                        {log.level.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-gray-700">{log.message}</p>
                    {log.details && (
                      <details className="mt-1">
                        <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700">
                          View details
                        </summary>
                        <pre className="mt-1 text-xs bg-white p-2 rounded border overflow-x-auto">
                          {log.details}
                        </pre>
                      </details>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      )}
    </Card>
  );
}