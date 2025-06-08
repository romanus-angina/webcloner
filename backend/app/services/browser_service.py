from typing import Optional, Dict, Any, List, Union
import asyncio
import logging
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from ..config import settings
from ..core.exceptions import BrowserError, BrowserTimeoutError, BrowserConnectionError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class BrowserService:
    """
    Core browser automation service using Playwright.
    
    Manages browser lifecycle, provides page creation and cleanup,
    and handles browser configuration for web scraping operations.
    """
    
    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._contexts: List[BrowserContext] = []
        self._is_initialized = False
        
    async def initialize(self) -> None:
        """Initialize the browser service with Playwright."""
        if self._is_initialized:
            logger.warning("Browser service already initialized")
            return
            
        try:
            logger.info("Initializing browser service with Playwright")
            self._playwright = await async_playwright().start()
            
            # Launch browser based on configuration
            browser_type = getattr(self._playwright, settings.BROWSER_TYPE)
            
            launch_options = self._get_launch_options()
            self._browser = await browser_type.launch(**launch_options)
            
            self._is_initialized = True
            logger.info(f"Browser service initialized successfully with {settings.BROWSER_TYPE}")
            
        except Exception as e:
            logger.error(f"Failed to initialize browser service: {str(e)}")
            await self.cleanup()
            raise BrowserConnectionError(f"Browser initialization failed: {str(e)}")
    
    def _get_launch_options(self) -> Dict[str, Any]:
        """Get browser launch options based on configuration."""
        options = {
            "headless": settings.BROWSER_HEADLESS,
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-default-apps",
            ]
        }
        
        # Add viewport size if specified
        if hasattr(settings, 'BROWSER_VIEWPORT_WIDTH') and hasattr(settings, 'BROWSER_VIEWPORT_HEIGHT'):
            options["args"].extend([
                f"--window-size={settings.BROWSER_VIEWPORT_WIDTH},{settings.BROWSER_VIEWPORT_HEIGHT}"
            ])
        
        # Add timeout settings
        if hasattr(settings, 'BROWSER_TIMEOUT'):
            options["timeout"] = settings.BROWSER_TIMEOUT * 1000  # Convert to milliseconds
            
        return options
    
    async def create_context(self, **context_options) -> BrowserContext:
        """
        Create a new browser context with optional configuration.
        
        Inputs:
            **context_options: Additional context configuration options
            
        Returns:
            BrowserContext: New browser context
            
        Raises:
            BrowserError: If context creation fails
        """
        if not self._is_initialized or not self._browser:
            raise BrowserError("Browser service not initialized")
            
        try:
            # Default context options
            default_options = {
                "viewport": {
                    "width": getattr(settings, 'BROWSER_VIEWPORT_WIDTH', 1920),
                    "height": getattr(settings, 'BROWSER_VIEWPORT_HEIGHT', 1080)
                },
                "user_agent": getattr(settings, 'BROWSER_USER_AGENT', None),
                "java_script_enabled": True,
                "accept_downloads": False,
                "ignore_https_errors": True,
            }
            
            # Merge with provided options
            options = {**default_options, **context_options}
            
            context = await self._browser.new_context(**options)
            self._contexts.append(context)
            
            logger.debug(f"Created new browser context (total: {len(self._contexts)})")
            return context
            
        except Exception as e:
            logger.error(f"Failed to create browser context: {str(e)}")
            raise BrowserError(f"Context creation failed: {str(e)}")
    
    async def create_page(self, context: Optional[BrowserContext] = None) -> Page:
        """
        Create a new page in the specified context or create a new context.
        
        Inputs:
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
            
            # Set default timeouts
            page.set_default_timeout(getattr(settings, 'BROWSER_TIMEOUT', 30) * 1000)
            page.set_default_navigation_timeout(getattr(settings, 'BROWSER_NAVIGATION_TIMEOUT', 30) * 1000)
            
            logger.debug("Created new browser page")
            return page
            
        except Exception as e:
            logger.error(f"Failed to create browser page: {str(e)}")
            raise BrowserError(f"Page creation failed: {str(e)}")
    
    @asynccontextmanager
    async def page_context(self, **context_options):
        """
        Context manager for creating and cleaning up browser pages.
        
        Inputs:
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
            
        except PlaywrightTimeoutError as e:
            logger.error(f"Browser operation timed out: {str(e)}")
            raise BrowserTimeoutError(f"Operation timed out: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error in page context: {str(e)}")
            raise BrowserError(f"Page context error: {str(e)}")
            
        finally:
            # Cleanup page and context
            if page:
                try:
                    await page.close()
                    logger.debug("Page closed successfully")
                except Exception as e:
                    logger.warning(f"Error closing page: {str(e)}")
            
            if context:
                try:
                    await context.close()
                    if context in self._contexts:
                        self._contexts.remove(context)
                    logger.debug("Context closed successfully")
                except Exception as e:
                    logger.warning(f"Error closing context: {str(e)}")
    
    async def navigate_to_url(self, page: Page, url: str, wait_for: str = "networkidle") -> None:
        """
        Navigate to a URL with error handling and wait conditions.
        
        Inputs:
            page: Browser page instance
            url: URL to navigate to
            wait_for: Wait condition ('load', 'domcontentloaded', 'networkidle')
            
        Raises:
            BrowserTimeoutError: If navigation times out
            BrowserError: If navigation fails
        """
        try:
            logger.info(f"Navigating to URL: {url}")
            
            response = await page.goto(
                url,
                wait_until=wait_for,
                timeout=getattr(settings, 'BROWSER_NAVIGATION_TIMEOUT', 30) * 1000
            )
            
            if response is None:
                raise BrowserError(f"Failed to navigate to {url}: No response received")
            
            if not response.ok:
                logger.warning(f"Navigation returned non-OK status: {response.status}")
            
            logger.info(f"Successfully navigated to {url} (status: {response.status})")
            
        except PlaywrightTimeoutError as e:
            logger.error(f"Navigation timeout for {url}: {str(e)}")
            raise BrowserTimeoutError(f"Navigation to {url} timed out")
            
        except Exception as e:
            logger.error(f"Navigation failed for {url}: {str(e)}")
            raise BrowserError(f"Navigation to {url} failed: {str(e)}")
    
    async def wait_for_page_load(self, page: Page, timeout: Optional[int] = None) -> None:
        """
        Wait for page to be fully loaded with custom timeout.
        
        Inputs:
            page: Browser page instance
            timeout: Optional timeout in seconds
            
        Raises:
            BrowserTimeoutError: If page load times out
        """
        timeout_ms = (timeout or getattr(settings, 'BROWSER_TIMEOUT', 30)) * 1000
        
        try:
            # Wait for network to be idle
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)
            
            # Additional wait for any dynamic content
            await page.wait_for_timeout(1000)  # 1 second buffer
            
            logger.debug("Page fully loaded")
            
        except PlaywrightTimeoutError as e:
            logger.error(f"Page load timeout: {str(e)}")
            raise BrowserTimeoutError("Page load timed out")
    
    async def get_browser_info(self) -> Dict[str, Any]:
        """
        Get information about the current browser instance.
        
        Returns:
            Dict containing browser information
        """
        if not self._browser:
            return {"status": "not_initialized"}
        
        try:
            version = await self._browser.version()
            return {
                "status": "initialized",
                "browser_type": settings.BROWSER_TYPE,
                "version": version,
                "headless": settings.BROWSER_HEADLESS,
                "contexts_count": len(self._contexts),
                "is_connected": self._browser.is_connected()
            }
        except Exception as e:
            logger.error(f"Error getting browser info: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def cleanup(self) -> None:
        """Clean up browser resources."""
        logger.info("Cleaning up browser service")
        
        # Close all contexts
        for context in self._contexts[:]:  # Create a copy to iterate
            try:
                await context.close()
                self._contexts.remove(context)
            except Exception as e:
                logger.warning(f"Error closing context: {str(e)}")
        
        # Close browser
        if self._browser:
            try:
                await self._browser.close()
                logger.info("Browser closed successfully")
            except Exception as e:
                logger.warning(f"Error closing browser: {str(e)}")
            finally:
                self._browser = None
        
        # Stop playwright
        if self._playwright:
            try:
                await self._playwright.stop()
                logger.info("Playwright stopped successfully")
            except Exception as e:
                logger.warning(f"Error stopping Playwright: {str(e)}")
            finally:
                self._playwright = None
        
        self._is_initialized = False
        logger.info("Browser service cleanup completed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()


# Singleton instance for global use
browser_service = BrowserService()