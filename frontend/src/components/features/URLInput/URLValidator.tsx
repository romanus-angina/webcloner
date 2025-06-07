'use client';

import React from 'react';
import { CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { validateUrl } from '@/utils/validation';

interface URLValidatorProps {
  url: string;
  showValidation: boolean;
}

export function URLValidator({ url, showValidation }: URLValidatorProps) {
  if (!showValidation || !url.trim()) return null;

  const validation = validateUrl(url);
  
  return (
    <div className={`
      flex items-center gap-2 text-sm mt-2 p-2 rounded-md
      ${validation.isValid 
        ? 'text-green-700 bg-green-50' 
        : 'text-red-700 bg-red-50'
      }
    `}>
      {validation.isValid ? (
        <>
          <CheckCircle className="w-4 h-4" />
          <span>URL looks good!</span>
        </>
      ) : (
        <>
          <XCircle className="w-4 h-4" />
          <span>{validation.error}</span>
        </>
      )}
    </div>
  );
}