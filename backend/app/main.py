from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
import json
from fastapi.responses import JSONResponse as BaseJSONResponse
from fastapi.exception_handlers import http_exception_handler
from contextlib import asynccontextmanager
import time
import logging
from datetime import datetime, UTC
from typing import Dict, Any

from .config import settings
from .dependencies import (
    get_app_state, 
    get_logger, 
    increment_request_counter,
    ApplicationState
)
from .core.exceptions import (
    WebsiteClonerException, 
    get_http_status_code
)
from .models.responses import ErrorResponse, HealthResponse
from .utils.logger import setup_logging, get_logger
from .dependencies import get_browser_manager

# Initialize logging
setup_logging()
logger = get_logger(__name__)

# Custom JSON Response that handles datetime serialization
class JSONResponse(BaseJSONResponse):
    """Custom JSON response that properly handles datetime serialization."""
    
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            default=self._json_serializer
        ).encode("utf-8")
    
    def _json_serializer(self, obj):
        """Custom JSON serializer for special types."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    
    # Initialize browser manager
    try:
        browser_manager = get_browser_manager()
        await browser_manager.initialize()
        logger.info("Browser manager initialized successfully")
    except Exception as e:
        logger.warning(f"Browser manager initialization failed: {str(e)}")
        logger.info("Browser will be initialized on first use")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    try:
        browser_manager = get_browser_manager()
        await browser_manager.cleanup()
        logger.info("Browser manager cleaned up")
    except Exception as e:
        logger.warning(f"Browser cleanup error: {str(e)}")



# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="AI-powered website cloning service that creates visually similar HTML replicas",
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,  # Hide docs in production
    redoc_url="/redoc" if settings.debug else None,
)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging and context middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with proper context."""
    start_time = time.time()
    
    # Generate request ID and add to request state
    from .dependencies import add_request_context
    request_id = await add_request_context(request)
    
    # Create logger with request context
    request_logger = get_logger("requests")
    
    try:
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log successful response
        request_logger.info(
            f"Request completed: {response.status_code} in {process_time:.3f}s",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": str(request.url.path),
                "status_code": response.status_code,
                "process_time": process_time,
                "client_ip": request.client.host if request.client else "unknown"
            }
        )
        
        # Add headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
        
    except Exception as e:
        # Calculate processing time for errors
        process_time = time.time() - start_time
        
        # Log error
        request_logger.error(
            f"Request failed: {str(e)} after {process_time:.3f}s",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": str(request.url.path),
                "process_time": process_time,
                "error": str(e),
                "client_ip": request.client.host if request.client else "unknown"
            },
            exc_info=True
        )
        
        # Re-raise the exception
        raise


# Global exception handler for our custom exceptions
@app.exception_handler(WebsiteClonerException)
async def website_cloner_exception_handler(request: Request, exc: WebsiteClonerException):
    """Handle custom application exceptions."""
    logger.error(f"Application error: {exc.message}", extra={"details": exc.details})
    
    status_code = get_http_status_code(exc)
    
    error_response = ErrorResponse(
        error=exc.error_code,
        message=exc.message,
        details=exc.details,
        timestamp=datetime.now(UTC)
    )
    
    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump()
    )


# Global exception handler for HTTP exceptions
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent format."""
    logger.warning(f"HTTP error: {exc.status_code} - {exc.detail}")
    
    error_response = ErrorResponse(
        error="HTTP_ERROR",
        message=exc.detail,
        timestamp=datetime.now(UTC)
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump()
    )


# Global exception handler for unexpected errors
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    
    # Don't expose internal errors in production
    message = str(exc) if settings.debug else "Internal server error"
    
    error_response = ErrorResponse(
        error="INTERNAL_ERROR",
        message=message,
        timestamp=datetime.now(UTC)
    )
    
    return JSONResponse(
        status_code=500,
        content=error_response.model_dump()
    )


# Root endpoint
@app.get("/", tags=["General"])
async def root():
    """Root endpoint with basic application information."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "running",
        "docs_url": "/docs" if settings.debug else "Documentation not available in production"
    }


# Health check endpoint
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(
    include_details: bool = False,
    app_state: ApplicationState = Depends(get_app_state),
    request_count: int = Depends(increment_request_counter)
):
    """
    Health check endpoint.
    
    Args:
        include_details: Whether to include detailed system information
        app_state: Application state dependency
        request_count: Current request count
        
    Returns:
        Health status information
    """
    uptime = app_state.get_uptime()
    
    health_response = HealthResponse(
        status="healthy",
        timestamp=datetime.now(UTC),
        version=settings.app_version,
        uptime=uptime
    )
    
    if include_details:
        health_response.details = {
            "environment": settings.environment,
            "debug_mode": settings.debug,
            "total_requests": request_count,
            "active_sessions": len(app_state.active_sessions),
            "uptime_formatted": f"{uptime:.2f} seconds",
            "settings": {
                "rate_limit_requests": settings.rate_limit_requests,
                "rate_limit_window": settings.rate_limit_window,
                "max_file_size": settings.max_file_size,
                "request_timeout": settings.request_timeout
            }
        }
    
    return health_response


# API version info
@app.get("/api/version", tags=["General"])
async def get_version():
    """Get API version information."""
    return {
        "api_version": "1.0.0",
        "app_version": settings.app_version,
        "environment": settings.environment,
        "features": {
            "website_cloning": True,
            "real_time_updates": True,
            "refinement": True,
            "batch_processing": False  # Future feature
        }
    }


# Include routers
from .api.routes import clone, health, screenshot, dom_extraction

app.include_router(clone.router, prefix=settings.api_v1_prefix, tags=["Cloning"])
app.include_router(health.router, prefix=settings.api_v1_prefix, tags=["Health Extended"])
app.include_router(screenshot.router, prefix=settings.api_v1_prefix + "/screenshots", tags=["Screenshots"])
app.include_router(dom_extraction.router, prefix=settings.api_v1_prefix + "/dom", tags=["DOM Extraction"])

# WebSocket router will be added in the next phase
# from .api.routes import websocket
# app.include_router(websocket.router, prefix=settings.api_v1_prefix, tags=["WebSocket"])


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting server on {settings.host}:{settings.port}")
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info"
    )