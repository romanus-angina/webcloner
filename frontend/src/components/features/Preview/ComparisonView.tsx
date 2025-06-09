'use client';

import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Monitor, Smartphone, Tablet, Eye, Download } from 'lucide-react';
import { PreviewFrame } from './PreviewFrame';

interface ComparisonViewProps {
  originalUrl: string;
  generatedHtml: string;
  similarityScore?: number;
  onDownload?: () => void;
}

type ViewMode = 'side-by-side' | 'tabs';
type DeviceMode = 'desktop' | 'tablet' | 'mobile';

export function ComparisonView({ 
  originalUrl, 
  generatedHtml, 
  similarityScore,
  onDownload 
}: ComparisonViewProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('side-by-side');
  const [deviceMode, setDeviceMode] = useState<DeviceMode>('desktop');
  const [activeTab, setActiveTab] = useState<'original' | 'generated'>('original');

  const getDeviceClass = () => {
    switch (deviceMode) {
      case 'mobile':
        return 'max-w-sm mx-auto';
      case 'tablet':
        return 'max-w-2xl mx-auto';
      case 'desktop':
      default:
        return 'w-full';
    }
  };

  const getFrameHeight = () => {
    switch (deviceMode) {
      case 'mobile':
        return 'h-96';
      case 'tablet':
        return 'h-[500px]';
      case 'desktop':
      default:
        return 'h-[600px]';
    }
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2 text-gray-900 text-xl font-bold">
              <Eye className="w-5 h-5" />
              Website Comparison
            </CardTitle>
            {similarityScore !== undefined && (
              <p className="text-sm text-gray-800 font-medium mt-1">
                Similarity Score: 
                <span className="font-bold text-green-600 ml-1 text-base">
                  {Math.round(similarityScore)}%
                </span>
              </p>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            {onDownload && (
              <Button size="sm" variant="outline" onClick={onDownload} className="font-semibold">
                <Download className="w-4 h-4 mr-1" />
                Download
              </Button>
            )}
          </div>
        </div>
        
        {/* Controls */}
        <div className="flex flex-col sm:flex-row gap-4 pt-4">
          {/* View Mode Toggle */}
          <div className="flex rounded-lg border p-1">
            <button
              onClick={() => setViewMode('side-by-side')}
              className={`px-3 py-1 rounded text-sm font-semibold transition-colors ${
                viewMode === 'side-by-side'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-700 hover:text-gray-900'
              }`}
            >
              Side by Side
            </button>
            <button
              onClick={() => setViewMode('tabs')}
              className={`px-3 py-1 rounded text-sm font-semibold transition-colors ${
                viewMode === 'tabs'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-700 hover:text-gray-900'
              }`}
            >
              Tabs
            </button>
          </div>

          {/* Device Mode */}
          <div className="flex rounded-lg border p-1">
            <button
              onClick={() => setDeviceMode('desktop')}
              className={`p-2 rounded transition-colors ${
                deviceMode === 'desktop'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
              title="Desktop View"
            >
              <Monitor className="w-4 h-4" />
            </button>
            <button
              onClick={() => setDeviceMode('tablet')}
              className={`p-2 rounded transition-colors ${
                deviceMode === 'tablet'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
              title="Tablet View"
            >
              <Tablet className="w-4 h-4" />
            </button>
            <button
              onClick={() => setDeviceMode('mobile')}
              className={`p-2 rounded transition-colors ${
                deviceMode === 'mobile'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
              title="Mobile View"
            >
              <Smartphone className="w-4 h-4" />
            </button>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {viewMode === 'side-by-side' ? (
          <div className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Original Website */}
              <div className="space-y-3">
                <h3 className="font-bold text-gray-900 flex items-center gap-2 text-base">
                  <div className="w-3 h-3 bg-blue-500 rounded-full" />
                  Original Website
                </h3>
                <div className={`${getDeviceClass()}`}>
                  <PreviewFrame
                    title="Original Website"
                    src={originalUrl}
                    height={getFrameHeight()}
                  />
                </div>
              </div>

              {/* Generated Website */}
              <div className="space-y-3">
                <h3 className="font-bold text-gray-900 flex items-center gap-2 text-base">
                  <div className="w-3 h-3 bg-green-500 rounded-full" />
                  Generated Clone
                </h3>
                <div className={`${getDeviceClass()}`}>
                  <PreviewFrame
                    title="Generated Clone"
                    content={generatedHtml}
                    height={getFrameHeight()}
                  />
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Tab Navigation */}
            <div className="flex border-b">
              <button
                onClick={() => setActiveTab('original')}
                className={`px-4 py-2 font-bold text-sm border-b-2 transition-colors ${
                  activeTab === 'original'
                    ? 'border-blue-500 text-blue-700'
                    : 'border-transparent text-gray-700 hover:text-gray-900'
                }`}
              >
                Original Website
              </button>
              <button
                onClick={() => setActiveTab('generated')}
                className={`px-4 py-2 font-bold text-sm border-b-2 transition-colors ${
                  activeTab === 'generated'
                    ? 'border-blue-500 text-blue-700'
                    : 'border-transparent text-gray-700 hover:text-gray-900'
                }`}
              >
                Generated Clone
              </button>
            </div>

            {/* Tab Content */}
            <div className={`${getDeviceClass()}`}>
              {activeTab === 'original' ? (
                <PreviewFrame
                  title="Original Website"
                  src={originalUrl}
                  height={getFrameHeight()}
                />
              ) : (
                <PreviewFrame
                  title="Generated Clone"
                  content={generatedHtml}
                  height={getFrameHeight()}
                />
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}