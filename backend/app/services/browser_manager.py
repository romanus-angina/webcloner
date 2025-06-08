from typing import Optional, Dict, Any, Union
import asyncio
import logging
from contextlib import asynccontextmanager
from enum import Enum

from ..config import settings
from ..core.exceptions import (
    BrowserError, 
    BrowserConnectionError,
    ConfigurationError
)
from ..utils.logger import get_logger
from .browser_service import BrowserService
from .cloud_browser import CloudBrowserService

logger = get_logger(__name__)


class BrowserType(str, Enum):
    """Enumeration of browser types."""
    LOCAL = "local"
    CLOUD = "cloud"
    AUTO = "auto"


class BrowserManager:
    """
    Manages browser services with automatic fallback between cloud and local browsers.
    
    Provides a unified interface for browser operations while handling:
    - Automatic fallback from cloud to local browsers
    - Service health monitoring
    - Resource management and cleanup
    - Configuration-based service selection
    """
    
    def __init__(self, preferred_type: BrowserType = BrowserType.AUTO):
        self.preferred_type = preferred_type
        self._current_service: Optional[Union[BrowserService, CloudBrowserService]] = None
        self._service_type: Optional[BrowserType] = None
        self._is_initialized = False
        
    def _determine_browser_type(self) -> BrowserType:
        """
        Determine which browser type to use based on configuration and preferences.
        
        Returns:
            BrowserType to use
        """
        # If explicitly set to local or cloud, respect that choice
        if self.preferred_type in [BrowserType.LOCAL, BrowserType.CLOUD]:
            return self.preferred_type
        
        # Auto selection based on configuration
        if getattr(settings, 'USE_CLOUD_BROWSER', False):
            # Check if cloud browser is properly configured
            if (hasattr(settings, 'BROWSERBASE_API_KEY') and settings.BROWSERBASE_API_KEY and
                hasattr(settings, 'BROWSERBASE_PROJECT_ID') and settings.BROWSERBASE_PROJECT_ID):
                logger.info("Auto-selecting cloud browser (Browserbase configured)")
                return BrowserType.CLOUD
            else:
                logger.warning("Cloud browser requested but not properly configured, falling back to local")
                return BrowserType.LOCAL
        else:
            logger.info("Auto-selecting local browser")
            return BrowserType.LOCAL
    
    async def initialize(self, force_type: Optional[BrowserType] = None) -> None:
        """
        Initialize the browser manager with the appropriate service.
        
        Inputs:
            force_type: Override automatic browser type selection
            
        Raises:
            BrowserConnectionError: If initialization fails
        """
        if self._is_initialized and not force_type:
            logger.warning("Browser manager already initialized")
            return
        
        # Determine browser type
        browser_type = force_type or self._determine_browser_type()
        
        try:
            logger.info(f"Initializing browser manager with {browser_type.value} browser")
            
            # Create appropriate service
            if browser_type == BrowserType.CLOUD:
                self._current_service = CloudBrowserService()
            else:
                self._current_service = BrowserService()
            
            # Initialize the service
            await self._current_service.initialize()
            
            self._service_type = browser_type
            self._is_initialized = True
            
            logger.info(f"Browser manager initialized successfully with {browser_type.value} browser")
            
        except Exception as e:
            logger.error(f"Failed to initialize {browser_type.value} browser: {str(e)}")
            
            # Try fallback if this was cloud browser
            if browser_type == BrowserType.CLOUD and force_type is None:
                logger.info("Attempting fallback to local browser")
                try:
                    await self._fallback_to_local()
                except Exception as fallback_error:
                    logger.error(f"Fallback to local browser also failed: {str(fallback_error)}")
                    raise BrowserConnectionError(
                        f"Both cloud and local browser initialization failed. "
                        f"Cloud error: {str(e)}, Local error: {str(fallback_error)}"
                    )
            else:
                raise BrowserConnectionError(f"Browser initialization failed: {str(e)}")
    
    async def _fallback_to_local(self) -> None:
        """Fallback to local browser service."""
        logger.info("Falling back to local browser")
        
        # Cleanup failed cloud service if exists
        if self._current_service:
            try:
                await self._current_service.cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up failed cloud service: {str(e)}")
        
        # Initialize local service
        self._current_service = BrowserService()
        await self._current_service.initialize()
        self._service_type = BrowserType.LOCAL
        self._is_initialized = True
        
        logger.info("Successfully fell back to local browser")
    
    async def create_context(self, **context_options):
        """
        Create a browser context using the current service.
        
        Inputs:
            **context_options: Context configuration options
            
        Returns:
            BrowserContext from the active service
        """
        if not self._is_initialized or not self._current_service:
            raise BrowserError("Browser manager not initialized")
        
        try:
            return await self._current_service.create_context(**context_options)
        except Exception as e:
            logger.error(f"Failed to create context with {self._service_type.value} browser: {str(e)}")
            
            # Try fallback if this was cloud browser
            if self._service_type == BrowserType.CLOUD:
                logger.info("Context creation failed, attempting fallback to local browser")
                try:
                    await self._fallback_to_local()
                    return await self._current_service.create_context(**context_options)
                except Exception as fallback_error:
                    logger.error(f"Fallback context creation also failed: {str(fallback_error)}")
                    raise BrowserError(f"Context creation failed on both services: {str(e)}")
            else:
                raise
    
    async def create_page(self, context=None):
        """
        Create a browser page using the current service.
        
        Inputs:
            context: Optional browser context
            
        Returns:
            Page from the active service
        """
        if not self._is_initialized or not self._current_service:
            raise BrowserError("Browser manager not initialized")
        
        return await self._current_service.create_page(context)
    
    @asynccontextmanager
    async def page_context(self, **context_options):
        """
        Context manager for browser pages with automatic cleanup.
        
        Inputs:
            **context_options: Context configuration options
            
        Yields:
            Page instance from the active service
        """
        if not self._is_initialized or not self._current_service:
            raise BrowserError("Browser manager not initialized")
        
        async with self._current_service.page_context(**context_options) as page:
            yield page
    
    async def navigate_to_url(self, page, url: str, wait_for: str = "networkidle") -> None:
        """
        Navigate to URL using the current service.
        
        Inputs:
            page: Browser page instance
            url: URL to navigate to
            wait_for: Wait condition
        """
        if hasattr(self._current_service, 'navigate_to_url'):
            await self._current_service.navigate_to_url(page, url, wait_for)
        else:
            # Fallback to direct page navigation
            await page.goto(url, wait_until=wait_for)
    
    async def wait_for_page_load(self, page, timeout: Optional[int] = None) -> None:
        """
        Wait for page load using the current service.
        
        Inputs:
            page: Browser page instance
            timeout: Optional timeout in seconds
        """
        if hasattr(self._current_service, 'wait_for_page_load'):
            await self._current_service.wait_for_page_load(page, timeout)
        else:
            # Fallback to basic page load waiting
            timeout_ms = (timeout or 30) * 1000
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)
    
    async def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the current browser service.
        
        Returns:
            Dict containing service information
        """
        if not self._is_initialized or not self._current_service:
            return {
                "status": "not_initialized",
                "service_type": None
            }
        
        # Get service-specific info
        if hasattr(self._current_service, 'get_browser_info'):
            service_info = await self._current_service.get_browser_info()
        elif hasattr(self._current_service, 'get_session_info'):
            service_info = await self._current_service.get_session_info()
        else:
            service_info = {"status": "unknown"}
        
        return {
            "service_type": self._service_type.value if self._service_type else None,
            "manager_status": "initialized" if self._is_initialized else "not_initialized",
            "service_info": service_info
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the current browser service.
        
        Returns:
            Dict containing health status
        """
        try:
            if not self._is_initialized or not self._current_service:
                return {
                    "healthy": False,
                    "error": "Browser manager not initialized"
                }
            
            # Test basic functionality
            async with self.page_context() as page:
                # Try to navigate to a simple test page
                await page.goto("data:text/html,<html><body>Health Check</body></html>")
                title = await page.title()
                
            return {
                "healthy": True,
                "service_type": self._service_type.value,
                "test_result": "success",
                "title_retrieved": bool(title)
            }
            
        except Exception as e:
            logger.error(f"Browser health check failed: {str(e)}")
            return {
                "healthy": False,
                "service_type": self._service_type.value if self._service_type else None,
                "error": str(e)
            }
    
    async def cleanup(self) -> None:
        """Clean up browser manager resources."""
        logger.info("Cleaning up browser manager")
        
        if self._current_service:
            try:
                await self._current_service.cleanup()
                logger.info("Browser service cleaned up successfully")
            except Exception as e:
                logger.warning(f"Error cleaning up browser service: {str(e)}")
            finally:
                self._current_service = None
        
        self._is_initialized = False
        self._service_type = None
        logger.info("Browser manager cleanup completed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()


# Global browser manager instance
browser_manager = BrowserManager()