from typing import Optional, Dict, Any


class WebsiteClonerException(Exception):
    """Base exception for all website cloner errors."""
    
    def __init__(
        self, 
        message: str, 
        error_code: str = "GENERAL_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(WebsiteClonerException):
    """Exception raised for input validation errors."""
    
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.field = field
        super().__init__(message, "VALIDATION_ERROR", details)


class ScrapingError(WebsiteClonerException):
    """Exception raised when website scraping fails."""
    
    def __init__(self, message: str, url: Optional[str] = None, status_code: Optional[int] = None):
        details = {}
        if url:
            details["url"] = url
        if status_code:
            details["status_code"] = status_code
        super().__init__(message, "SCRAPING_ERROR", details)


class NetworkError(WebsiteClonerException):
    """Exception raised for network-related errors."""
    
    def __init__(self, message: str, url: Optional[str] = None, timeout: Optional[bool] = False):
        details = {"timeout": timeout}
        if url:
            details["url"] = url
        super().__init__(message, "NETWORK_ERROR", details)


class LLMError(WebsiteClonerException):
    """Exception raised when LLM service fails."""
    
    def __init__(self, message: str, provider: Optional[str] = None, model: Optional[str] = None):
        details = {}
        if provider:
            details["provider"] = provider
        if model:
            details["model"] = model
        super().__init__(message, "LLM_ERROR", details)


class ProcessingError(WebsiteClonerException):
    """Exception raised during content processing."""
    
    def __init__(self, message: str, stage: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        processing_details = details or {}
        if stage:
            processing_details["stage"] = stage
        super().__init__(message, "PROCESSING_ERROR", processing_details)


class StorageError(WebsiteClonerException):
    """Exception raised for file storage operations."""
    
    def __init__(self, message: str, file_path: Optional[str] = None, operation: Optional[str] = None):
        details = {}
        if file_path:
            details["file_path"] = file_path
        if operation:
            details["operation"] = operation
        super().__init__(message, "STORAGE_ERROR", details)


class AuthenticationError(WebsiteClonerException):
    """Exception raised for authentication failures."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, "AUTHENTICATION_ERROR")


class AuthorizationError(WebsiteClonerException):
    """Exception raised for authorization failures."""
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, "AUTHORIZATION_ERROR")


class RateLimitError(WebsiteClonerException):
    """Exception raised when rate limits are exceeded."""
    
    def __init__(self, message: str, retry_after: Optional[int] = None):
        details = {}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message, "RATE_LIMIT_ERROR", details)


class SessionError(WebsiteClonerException):
    """Exception raised for session-related errors."""
    
    def __init__(self, message: str, session_id: Optional[str] = None):
        details = {}
        if session_id:
            details["session_id"] = session_id
        super().__init__(message, "SESSION_ERROR", details)


class ConfigurationError(WebsiteClonerException):
    """Exception raised for configuration-related errors."""
    
    def __init__(self, message: str, config_key: Optional[str] = None):
        details = {}
        if config_key:
            details["config_key"] = config_key
        super().__init__(message, "CONFIGURATION_ERROR", details)


class ResourceNotFoundError(WebsiteClonerException):
    """Exception raised when a requested resource is not found."""
    
    def __init__(self, message: str, resource_type: Optional[str] = None, resource_id: Optional[str] = None):
        details = {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id
        super().__init__(message, "RESOURCE_NOT_FOUND", details)


class ServiceUnavailableError(WebsiteClonerException):
    """Exception raised when a required service is unavailable."""
    
    def __init__(self, message: str, service: Optional[str] = None):
        details = {}
        if service:
            details["service"] = service
        super().__init__(message, "SERVICE_UNAVAILABLE", details)


# Mapping of exception types to HTTP status codes
EXCEPTION_STATUS_CODES = {
    ValidationError: 400,
    AuthenticationError: 401,
    AuthorizationError: 403,
    ResourceNotFoundError: 404,
    RateLimitError: 429,
    ConfigurationError: 500,
    ScrapingError: 502,
    NetworkError: 502,
    LLMError: 502,
    ServiceUnavailableError: 503,
    ProcessingError: 500,
    StorageError: 500,
    SessionError: 400,
    WebsiteClonerException: 500,  # Default for base exception
}


def get_http_status_code(exception: WebsiteClonerException) -> int:
    """
    Get the appropriate HTTP status code for an exception.
    
    Args:
        exception: The exception instance
        
    Returns:
        HTTP status code
    """
    return EXCEPTION_STATUS_CODES.get(type(exception), 500)