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
        return 'text-blue-700';
      case 'warning':
        return 'text-yellow-700';
      case 'error':
        return 'text-red-700';
    }
  };

  if (logs.length === 0) {
    return null;
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-bold text-gray-900">Process Logs</CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="font-semibold"
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
                className="font-semibold"
              >
                {level.charAt(0).toUpperCase() + level.slice(1)}
                {level !== 'all' && (
                  <span className="ml-1 text-xs font-bold">
                    ({logs.filter(log => log.level === level).length})
                  </span>
                )}
              </Button>
            ))}
          </div>

          {/* Log Entries */}
          <div 
            className="space-y-2 overflow-y-auto border-2 border-gray-200 rounded-md p-4 bg-gray-50"
            style={{ maxHeight }}
          >
            {filteredLogs.length === 0 ? (
              <p className="text-sm text-gray-600 text-center py-4 font-medium">
                No logs for selected level
              </p>
            ) : (
              filteredLogs.map((log, index) => (
                <div key={index} className="flex gap-3 text-sm bg-white p-3 rounded border">
                  {getLevelIcon(log.level)}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-gray-600">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </span>
                      <span className={`font-bold text-xs ${getLevelColor(log.level)}`}>
                        {log.level.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-gray-900 font-medium">{log.message}</p>
                    {log.details && (
                      <details className="mt-2">
                        <summary className="cursor-pointer text-xs text-gray-700 hover:text-gray-900 font-semibold">
                          View details
                        </summary>
                        <pre className="mt-2 text-xs bg-gray-100 p-2 rounded border overflow-x-auto font-mono text-gray-800">
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