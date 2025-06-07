'use client';

import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Loading } from '@/components/ui/Loading';
import { validateUrl } from '@/utils/validation';
import { Globe, Zap, Clock, Sparkles } from 'lucide-react';

interface URLInputProps {
  onSubmit: (data: URLInputData) => void;
  isLoading?: boolean;
}

export interface URLInputData {
  url: string;
  quality: 'fast' | 'balanced' | 'high';
  include_images: boolean;
  include_styling: boolean;
  custom_instructions?: string;
}

const qualityOptions = [
  {
    value: 'fast' as const,
    label: 'Fast',
    description: 'Quick clone with basic styling',
    icon: Zap,
    time: '~30s'
  },
  {
    value: 'balanced' as const,
    label: 'Balanced',
    description: 'Good quality with reasonable speed',
    icon: Clock,
    time: '~2m'
  },
  {
    value: 'high' as const,
    label: 'High Quality',
    description: 'Best quality, detailed reproduction',
    icon: Sparkles,
    time: '~5m'
  }
];

export function URLInput({ onSubmit, isLoading = false }: URLInputProps) {
  const [formData, setFormData] = useState<URLInputData>({
    url: '',
    quality: 'balanced',
    include_images: true,
    include_styling: true,
    custom_instructions: ''
  });
  const [urlError, setUrlError] = useState<string>('');

  const handleUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const url = e.target.value;
    setFormData(prev => ({ ...prev, url }));
    
    // Clear error when user starts typing
    if (urlError) {
      setUrlError('');
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate URL
    const validation = validateUrl(formData.url);
    if (!validation.isValid) {
      setUrlError(validation.error || 'Invalid URL');
      return;
    }

    onSubmit(formData);
  };

  return (
    <Card className="w-full max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Globe className="w-6 h-6 text-blue-600" />
          Clone Any Website
        </CardTitle>
        <CardDescription>
          Enter a website URL to create an aesthetically similar HTML replica using AI
        </CardDescription>
      </CardHeader>
      
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* URL Input */}
          <div>
            <Input
              label="Website URL"
              type="url"
              placeholder="https://example.com"
              value={formData.url}
              onChange={handleUrlChange}
              error={urlError}
              disabled={isLoading}
              className="text-lg"
            />
          </div>

          {/* Quality Selection */}
          <div className="space-y-3">
            <label className="text-sm font-medium text-gray-700">
              Clone Quality
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {qualityOptions.map((option) => {
                const Icon = option.icon;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setFormData(prev => ({ ...prev, quality: option.value }))}
                    disabled={isLoading}
                    className={`
                      p-4 rounded-lg border-2 text-left transition-all
                      ${formData.quality === option.value
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                      }
                      ${isLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
                    `}
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <Icon className={`w-5 h-5 ${
                        formData.quality === option.value ? 'text-blue-600' : 'text-gray-500'
                      }`} />
                      <span className="font-medium">{option.label}</span>
                      <span className="text-xs text-gray-500 ml-auto">{option.time}</span>
                    </div>
                    <p className="text-sm text-gray-600">{option.description}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Options */}
          <div className="space-y-3">
            <label className="text-sm font-medium text-gray-700">
              Include Elements
            </label>
            <div className="space-y-2">
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={formData.include_images}
                  onChange={(e) => setFormData(prev => ({ 
                    ...prev, 
                    include_images: e.target.checked 
                  }))}
                  disabled={isLoading}
                  className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                />
                <span className="text-sm">Include Images</span>
              </label>
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={formData.include_styling}
                  onChange={(e) => setFormData(prev => ({ 
                    ...prev, 
                    include_styling: e.target.checked 
                  }))}
                  disabled={isLoading}
                  className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                />
                <span className="text-sm">Include CSS Styling</span>
              </label>
            </div>
          </div>

          {/* Custom Instructions */}
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-2">
              Custom Instructions (Optional)
            </label>
            <textarea
              value={formData.custom_instructions}
              onChange={(e) => setFormData(prev => ({ 
                ...prev, 
                custom_instructions: e.target.value 
              }))}
              disabled={isLoading}
              placeholder="Any specific requirements or preferences..."
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm ring-offset-white placeholder:text-gray-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
              rows={3}
              maxLength={500}
            />
            <p className="text-xs text-gray-500 mt-1">
              {formData.custom_instructions?.length || 0}/500 characters
            </p>
          </div>

          {/* Submit Button */}
          <Button
            type="submit"
            className="w-full"
            size="lg"
            disabled={isLoading || !formData.url.trim()}
          >
            {isLoading ? (
              <>
                <Loading size="sm" className="mr-2" />
                Starting Clone Process...
              </>
            ) : (
              'Start Cloning'
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}