import { useState, useCallback } from 'react';
import { apiClient, type CloneRequest, type CloneResponse, ApiError } from '@/services/api';

interface UseCloningState {
  isLoading: boolean;
  data: CloneResponse | null;
  error: string | null;
}

export function useCloning() {
  const [state, setState] = useState<UseCloningState>({
    isLoading: false,
    data: null,
    error: null,
  });

  const cloneWebsite = useCallback(async (request: CloneRequest) => {
    setState({ isLoading: true, data: null, error: null });
    
    try {
      const response = await apiClient.cloneWebsite(request);
      setState({ isLoading: false, data: response, error: null });
      return response;
    } catch (error) {
      const errorMessage = error instanceof ApiError 
        ? error.message 
        : 'An unexpected error occurred';
      setState({ isLoading: false, data: null, error: errorMessage });
      throw error;
    }
  }, []);

  const getStatus = useCallback(async (sessionId: string) => {
    try {
      const response = await apiClient.getCloneStatus(sessionId);
      setState(prev => ({ ...prev, data: response, error: null }));
      return response;
    } catch (error) {
      const errorMessage = error instanceof ApiError 
        ? error.message 
        : 'Failed to get status';
      setState(prev => ({ ...prev, error: errorMessage }));
      throw error;
    }
  }, []);

  const reset = useCallback(() => {
    setState({ isLoading: false, data: null, error: null });
  }, []);

  return {
    ...state,
    cloneWebsite,
    getStatus,
    reset,
  };
}