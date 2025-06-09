'use client';

import React, { useState } from 'react';
import { AlertCircle, RefreshCw, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Loading } from '@/components/ui/Loading';

interface PreviewFrameProps {
  title: string;
  src?: string;
  content?: string;
  height?: string;
}

export function PreviewFrame({ title, src, content, height = 'h-96' }: PreviewFrameProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleLoad = () => {
    setIsLoading(false);
    setHasError(false);
  };

  const handleError = () => {
    setIsLoading(false);
    setHasError(true);
  };

  const handleRefresh = () => {
    setIsLoading(true);
    setHasError(false);
    setRefreshKey(prev => prev + 1);
  };

  const getSrcDoc = () => {
    if (content) {
      // Ensure the content is valid HTML
      const validHtml = content.startsWith('<!DOCTYPE html') || content.startsWith('<html') 
        ? content 
        : `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Generated Clone</title></head><body>${content}</body></html>`;
      return validHtml;
    }
    return undefined;
  };

  return (
    <div className={`relative border rounded-lg overflow-hidden ${height} bg-white`}>
      {/* Loading State */}
      {isLoading && (
        <div className="absolute inset-0 bg-white flex items-center justify-center z-10">
          <div className="text-center">
            <Loading size="lg" className="mx-auto mb-2" />
            <p className="text-sm text-gray-600">Loading {title.toLowerCase()}...</p>
          </div>
        </div>
      )}

      {/* Error State */}
      {hasError && !isLoading && (
        <div className="absolute inset-0 bg-gray-50 flex items-center justify-center z-10">
          <div className="text-center p-6">
            <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-3" />
            <h3 className="font-medium text-gray-900 mb-2">Failed to load {title.toLowerCase()}</h3>
            <p className="text-sm text-gray-600 mb-4">
              {src ? 'The website could not be loaded in the preview.' : 'The generated content could not be displayed.'}
            </p>
            <div className="flex gap-2 justify-center">
              <Button size="sm" variant="outline" onClick={handleRefresh}>
                <RefreshCw className="w-4 h-4 mr-1" />
                Try Again
              </Button>
              {src && (
                <Button size="sm" variant="outline" onClick={() => window.open(src, '_blank')}>
                  <ExternalLink className="w-4 h-4 mr-1" />
                  Open in New Tab
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Frame */}
      <iframe
        key={refreshKey}
        src={src}
        srcDoc={getSrcDoc()}
        title={title}
        className="w-full h-full border-0"
        onLoad={handleLoad}
        onError={handleError}
        sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-presentation"
        loading="lazy"
        style={{ backgroundColor: 'white' }}
      />
    </div>
  );
}