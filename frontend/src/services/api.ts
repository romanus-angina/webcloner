import { 
  type CloneRequest, 
  type CloneResponse, 
  type CloneStatus, 
  type ProgressStep,
  type ApiError as ApiErrorType,
  type HealthResponse 
} from '@/types/api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const API_VERSION = '/api/v1';

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
    public details?: Record<string, any>
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

class ApiClient {
  private baseURL: string;
  private defaultHeaders: HeadersInit;

  constructor() {
    this.baseURL = `${API_BASE_URL}${API_VERSION}`;
    this.defaultHeaders = {
      'Content-Type': 'application/json',
    };
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    const config: RequestInit = {
      ...options,
      headers: {
        ...this.defaultHeaders,
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        let errorData: ApiErrorType;
        try {
          errorData = await response.json();
        } catch {
          errorData = {
            error: 'HTTP_ERROR',
            message: `HTTP ${response.status}: ${response.statusText}`,
            timestamp: new Date().toISOString()
          };
        }
        
        throw new ApiError(
          errorData.message || 'Request failed',
          response.status,
          errorData.error,
          errorData.details
        );
      }

      return await response.json();
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      
      throw new ApiError(
        error instanceof Error ? error.message : 'Network error occurred',
        0,
        'NETWORK_ERROR'
      );
    }
  }

  async healthCheck(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health');
  }

  async cloneWebsite(request: CloneRequest): Promise<CloneResponse> {
    return this.request<CloneResponse>('/clone', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getCloneStatus(sessionId: string): Promise<CloneResponse> {
    return this.request<CloneResponse>(`/clone/${sessionId}`);
  }

  async deleteSession(sessionId: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/clone/${sessionId}`, {
      method: 'DELETE',
    });
  }
}

export const apiClient = new ApiClient();

export { 
  type CloneRequest, 
  type CloneResponse, 
  type CloneStatus, 
  type ProgressStep,
  type HealthResponse
};