'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { URLInput, type URLInputData } from './URLInput/URLInput';
import { ProgressTracker } from './Progress/ProgressTracker';
import { ComparisonView } from './Preview/ComparisonView';
import { CodeViewer } from './Preview/CodeViewer';
import { StatusCard } from './Progress/StatusCard';
import { LogViewer } from './Progress/LogViewer';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { useCloning } from '@/hooks/useCloning';
import { type CloneResponse, type CloneStatus } from '@/services/api';
import { AlertCircle, CheckCircle, ArrowLeft, RefreshCw } from 'lucide-react';

type ViewState = 'input' | 'processing' | 'results' | 'error';

interface CloneInterfaceState {
  view: ViewState;
  currentSession: CloneResponse | null;
  pollingInterval: NodeJS.Timeout | null;
  showCode: boolean;
  logs: Array<{
    timestamp: string;
    level: 'info' | 'warning' | 'error';
    message: string;
    details?: string;
  }>;
}

export function CloneInterface() {
  const { isLoading, data, error, cloneWebsite, getStatus, reset } = useCloning();
  const [state, setState] = useState<CloneInterfaceState>({
    view: 'input',
    currentSession: null,
    pollingInterval: null,
    showCode: false,
    logs: []
  });

  // Add log entry
  const addLog = useCallback((level: 'info' | 'warning' | 'error', message: string, details?: string) => {
    setState(prev => ({
      ...prev,
      logs: [...prev.logs, {
        timestamp: new Date().toISOString(),
        level,
        message,
        details
      }]
    }));
  }, []);

  // Handle cloning submission
  const handleCloneSubmit = async (inputData: URLInputData) => {
    try {
      addLog('info', `Starting clone process for ${inputData.url}`);
      
      const request = {
        url: inputData.url,
        quality: inputData.quality,
        include_images: inputData.include_images,
        include_styling: inputData.include_styling,
        max_depth: 1, // Single page for now
        custom_instructions: inputData.custom_instructions || undefined
      };

      const response = await cloneWebsite(request);
      
      setState(prev => ({
        ...prev,
        view: 'processing',
        currentSession: response
      }));

      addLog('info', `Clone process initiated with session ID: ${response.session_id}`);
      startPolling(response.session_id);
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to start cloning process';
      addLog('error', errorMessage);
      setState(prev => ({ ...prev, view: 'error' }));
    }
  };

  // Start polling for status updates
  const startPolling = (sessionId: string) => {
    if (state.pollingInterval) {
      clearInterval(state.pollingInterval);
    }

    const interval = setInterval(async () => {
      try {
        const response = await getStatus(sessionId);
        
        setState(prev => ({
          ...prev,
          currentSession: response
        }));

        // Check if process is complete
        if (response.status === 'completed') {
          addLog('info', 'Clone process completed successfully');
          setState(prev => ({
            ...prev,
            view: 'results',
            pollingInterval: null
          }));
          clearInterval(interval);
        } else if (response.status === 'failed') {
          addLog('error', 'Clone process failed', response.error_message);
          setState(prev => ({
            ...prev,
            view: 'error',
            pollingInterval: null
          }));
          clearInterval(interval);
        }
      } catch (err) {
        addLog('warning', 'Failed to get status update');
        // Continue polling - don't stop on temporary errors
      }
    }, 2000); // Poll every 2 seconds

    setState(prev => ({
      ...prev,
      pollingInterval: interval
    }));
  };

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (state.pollingInterval) {
        clearInterval(state.pollingInterval);
      }
    };
  }, [state.pollingInterval]);

  // Handle starting over
  const handleStartOver = () => {
    if (state.pollingInterval) {
      clearInterval(state.pollingInterval);
    }
    
    reset();
    setState({
      view: 'input',
      currentSession: null,
      pollingInterval: null,
      showCode: false,
      logs: []
    });
  };

  // Handle download
  const handleDownload = () => {
    if (!state.currentSession?.result?.html_content) return;

    const htmlContent = state.currentSession.result.html_content;
    const blob = new Blob([htmlContent], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = 'cloned-website.html';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    addLog('info', 'Website downloaded successfully');
  };

  // Handle manual refresh
  const handleRefresh = async () => {
    if (!state.currentSession?.session_id) return;

    try {
      const response = await getStatus(state.currentSession.session_id);
      setState(prev => ({
        ...prev,
        currentSession: response
      }));
      addLog('info', 'Status refreshed manually');
    } catch (err) {
      addLog('error', 'Failed to refresh status');
    }
  };

  // Render based on current view state
  const renderContent = () => {
    switch (state.view) {
      case 'input':
        return (
          <div className="max-w-4xl mx-auto space-y-6">
            <URLInput onSubmit={handleCloneSubmit} isLoading={isLoading} />
            
            {/* Quick Info */}
            <Card>
              <CardContent className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
                  <div>
                    <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-3">
                      <span className="text-2xl">🌐</span>
                    </div>
                    <h3 className="font-medium">Enter URL</h3>
                    <p className="text-sm text-gray-600">Paste any public website URL</p>
                  </div>
                  <div>
                    <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-3">
                      <span className="text-2xl">🤖</span>
                    </div>
                    <h3 className="font-medium">AI Analysis</h3>
                    <p className="text-sm text-gray-600">Our AI analyzes the design</p>
                  </div>
                  <div>
                    <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-3">
                      <span className="text-2xl">✨</span>
                    </div>
                    <h3 className="font-medium">Get Clone</h3>
                    <p className="text-sm text-gray-600">Download your HTML replica</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        );

      case 'processing':
        return (
          <div className="max-w-4xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
              <Button variant="ghost" onClick={handleStartOver}>
                <ArrowLeft className="w-4 h-4 mr-2" />
                Start Over
              </Button>
              <Button variant="outline" onClick={handleRefresh}>
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
            </div>

            {/* Progress Tracking */}
            {state.currentSession && (
              <ProgressTracker
                steps={state.currentSession.progress}
                currentStatus={state.currentSession.status}
                sessionId={state.currentSession.session_id}
                estimatedCompletion={state.currentSession.estimated_completion}
                startTime={state.currentSession.created_at}
              />
            )}

            {/* Log Viewer */}
            <LogViewer logs={state.logs} />
          </div>
        );

      case 'results':
        return (
          <div className="max-w-6xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <CheckCircle className="w-6 h-6 text-green-600" />
                <div>
                  <h1 className="text-xl font-semibold">Clone Completed Successfully!</h1>
                  <p className="text-gray-600">Your website clone is ready</p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setState(prev => ({ ...prev, showCode: !prev.showCode }))}>
                  {state.showCode ? 'Hide Code' : 'View Code'}
                </Button>
                <Button variant="outline" onClick={handleStartOver}>
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Clone Another
                </Button>
              </div>
            </div>

            {/* Results Display */}
            {state.currentSession?.result && (
              <>
                {/* Comparison View */}
                <ComparisonView
                  originalUrl={state.currentSession.request?.url || ''}
                  generatedHtml={state.currentSession.result.html_content}
                  similarityScore={state.currentSession.result.similarity_score}
                  onDownload={handleDownload}
                />

                {/* Code Viewer (conditional) */}
                {state.showCode && (
                  <CodeViewer
                    htmlContent={state.currentSession.result.html_content}
                    cssContent={state.currentSession.result.css_content}
                    onDownload={handleDownload}
                  />
                )}
              </>
            )}

            {/* Session Info */}
            {state.currentSession && (
              <StatusCard
                sessionId={state.currentSession.session_id}
                url={state.currentSession.request?.url || 'Unknown URL'}
                status={state.currentSession.status}
                createdAt={state.currentSession.created_at}
                similarityScore={state.currentSession.result?.similarity_score}
                onDownload={handleDownload}
              />
            )}
          </div>
        );

      case 'error':
        return (
          <div className="max-w-2xl mx-auto">
            <Card>
              <CardContent className="p-8 text-center">
                <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
                <h2 className="text-xl font-semibold mb-2">Something went wrong</h2>
                <p className="text-gray-600 mb-6">
                  {error || state.currentSession?.error_message || 'An unexpected error occurred during the cloning process.'}
                </p>
                <div className="flex gap-3 justify-center">
                  <Button onClick={handleStartOver}>
                    Try Again
                  </Button>
                  <Button variant="outline" onClick={() => setState(prev => ({ ...prev, view: 'input' }))}>
                    Go Back
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      {renderContent()}
    </div>
  );
}