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

const DebugButton = ({ formData, isLoading, urlError }: any) => {
  const isFormValid = formData.url.trim().length > 0 && !urlError;
  
  console.log('Debug Info:', {
    url: formData.url,
    urlLength: formData.url.trim().length,
    urlError,
    isLoading,
    isFormValid
  });

  return (
    <div className="p-4 bg-yellow-50 border border-yellow-200 rounded text-sm">
      <strong>Debug Info:</strong>
      <ul className="mt-2 space-y-1">
        <li>URL: "{formData.url}"</li>
        <li>URL Length: {formData.url.trim().length}</li>
        <li>URL Error: {urlError || 'None'}</li>
        <li>Is Loading: {isLoading ? 'Yes' : 'No'}</li>
        <li>Is Form Valid: {isFormValid ? 'Yes' : 'No'}</li>
        <li>Button Should Be: {isFormValid && !isLoading ? 'ENABLED' : 'DISABLED'}</li>
      </ul>
    </div>
  );
};

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

    console.log('Submitting form data:', formData);
    onSubmit(formData);
  };

  // Check if form is valid
  const isFormValid = formData.url.trim().length > 0 && !urlError;

  return (
    <Card className="w-full max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-gray-900">
          <Globe className="w-6 h-6 text-blue-600" />
          Clone Any Website
        </CardTitle>
        <CardDescription className="text-gray-700 font-medium">
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
          <div className="space-y-4">
            <label className="text-sm font-semibold text-gray-900 block">
              Clone Quality
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {qualityOptions.map((option) => {
                const Icon = option.icon;
                const isSelected = formData.quality === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setFormData(prev => ({ ...prev, quality: option.value }))}
                    disabled={isLoading}
                    className={`
                      p-4 rounded-lg border-2 text-left transition-all relative
                      ${isSelected
                        ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-200'
                        : 'border-gray-300 hover:border-gray-400 bg-white hover:bg-gray-50'
                      }
                      ${isLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
                    `}
                  >
                    <div className="flex items-center gap-3 mb-3">
                      <Icon className={`w-5 h-5 ${
                        isSelected ? 'text-blue-600' : 'text-gray-600'
                      }`} />
                      <span className={`font-semibold ${
                        isSelected ? 'text-blue-900' : 'text-gray-900'
                      }`}>
                        {option.label}
                      </span>
                      <span className={`text-xs px-2 py-1 rounded-full ml-auto ${
                        isSelected ? 'bg-blue-200 text-blue-800' : 'bg-gray-200 text-gray-700'
                      }`}>
                        {option.time}
                      </span>
                    </div>
                    <p className={`text-sm leading-relaxed ${
                      isSelected ? 'text-blue-800' : 'text-gray-700'
                    }`}>
                      {option.description}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Options */}
          <div className="space-y-4">
            <label className="text-sm font-semibold text-gray-900 block">
              Include Elements
            </label>
            <div className="space-y-3 bg-gray-50 p-4 rounded-lg">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.include_images}
                  onChange={(e) => setFormData(prev => ({ 
                    ...prev, 
                    include_images: e.target.checked 
                  }))}
                  disabled={isLoading}
                  className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500 focus:ring-2"
                />
                <span className="text-sm font-medium text-gray-900">Include Images</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.include_styling}
                  onChange={(e) => setFormData(prev => ({ 
                    ...prev, 
                    include_styling: e.target.checked 
                  }))}
                  disabled={isLoading}
                  className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500 focus:ring-2"
                />
                <span className="text-sm font-medium text-gray-900">Include CSS Styling</span>
              </label>
            </div>
          </div>

          {/* Custom Instructions - Enhanced */}
          <div>
            <label className="text-sm font-semibold text-gray-900 block mb-3">
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
              className="w-full h-24 rounded-md border-2 border-gray-300 px-4 py-3 text-base font-medium text-gray-900 placeholder:text-gray-400 placeholder:font-normal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:border-blue-500 disabled:cursor-not-allowed disabled:opacity-50 bg-white resize-none"
              rows={3}
              maxLength={500}
            />
            <p className="text-xs font-medium text-gray-600 mt-2">
              {formData.custom_instructions?.length || 0}/500 characters
            </p>
          </div>

          {/* Submit Button */}
          <Button
            type="submit"
            className={`w-full h-12 text-base font-semibold transition-all ${
              isFormValid && !isLoading
                ? 'bg-blue-600 hover:bg-blue-700 text-white cursor-pointer'
                : 'bg-gray-400 text-gray-200 cursor-not-allowed'
            }`}
            disabled={!isFormValid || isLoading}
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

          <DebugButton formData={formData} isLoading={isLoading} urlError={urlError} />

          {/* Form Status */}
          {!isFormValid && formData.url.trim().length > 0 && (
            <p className="text-sm text-red-600 text-center">
              Please enter a valid URL to continue
            </p>
          )}
        </form>
      </CardContent>
    </Card>
  );
}