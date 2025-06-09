from typing import Optional, Dict, Any, List
import asyncio
import logging
import json
from contextlib import asynccontextmanager
import httpx
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from ..config import settings
from ..core.exceptions import (
    BrowserError, 
    BrowserTimeoutError, 
    BrowserConnectionError,
    ConfigurationError
)
from ..utils.logger import get_logger
from ..utils.browser import get_random_user_agent

logger = get_logger(__name__)


class CloudBrowserService:
    """
    Cloud browser service using Browserbase for remote browser automation.
    
    Provides remote browser instances with the same interface as local browsers,
    for scalable web scraping.
    """
    
    def __init__(self):
        self._session_id: Optional[str] = None
        self._browser: Optional[Browser] = None
        self._playwright = None
        self._contexts: List[BrowserContext] = []
        self._is_connected = False
        
    def _validate_configuration(self) -> None:
        """Validate Browserbase configuration."""
        if not settings.BROWSERBASE_API_KEY:
            raise ConfigurationError(
                "Browserbase API key not configured", 
                config_key="BROWSERBASE_API_KEY"
            )
        
        if not settings.BROWSERBASE_PROJECT_ID:
            raise ConfigurationError(
                "Browserbase project ID not configured",
                config_key="BROWSERBASE_PROJECT_ID"
            )
    
    async def _create_session(self) -> tuple[str, str]:
        """
        Create a new Browserbase session.
        
        Returns:
            Tuple of (session_id, connect_url)
            
        Raises:
            BrowserConnectionError: If session creation fails
        """
        try:
            self._validate_configuration()
            
            logger.info("Creating new Browserbase session")

            # Get a random user agent for the session
            user_agent = get_random_user_agent(settings.USER_AGENTS)
            logger.info(f"Using User-Agent for cloud session: {user_agent}")
            
            session_data = {
                "projectId": settings.BROWSERBASE_PROJECT_ID,
                "browserSettings": {
                    "viewport": {
                        "width": getattr(settings, 'BROWSER_VIEWPORT_WIDTH', 1920),
                        "height": getattr(settings, 'BROWSER_VIEWPORT_HEIGHT', 1080)
                    },
                    "fingerprint": {
                        "screen": {
                            "width": getattr(settings, 'BROWSER_VIEWPORT_WIDTH', 1920),
                            "height": getattr(settings, 'BROWSER_VIEWPORT_HEIGHT', 1080)
                        },
                        # Add the user agent to the fingerprint
                        "userAgent": user_agent
                    }
                }
            }
            
            headers = {
                "x-bb-api-key": settings.BROWSERBASE_API_KEY,
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://www.browserbase.com/v1/sessions",
                    json=session_data,
                    headers=headers
                )
                
                # Accept both 200 OK and 201 Created as success
                if response.status_code not in [200, 201]:
                    error_msg = f"Failed to create Browserbase session: {response.status_code}"
                    
                    if response.status_code == 401:
                        error_msg = "Browserbase authentication failed - check API key"
                    elif response.status_code == 403:
                        error_msg = "Browserbase access forbidden - check project ID and permissions"
                    elif response.status_code == 429:
                        error_msg = f"Browserbase rate limit exceeded: {response.text}"
                    
                    logger.error(f"{error_msg} - Response: {response.text}")
                    raise BrowserConnectionError(error_msg)
                
                session_info = response.json()
                
                # DEBUG: Log the creation response
                logger.info(f"Session creation response: {session_info}")
                
                session_id = session_info.get("id")
                
                if not session_id:
                    raise BrowserConnectionError("No session ID returned from Browserbase")
                
                # CRITICAL FIX: Get connectUrl from creation response
                connect_url = (
                    session_info.get("connectUrl") or 
                    session_info.get("connect_url") or
                    session_info.get("websocketUrl") or
                    session_info.get("websocket_url")
                )
                
                if not connect_url:
                    available_fields = list(session_info.keys())
                    logger.error(f"No connection URL in creation response. Available fields: {available_fields}")
                    raise BrowserConnectionError(
                        f"No connection URL returned in session creation. Available fields: {available_fields}"
                    )
                
                logger.info(f"Created Browserbase session: {session_id}")
                logger.info(f"Got connection URL from creation response")
                
                return session_id, connect_url
                
        except httpx.TimeoutException:
            logger.error("Timeout creating Browserbase session")
            raise BrowserConnectionError("Timeout connecting to Browserbase")
        except httpx.RequestError as e:
            logger.error(f"Network error creating Browserbase session: {str(e)}")
            raise BrowserConnectionError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error creating Browserbase session: {str(e)}")
            raise BrowserConnectionError(f"Session creation failed: {str(e)}")
        
    
    async def initialize(self) -> None:
        """Initialize cloud browser connection with fixed URL handling."""
        if self._is_connected:
            logger.warning("Cloud browser service already connected")
            return
        
        try:
            logger.info("Initializing cloud browser service")
            
            # Create Browserbase session and get connection URL in one call
            self._session_id, self._connect_url = await self._create_session()
            
            # Initialize Playwright
            self._playwright = await async_playwright().start()
            
            # Connect to remote browser using the URL from creation
            logger.info(f"Connecting to browser with URL: {self._connect_url[:50]}...")
            self._browser = await self._playwright.chromium.connect_over_cdp(self._connect_url)
            
            self._is_connected = True
            logger.info(f"Successfully connected to cloud browser (session: {self._session_id})")
            
        except Exception as e:
            logger.error(f"Failed to initialize cloud browser: {str(e)}")
            await self.cleanup()
            raise BrowserConnectionError(f"Cloud browser initialization failed: {str(e)}")
    
    
    async def create_context(self, **context_options) -> BrowserContext:
        """
        Create a new browser context in the cloud browser.
        
        Args:
            **context_options: Additional context configuration options
            
        Returns:
            BrowserContext: New browser context
            
        Raises:
            BrowserError: If context creation fails
        """
        if not self._is_connected or not self._browser:
            raise BrowserError("Cloud browser service not connected")
        
        try:
            # Default context options for cloud browser
            default_options = {
                "java_script_enabled": True,
                "accept_downloads": False,
                "ignore_https_errors": True,
                "user_agent": getattr(settings, 'BROWSER_USER_AGENT', None)
            }
            
            # Note: viewport is typically set at session level for Browserbase
            # but we can override if needed
            if 'viewport' not in context_options:
                default_options['viewport'] = {
                    "width": getattr(settings, 'BROWSER_VIEWPORT_WIDTH', 1920),
                    "height": getattr(settings, 'BROWSER_VIEWPORT_HEIGHT', 1080)
                }
            
            # Merge with provided options
            options = {**default_options, **context_options}
            
            context = await self._browser.new_context(**options)
            self._contexts.append(context)
            
            logger.debug(f"Created cloud browser context (total: {len(self._contexts)})")
            return context
            
        except Exception as e:
            logger.error(f"Failed to create cloud browser context: {str(e)}")
            raise BrowserError(f"Cloud context creation failed: {str(e)}")
    
    async def create_page(self, context: Optional[BrowserContext] = None) -> Page:
        """
        Create a new page in the cloud browser.
        
        Args:
            context: Optional browser context to use
            
        Returns:
            Page: New browser page
            
        Raises:
            BrowserError: If page creation fails
        """
        try:
            if context is None:
                context = await self.create_context()
            
            page = await context.new_page()
            
            # Set timeouts
            page.set_default_timeout(getattr(settings, 'BROWSER_TIMEOUT', 30) * 1000)
            page.set_default_navigation_timeout(getattr(settings, 'BROWSER_NAVIGATION_TIMEOUT', 30) * 1000)
            
            logger.debug("Created cloud browser page")
            return page
            
        except Exception as e:
            logger.error(f"Failed to create cloud browser page: {str(e)}")
            raise BrowserError(f"Cloud page creation failed: {str(e)}")
    
    @asynccontextmanager
    async def page_context(self, **context_options):
        """
        Context manager for creating and cleaning up cloud browser pages.
        
        Args:
            **context_options: Browser context configuration options
            
        Yields:
            Page: Browser page instance
        """
        context = None
        page = None
        
        try:
            context = await self.create_context(**context_options)
            page = await self.create_page(context)
            yield page
            
        except Exception as e:
            logger.error(f"Error in cloud page context: {str(e)}")
            raise BrowserError(f"Cloud page context error: {str(e)}")
            
        finally:
            # Cleanup page and context
            if page:
                try:
                    await page.close()
                    logger.debug("Cloud page closed successfully")
                except Exception as e:
                    logger.warning(f"Error closing cloud page: {str(e)}")
            
            if context:
                try:
                    await context.close()
                    if context in self._contexts:
                        self._contexts.remove(context)
                    logger.debug("Cloud context closed successfully")
                except Exception as e:
                    logger.warning(f"Error closing cloud context: {str(e)}")
    
    async def get_session_info(self) -> Dict[str, Any]:
        """
        Get information about the current cloud browser session.
        
        Returns:
            Dict containing session information
        """
        if not self._session_id:
            return {"status": "not_connected"}
        
        try:
            headers = {
                "x-bb-api-key": settings.BROWSERBASE_API_KEY
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://www.browserbase.com/v1/sessions/{self._session_id}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    session_data = response.json()
                    return {
                        "status": "connected",
                        "session_id": self._session_id,
                        "session_data": session_data,
                        "contexts_count": len(self._contexts),
                        "browser_connected": self._browser.is_connected() if self._browser else False,
                        "connect_url_available": bool(self._connect_url)  # Add this for debugging
                    }
                else:
                    return {
                        "status": "error",
                        "session_id": self._session_id,
                        "error": f"HTTP {response.status_code}"
                    }
                    
        except Exception as e:
            logger.error(f"Error getting session info: {str(e)}")
            return {
                "status": "error",
                "session_id": self._session_id,
                "error": str(e)
            }
    
    async def cleanup(self) -> None:
        """Clean up cloud browser resources with improved error handling."""
        logger.info("Cleaning up cloud browser service")
        
        # End Browserbase session FIRST (before closing browser)
        if self._session_id:
            try:
                await self._end_session()
            except Exception as e:
                logger.warning(f"Error ending Browserbase session: {str(e)}")
        
        # Close all contexts
        for context in self._contexts[:]:
            try:
                await asyncio.wait_for(context.close(), timeout=5.0)
                self._contexts.remove(context)
                logger.debug("Cloud context closed successfully")
            except asyncio.TimeoutError:
                logger.warning("Context close timed out")
            except Exception as e:
                logger.warning(f"Error closing cloud context: {str(e)}")
        
        # Close browser connection
        if self._browser:
            try:
                # Set a timeout for browser closing
                await asyncio.wait_for(self._browser.close(), timeout=10.0)
                logger.info("Cloud browser connection closed")
            except asyncio.TimeoutError:
                logger.warning("Browser close timed out - forcing disconnect")
            except Exception as e:
                logger.warning(f"Error closing cloud browser: {str(e)}")
            finally:
                self._browser = None
        
        # Stop playwright (with event loop protection)
        if self._playwright:
            try:
                # Check if event loop is still running
                loop = asyncio.get_event_loop()
                if not loop.is_closed():
                    await asyncio.wait_for(self._playwright.stop(), timeout=5.0)
                    logger.info("Playwright stopped")
                else:
                    logger.warning("Event loop closed, skipping playwright.stop()")
            except asyncio.TimeoutError:
                logger.warning("Playwright stop timed out")
            except RuntimeError as e:
                if "Event loop is closed" in str(e):
                    logger.warning("Event loop closed during playwright cleanup")
                else:
                    logger.warning(f"Runtime error stopping Playwright: {str(e)}")
            except Exception as e:
                logger.warning(f"Error stopping Playwright: {str(e)}")
            finally:
                self._playwright = None
        
        self._is_connected = False
        self._session_id = None
        self._connect_url = None 
        logger.info("Cloud browser service cleanup completed")

    async def _end_session(self) -> None:
        """End the Browserbase session with improved error handling."""
        if not self._session_id:
            return
        
        try:
            headers = {
                "x-bb-api-key": settings.BROWSERBASE_API_KEY,
                "Content-Type": "application/json"
            }
            
            # Use a shorter timeout for cleanup operations
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Try the correct API endpoint format
                response = await client.post(
                    f"https://www.browserbase.com/v1/sessions/{self._session_id}/stop",
                    headers=headers
                )
                
                if response.status_code in [200, 201, 204]:
                    logger.info(f"Browserbase session {self._session_id} stopped successfully")
                    return
                elif response.status_code == 404:
                    logger.info(f"Browserbase session {self._session_id} already ended")
                    return
                else:
                    # If POST /stop doesn't work, try DELETE
                    logger.warning(f"POST /stop failed with {response.status_code}, trying DELETE")
                    
                    delete_response = await client.delete(
                        f"https://www.browserbase.com/v1/sessions/{self._session_id}",
                        headers=headers
                    )
                    
                    if delete_response.status_code in [200, 204, 404]:
                        logger.info(f"Browserbase session {self._session_id} deleted successfully")
                    else:
                        logger.warning(f"Failed to end session {self._session_id}: DELETE returned {delete_response.status_code}")
                        logger.warning(f"Response: {delete_response.text}")
                    
        except httpx.TimeoutException:
            logger.error(f"Timeout ending Browserbase session {self._session_id}")
        except Exception as e:
            logger.error(f"Error ending Browserbase session {self._session_id}: {str(e)}")
        finally:
            # Always clear the session ID to prevent retry attempts
            logger.info(f"Clearing session ID {self._session_id}")
            self._session_id = None


# Factory function to create appropriate browser service
def create_browser_service():
    """
    Factory function to create the appropriate browser service based on configuration.
    
    Returns:
        BrowserService or CloudBrowserService based on settings
    """
    if getattr(settings, 'USE_CLOUD_BROWSER', False):
        logger.info("Creating cloud browser service")
        return CloudBrowserService()
    else:
        logger.info("Creating local browser service")
        from .browser_service import BrowserService
        return BrowserService()


# Global cloud browser service instance
cloud_browser_service = CloudBrowserService()