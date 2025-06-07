export const API_ENDPOINTS = {
    HEALTH: '/health',
    CLONE: '/clone',
    SESSIONS: '/sessions',
  } as const;
  
  export const CLONE_QUALITY = {
    FAST: 'fast',
    BALANCED: 'balanced',
    HIGH: 'high',
  } as const;
  
  export const CLONE_STATUS = {
    PENDING: 'pending',
    ANALYZING: 'analyzing',
    SCRAPING: 'scraping',
    GENERATING: 'generating',
    REFINING: 'refining',
    COMPLETED: 'completed',
    FAILED: 'failed',
  } as const;
  
  export const POLLING_INTERVAL = 2000; // 2 seconds
  export const MAX_RETRIES = 3;
  export const REQUEST_TIMEOUT = 30000; // 30 seconds