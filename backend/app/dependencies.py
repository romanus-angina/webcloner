from typing import Generator, Optional
from fastapi import Depends, HTTPException, status, Request
from functools import lru_cache
import time
import uuid
import logging
from datetime import datetime, UTC

from .config import Settings, settings
from .services.browser_manager import BrowserManager, browser_manager
from .services.screenshot_service import ScreenshotService, screenshot_service

# Global application state
class ApplicationState:
    """Global application state management."""
    
    def __init__(self):
        self.start_time = time.time()
        self.active_sessions: dict[str, dict] = {}
        self.request_count = 0
        
    def get_uptime(self) -> float:
        """Get application uptime in seconds."""
        return time.time() - self.start_time
    
    def create_session(self) -> str:
        """Create a new session and return its ID."""
        session_id = str(uuid.uuid4())
        self.active_sessions[session_id] = {
            "created_at": datetime.now(UTC),
            "status": "pending",
            "progress": []
        }
        return session_id
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """Get session data by ID."""
        return self.active_sessions.get(session_id)
    
    def update_session(self, session_id: str, data: dict):
        """Update session data."""
        if session_id in self.active_sessions:
            self.active_sessions[session_id].update(data)
    
    def increment_request_count(self):
        """Increment the global request counter."""
        self.request_count += 1


# Global app state instance
app_state = ApplicationState()


@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings.
    Uses lru_cache to ensure settings are loaded only once.
    """
    return settings


def get_app_state() -> ApplicationState:
    """Get the global application state."""
    return app_state


def get_browser_manager() -> BrowserManager:
    """
    Get the global browser manager instance.
    
    Returns:
        BrowserManager: Global browser manager
    """
    return browser_manager


def get_logger(name: str = "website_cloner") -> logging.Logger:
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        # Configure logger if not already configured
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Set log level based on settings
        settings = get_settings()
        log_level = logging.DEBUG if settings.debug else logging.INFO
        logger.setLevel(log_level)
    
    return logger


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return str(uuid.uuid4())


def get_request_id() -> str:
    """Dependency to get a unique request ID for each request."""
    return generate_request_id()


async def add_request_context(request: Request) -> str:
    """
    Add request context to the request state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Request ID
    """
    request_id = generate_request_id()
    request.state.request_id = request_id
    return request_id


async def validate_session_id(session_id: str) -> str:
    """
    Validate that a session ID exists.
    
    Args:
        session_id: Session ID to validate
        
    Returns:
        The validated session ID
        
    Raises:
        HTTPException: If session ID is invalid
    """
    state = get_app_state()
    if session_id not in state.active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    return session_id


async def get_current_user_id() -> Optional[str]:
    """
    Get current user ID (placeholder for future authentication).
    
    Returns:
        User ID if authenticated, None otherwise
    """
    # TODO: Implement proper authentication
    # For now, return None (anonymous users)
    return None


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self):
        self.requests: dict[str, list[float]] = {}
    
    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """
        Check if request is allowed based on rate limiting.
        
        Args:
            key: Unique key for the client (IP, user ID, etc.)
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds
            
        Returns:
            True if request is allowed, False otherwise
        """
        now = time.time()
        
        # Initialize key if none exists
        if key not in self.requests:
            self.requests[key] = []
        
        # Remove old requests outside the window
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if now - req_time < window_seconds
        ]
        
        # Check if under limit
        if len(self.requests[key]) < max_requests:
            self.requests[key].append(now)
            return True
        
        return False


# Global rate limiter instance
rate_limiter = RateLimiter()


async def check_rate_limit(request: Request = None, request_key: str = None) -> None:
    """
    Check rate limiting for the current request.
    
    Args:
        request: FastAPI request object (for extracting client IP)
        request_key: Unique key for rate limiting (overrides IP-based key)
        
    Raises:
        HTTPException: If rate limit is exceeded
    """
    # Determine rate limiting key
    if request_key is None:
        if request and request.client:
            request_key = request.client.host
        else:
            request_key = "global"
    
    settings = get_settings()
    
    if not rate_limiter.is_allowed(
        request_key, 
        settings.rate_limit_requests, 
        settings.rate_limit_window
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )


def increment_request_counter():
    """Dependency to increment the global request counter."""
    app_state.increment_request_count()
    return app_state.request_count


# Browser-related dependencies
async def get_browser_service():
    """
    Get an initialized browser service.
    
    Returns:
        Initialized browser service from the manager
        
    Raises:
        HTTPException: If browser service is not available
    """
    manager = get_browser_manager()
    
    if not manager._is_initialized:
        try:
            await manager.initialize()
        except Exception as e:
            logger = get_logger()
            logger.error(f"Failed to initialize browser service: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Browser service unavailable"
            )
    
    return manager._current_service


async def get_browser_health():
    """
    Get browser service health status.
    
    Returns:
        Dict containing health information
    """
    manager = get_browser_manager()
    return await manager.health_check()

def get_screenshot_service() -> ScreenshotService:
    """
    Get the global screenshot service instance.
    
    Returns:
        ScreenshotService: Global screenshot service
    """
    return screenshot_service

# Common dependency combinations
CommonDeps = Depends(get_settings)
StateDeps = Depends(get_app_state)
LoggerDeps = Depends(get_logger)
RequestIdDeps = Depends(get_request_id)
RateLimitDeps = Depends(check_rate_limit)
BrowserManagerDeps = Depends(get_browser_manager)
BrowserServiceDeps = Depends(get_browser_service)
ScreenshotServiceDeps = Depends(get_screenshot_service)