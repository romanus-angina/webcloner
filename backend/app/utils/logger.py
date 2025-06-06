import logging
import logging.handlers
import sys
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from ..config import settings


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to console output."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record):
        """Format log record with colors for console output."""
        if hasattr(record, 'levelname'):
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        
        return super().format(record)


class RequestContextFilter(logging.Filter):
    """Filter to add request context to log records."""
    
    def filter(self, record):
        """Add request ID and session ID to log records if available."""
        # These will be set by FastAPI middleware
        record.request_id = getattr(record, 'request_id', 'N/A')
        record.session_id = getattr(record, 'session_id', 'N/A')
        record.user_id = getattr(record, 'user_id', 'anonymous')
        return True


def setup_logging(
    app_name: str = "website_cloner",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_console: bool = True,
    enable_file: bool = True
) -> logging.Logger:
    """
    Set up centralized logging configuration.
    
    Args:
        app_name: Name of the application/logger
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (defaults to logs/{app_name}.log)
        enable_console: Whether to enable console logging
        enable_file: Whether to enable file logging
        
    Returns:
        Configured logger instance
    """
    # Determine log level
    if log_level is None:
        log_level = "DEBUG" if settings.debug else "INFO"
    
    # Create logger
    logger = logging.getLogger(app_name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | '
            'req:%(request_id)s | sess:%(session_id)s | '
            '%(filename)s:%(lineno)d | %(funcName)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = ColoredFormatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Add request context filter
    context_filter = RequestContextFilter()
    
    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if settings.debug else logging.INFO)
        console_handler.setFormatter(simple_formatter)
        console_handler.addFilter(context_filter)
        logger.addHandler(console_handler)
    
    # File handler with rotation
    if enable_file:
        # Create logs directory
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Set default log file path
        if log_file is None:
            log_file = log_dir / f"{app_name}.log"
        
        # Rotating file handler (10MB max, keep 5 backups)
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        file_handler.addFilter(context_filter)
        logger.addHandler(file_handler)
    
    # Error file handler (separate file for errors)
    if enable_file:
        error_file = log_dir / f"{app_name}_errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            filename=error_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        error_handler.addFilter(context_filter)
        logger.addHandler(error_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    # Log the setup
    logger.info(f"Logging configured for {app_name}")
    logger.info(f"Log level: {log_level}")
    logger.info(f"Console logging: {enable_console}")
    logger.info(f"File logging: {enable_file}")
    if enable_file and log_file:
        logger.info(f"Log file: {log_file}")
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with proper configuration.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    # If this is the first time getting a logger, set up the main logger
    root_logger = logging.getLogger("website_cloner")
    if not root_logger.handlers:
        setup_logging()
    
    # Return child logger
    return logging.getLogger(f"website_cloner.{name}")


def log_function_call(func):
    """
    Decorator to automatically log function calls.
    
    Usage:
        @log_function_call
        def my_function(arg1, arg2):
            return result
    """
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        
        # Log function entry
        args_str = ', '.join([str(arg) for arg in args])
        kwargs_str = ', '.join([f"{k}={v}" for k, v in kwargs.items()])
        params = ', '.join(filter(None, [args_str, kwargs_str]))
        
        logger.debug(f"Calling {func.__name__}({params})")
        
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} failed: {str(e)}")
            raise
    
    return wrapper


def log_performance(func):
    """
    Decorator to log function performance metrics.
    
    Usage:
        @log_performance
        def slow_function():
            # function code
    """
    import time
    
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func.__name__} executed in {execution_time:.3f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.3f}s: {str(e)}")
            raise
    
    return wrapper


class LoggerMixin:
    """Mixin class to add logging capabilities to any class."""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        return get_logger(self.__class__.__module__)


# Additional loggers for specific components
def get_scraper_logger() -> logging.Logger:
    """Get logger for scraping operations."""
    return get_logger("scraper")


def get_llm_logger() -> logging.Logger:
    """Get logger for LLM operations."""
    return get_logger("llm")


def get_api_logger() -> logging.Logger:
    """Get logger for API operations."""
    return get_logger("api")


def get_background_logger() -> logging.Logger:
    """Get logger for background tasks."""
    return get_logger("background")


# Security logging functions
def log_security_event(event_type: str, details: dict, severity: str = "WARNING"):
    """
    Log security-related events.
    
    Args:
        event_type: Type of security event
        details: Event details
        severity: Log level (INFO, WARNING, ERROR, CRITICAL)
    """
    security_logger = get_logger("security")
    
    message = f"Security Event: {event_type}"
    extra = {"security_event": True, "event_details": details}
    
    getattr(security_logger, severity.lower())(message, extra=extra)


def log_rate_limit_violation(client_id: str, endpoint: str, limit: int):
    """Log rate limit violations."""
    log_security_event(
        "RATE_LIMIT_VIOLATION",
        {
            "client_id": client_id,
            "endpoint": endpoint,
            "limit": limit,
            "timestamp": datetime.utcnow().isoformat()
        },
        "WARNING"
    )


def log_invalid_request(client_id: str, error: str, endpoint: str):
    """Log invalid requests."""
    log_security_event(
        "INVALID_REQUEST",
        {
            "client_id": client_id,
            "error": error,
            "endpoint": endpoint,
            "timestamp": datetime.utcnow().isoformat()
        },
        "INFO"
    )