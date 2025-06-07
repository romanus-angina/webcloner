export interface CloneRequest {
    url: string;
    quality: 'fast' | 'balanced' | 'high';
    include_images: boolean;
    include_styling: boolean;
    max_depth: number;
    custom_instructions?: string;
  }
  
  export interface ProgressStep {
    step_name: string;
    status: CloneStatus;
    started_at?: string;
    completed_at?: string;
    progress_percentage: number;
    message?: string;
    error?: string;
  }
  
  export interface CloneResult {
    html_content: string;
    css_content?: string;
    assets: string[];
    similarity_score?: number;
    generation_time: number;
    tokens_used?: number;
  }
  
  export interface CloneResponse {
    session_id: string;
    status: CloneStatus;
    progress: ProgressStep[];
    result?: CloneResult;
    created_at: string;
    updated_at: string;
    estimated_completion?: string;
    error_message?: string;
  }
  
  export type CloneStatus = 
    | 'pending' 
    | 'analyzing' 
    | 'scraping' 
    | 'generating' 
    | 'refining' 
    | 'completed' 
    | 'failed';
  
  export interface ApiError {
    error: string;
    message: string;
    details?: Record<string, any>;
    timestamp: string;
    request_id?: string;
  }
  
  export interface HealthResponse {
    status: string;
    timestamp: string;
    version: string;
    uptime: number;
    details?: Record<string, any>;
  }
  