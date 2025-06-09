'use client';

import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Copy, Download, Code, FileText } from 'lucide-react';

interface CodeViewerProps {
  htmlContent: string;
  cssContent?: string;
  onDownload?: () => void;
}

export function CodeViewer({ htmlContent, cssContent, onDownload }: CodeViewerProps) {
  const [activeTab, setActiveTab] = useState<'html' | 'css'>('html');
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const content = activeTab === 'html' ? htmlContent : cssContent || '';
    
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy content:', err);
    }
  };

  const currentContent = activeTab === 'html' ? htmlContent : cssContent || '';

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-gray-900 font-bold text-xl">
            <Code className="w-5 h-5" />
            Generated Code
          </CardTitle>
          
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={handleCopy}
              disabled={!currentContent}
              className="font-semibold"
            >
              <Copy className="w-4 h-4 mr-1" />
              {copied ? 'Copied!' : 'Copy'}
            </Button>
            {onDownload && (
              <Button size="sm" variant="outline" onClick={onDownload} className="font-semibold">
                <Download className="w-4 h-4 mr-1" />
                Download
              </Button>
            )}
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b-2 border-gray-200">
          <button
            onClick={() => setActiveTab('html')}
            className={`px-4 py-3 font-bold text-sm border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === 'html'
                ? 'border-blue-500 text-blue-700 bg-blue-50'
                : 'border-transparent text-gray-700 hover:text-gray-900 hover:bg-gray-50'
            }`}
          >
            <FileText className="w-4 h-4" />
            HTML
          </button>
          {cssContent && (
            <button
              onClick={() => setActiveTab('css')}
              className={`px-4 py-3 font-bold text-sm border-b-2 transition-colors flex items-center gap-2 ${
                activeTab === 'css'
                  ? 'border-blue-500 text-blue-700 bg-blue-50'
                  : 'border-transparent text-gray-700 hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              <Code className="w-4 h-4" />
              CSS
            </button>
          )}
        </div>
      </CardHeader>

      <CardContent>
        <div className="relative">
          <pre className="bg-gray-900 border-2 border-gray-300 rounded-lg p-6 overflow-x-auto text-sm max-h-96 overflow-y-auto">
            <code className={`language-${activeTab} text-gray-100 font-mono leading-relaxed`}>
              {currentContent || `No ${activeTab.toUpperCase()} content available`}
            </code>
          </pre>
          
          {!currentContent && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-100 bg-opacity-90 rounded-lg">
              <p className="text-gray-700 font-semibold">No {activeTab.toUpperCase()} content to display</p>
            </div>
          )}
        </div>

        {/* Code Statistics */}
        {currentContent && (
          <div className="mt-4 flex items-center gap-6 text-sm bg-gray-50 p-3 rounded-lg border">
            <span className="font-semibold text-gray-800">
              Lines: <span className="font-bold text-gray-900">{currentContent.split('\n').length}</span>
            </span>
            <span className="font-semibold text-gray-800">
              Characters: <span className="font-bold text-gray-900">{currentContent.length.toLocaleString()}</span>
            </span>
            <span className="font-semibold text-gray-800">
              Size: <span className="font-bold text-gray-900">{(new Blob([currentContent]).size / 1024).toFixed(1)} KB</span>
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}