// Updated CloneInterface with better contrast for the info cards
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
    originalUrl: string; // ADD THIS - store the original URL
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
    originalUrl: '', // ADD THIS
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
      
      // STORE THE ORIGINAL URL
      setState(prev => ({
        ...prev,
        originalUrl: inputData.url // ADD THIS LINE
      }));
      
      const request = {
        url: inputData.url,
        quality: inputData.quality,
        include_images: inputData.include_images,
        include_styling: inputData.include_styling,
        max_depth: 1,
        custom_instructions: inputData.custom_instructions || undefined
      };
  
      const response = await cloneWebsite(request);
      
      setState(prev => ({
        ...prev,
        view: 'processing',
        currentSession: response
        // originalUrl is already set above
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

        if (response.status === 'completed') {
          addLog('info', `Clone process completed successfully! Similarity: ${response.result?.similarity_score?.toFixed(1)}%`);
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
        } else {
          const currentStep = response.progress?.[response.progress.length - 1];
          if (currentStep?.message) {
            addLog('info', `${currentStep.step_name}: ${currentStep.message}`);
          }
        }
      } catch (err) {
        addLog('warning', 'Failed to get status update');
      }
    }, 3000);

    setState(prev => ({
      ...prev,
      pollingInterval: interval
    }));
  };

  useEffect(() => {
    return () => {
      if (state.pollingInterval) {
        clearInterval(state.pollingInterval);
      }
    };
  }, [state.pollingInterval]);

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
      originalUrl: '', // CLEAR THE URL
      logs: []
    });
  };

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

  const getOriginalUrl = () => {
    return state.originalUrl || 'https://example.com';
  };

  const renderContent = () => {
    switch (state.view) {
      case 'input':
        return (
          <div className="max-w-4xl mx-auto space-y-8">
            <URLInput onSubmit={handleCloneSubmit} isLoading={isLoading} />
            
            {/* Enhanced Info Cards with Better Contrast */}
            <Card className="bg-white border-gray-200 shadow-sm">
              <CardContent className="p-8">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-8 text-center">
                  <div className="space-y-4">
                    <div className="w-16 h-16 bg-blue-500 rounded-xl flex items-center justify-center mx-auto">
                      <span className="text-3xl">🌐</span>
                    </div>
                    <div>
                      <h3 className="font-bold text-lg text-gray-900 mb-2">Enter URL</h3>
                      <p className="text-sm text-gray-700 leading-relaxed">
                        Paste any public website URL to get started with AI-powered cloning
                      </p>
                    </div>
                  </div>
                  <div className="space-y-4">
                    <div className="w-16 h-16 bg-green-500 rounded-xl flex items-center justify-center mx-auto">
                      <span className="text-3xl">🤖</span>
                    </div>
                    <div>
                      <h3 className="font-bold text-lg text-gray-900 mb-2">AI Analysis</h3>
                      <p className="text-sm text-gray-700 leading-relaxed">
                        Our AI analyzes the design and detects UI components automatically
                      </p>
                    </div>
                  </div>
                  <div className="space-y-4">
                    <div className="w-16 h-16 bg-purple-500 rounded-xl flex items-center justify-center mx-auto">
                      <span className="text-3xl">✨</span>
                    </div>
                    <div>
                      <h3 className="font-bold text-lg text-gray-900 mb-2">Get Clone</h3>
                      <p className="text-sm text-gray-700 leading-relaxed">
                        Download your clean, semantic HTML replica instantly
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        );

      case 'processing':
        return (
          <div className="max-w-4xl mx-auto space-y-6">
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

            {state.currentSession && (
              <ProgressTracker
                steps={state.currentSession.progress}
                currentStatus={state.currentSession.status}
                sessionId={state.currentSession.session_id}
                estimatedCompletion={state.currentSession.estimated_completion}
                startTime={state.currentSession.created_at}
              />
            )}

            <LogViewer logs={state.logs} />
          </div>
        );

        case 'results':
          return (
            <div className="max-w-6xl mx-auto space-y-6">
              {/* Enhanced Header with Better Contrast */}
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-white p-6 rounded-lg border shadow-sm">
                <div className="flex items-center gap-4">
                  <CheckCircle className="w-8 h-8 text-green-600" />
                  <div>
                    <h1 className="text-2xl font-bold text-gray-900">Clone Completed Successfully!</h1>
                    <p className="text-gray-700 font-medium">Your website clone is ready for download</p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <Button 
                    variant="outline" 
                    onClick={() => setState(prev => ({ ...prev, showCode: !prev.showCode }))}
                    className="font-semibold text-gray-900 border-gray-400 hover:bg-gray-100"
                  >
                    {state.showCode ? 'Hide Code' : 'View Code'}
                  </Button>
                  <Button 
                    variant="outline" 
                    onClick={handleStartOver}
                    className="font-semibold text-gray-900 border-gray-400 hover:bg-gray-100"
                  >
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Clone Another
                  </Button>
                </div>
              </div>
        
              {/* Rest of results content... */}
              {state.currentSession?.result && (
                <>
                  <ComparisonView
                    originalUrl={getOriginalUrl()}
                    generatedHtml={state.currentSession.result.html_content}
                    similarityScore={state.currentSession.result.similarity_score}
                    onDownload={handleDownload}
                  />
        
                  {state.showCode && (
                    <CodeViewer
                      htmlContent={state.currentSession.result.html_content}
                      cssContent={state.currentSession.result.css_content}
                      onDownload={handleDownload}
                    />
                  )}
                </>
              )}
        
              {state.currentSession && (
                <StatusCard
                  sessionId={state.currentSession.session_id}
                  url={getOriginalUrl()}
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