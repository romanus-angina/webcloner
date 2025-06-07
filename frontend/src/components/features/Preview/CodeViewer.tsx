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
          <CardTitle className="flex items-center gap-2">
            <Code className="w-5 h-5" />
            Generated Code
          </CardTitle>
          
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={handleCopy}
              disabled={!currentContent}
            >
              <Copy className="w-4 h-4 mr-1" />
              {copied ? 'Copied!' : 'Copy'}
            </Button>
            {onDownload && (
              <Button size="sm" variant="outline" onClick={onDownload}>
                <Download className="w-4 h-4 mr-1" />
                Download
              </Button>
            )}
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b">
          <button
            onClick={() => setActiveTab('html')}
            className={`px-4 py-2 font-medium text-sm border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === 'html'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            <FileText className="w-4 h-4" />
            HTML
          </button>
          {cssContent && (
            <button
              onClick={() => setActiveTab('css')}
              className={`px-4 py-2 font-medium text-sm border-b-2 transition-colors flex items-center gap-2 ${
                activeTab === 'css'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-600 hover:text-gray-900'
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
          <pre className="bg-gray-50 border rounded-lg p-4 overflow-x-auto text-sm max-h-96 overflow-y-auto">
            <code className={`language-${activeTab}`}>
              {currentContent || `No ${activeTab.toUpperCase()} content available`}
            </code>
          </pre>
          
          {!currentContent && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-50 bg-opacity-75">
              <p className="text-gray-500">No {activeTab.toUpperCase()} content to display</p>
            </div>
          )}
        </div>

        {/* Code Statistics */}
        {currentContent && (
          <div className="mt-4 flex items-center gap-4 text-sm text-gray-500">
            <span>
              Lines: {currentContent.split('\n').length}
            </span>
            <span>
              Characters: {currentContent.length}
            </span>
            <span>
              Size: {(new Blob([currentContent]).size / 1024).toFixed(1)} KB
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}