# backend/tests/test_browser_service.py

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
import os

from app.services.browser_service import BrowserService
from app.core.exceptions import (
    BrowserError, 
    BrowserTimeoutError, 
    BrowserConnectionError
)
from app.config import settings


class TestBrowserService:
    """Test suite for BrowserService core functionality."""
    
    @pytest.fixture
    async def service(self):
        service_instance = BrowserService()
        yield service_instance
        await service_instance.cleanup()
    
    # --- THIS TEST IS NOW CORRECTED ---
    @pytest.mark.asyncio
    async def test_initialization_success(self, service):
        """Test successful browser service initialization."""
        with patch('app.services.browser_service.async_playwright') as mock_async_playwright:
            # This is the corrected mock setup
            mock_playwright_manager = AsyncMock()
            mock_playwright_instance = AsyncMock()
            mock_async_playwright.return_value = mock_playwright_manager
            mock_playwright_manager.start.return_value = mock_playwright_instance
            
            mock_browser_type = AsyncMock()
            mock_browser = AsyncMock()
            mock_browser_type.launch.return_value = mock_browser
            setattr(mock_playwright_instance, settings.BROWSER_TYPE, mock_browser_type)
            
            await service.initialize()
            
            assert service._is_initialized is True
            assert service._browser is not None
            mock_playwright_manager.start.assert_called_once()
            mock_browser_type.launch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialization_failure(self, service):
        """Test browser service initialization failure."""
        with patch('app.services.browser_service.async_playwright') as mock_playwright:
            mock_playwright.return_value.start.side_effect = Exception("Playwright failed")
            
            with pytest.raises(BrowserConnectionError, match="Browser initialization failed"):
                await service.initialize()
            
            assert service._is_initialized is False
            assert service._browser is None
    
    # --- THIS TEST IS NOW CORRECTED ---
    @pytest.mark.asyncio
    async def test_initialize_with_proxy(self, service):
        """Test that launch options include proxy when configured."""
        proxy_url = "http://user:pass@proxy.test.com:8080"
        
        with patch.object(settings, 'PROXY_URL', proxy_url), \
             patch('app.services.browser_service.async_playwright') as mock_async_playwright:
            
            # Use the same corrected mock setup
            mock_playwright_manager = AsyncMock()
            mock_playwright_instance = AsyncMock()
            mock_async_playwright.return_value = mock_playwright_manager
            mock_playwright_manager.start.return_value = mock_playwright_instance

            mock_browser_type = AsyncMock()
            setattr(mock_playwright_instance, settings.BROWSER_TYPE, mock_browser_type)

            await service.initialize()

            mock_browser_type.launch.assert_called_once()
            launch_kwargs = mock_browser_type.launch.call_args.kwargs
            assert "proxy" in launch_kwargs
            assert launch_kwargs["proxy"]["server"] == proxy_url

    @pytest.mark.asyncio
    async def test_create_context_with_random_user_agent(self, service):
        """Test that a random user agent is used when creating a context."""
        service._is_initialized = True
        service._browser = AsyncMock()
        mock_context = AsyncMock()
        service._browser.new_context.return_value = mock_context

        await service.create_context()

        service._browser.new_context.assert_called_once()
        context_kwargs = service._browser.new_context.call_args.kwargs
        assert "user_agent" in context_kwargs
        assert context_kwargs["user_agent"] in settings.USER_AGENTS

    @pytest.mark.asyncio
    async def test_create_page_applies_stealth(self, service):
        """Test that the stealth plugin is applied to new pages."""
        service._is_initialized = True
        service._browser = AsyncMock()
        
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_page.set_default_timeout = MagicMock()
        mock_page.set_default_navigation_timeout = MagicMock()

        service._browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        with patch('app.services.browser_service.stealth_async') as mock_stealth:
            with patch.object(settings, 'USE_STEALTH_PLUGIN', True):
                page = await service.create_page()
                mock_stealth.assert_called_once_with(page)
    
    # --- ALL OTHER TESTS BELOW ARE UNCHANGED ---

    @pytest.mark.asyncio
    async def test_create_context_success(self, service):
        """Test successful browser context creation."""
        service._is_initialized = True
        service._browser = AsyncMock()
        
        mock_context = AsyncMock()
        service._browser.new_context.return_value = mock_context
        
        context = await service.create_context()
        
        assert context is mock_context
        assert len(service._contexts) == 1
        service._browser.new_context.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_context_not_initialized(self, service):
        """Test context creation when service not initialized."""
        with pytest.raises(BrowserError, match="Browser service not initialized"):
            await service.create_context()
    
    @pytest.mark.asyncio
    async def test_create_page_success(self, service):
        """Test successful page creation."""
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_context.new_page.return_value = mock_page
        
        mock_page.set_default_timeout = MagicMock()
        mock_page.set_default_navigation_timeout = MagicMock()
        
        page = await service.create_page(mock_context)
        
        assert page is mock_page
        mock_context.new_page.assert_called_once()
        mock_page.set_default_timeout.assert_called()
        mock_page.set_default_navigation_timeout.assert_called()
    
    @pytest.mark.asyncio
    async def test_create_page_without_context(self, service):
        """Test page creation without providing context."""
        service._is_initialized = True
        service._browser = AsyncMock()
        
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        service._browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        
        mock_page.set_default_timeout = MagicMock()
        mock_page.set_default_navigation_timeout = MagicMock()
        
        page = await service.create_page()
        
        assert page is mock_page
        assert len(service._contexts) == 1
    
    @pytest.mark.asyncio
    async def test_navigate_to_url_success(self, service):
        """Test successful URL navigation."""
        mock_page = AsyncMock()
        mock_response = AsyncMock()
        mock_response.ok = True
        mock_response.status = 200
        mock_page.goto.return_value = mock_response
        
        await service.navigate_to_url(mock_page, "https://example.com")
        
        mock_page.goto.assert_called_once_with(
            "https://example.com",
            wait_until="networkidle",
            timeout=30000
        )
    
    @pytest.mark.asyncio
    async def test_navigate_to_url_timeout(self, service):
        """Test URL navigation timeout."""
        mock_page = AsyncMock()
        mock_page.goto.side_effect = PlaywrightTimeoutError("Navigation timeout")
        
        with pytest.raises(BrowserTimeoutError, match="Navigation to https://example.com timed out"):
            await service.navigate_to_url(mock_page, "https://example.com")
    
    @pytest.mark.asyncio
    async def test_navigate_to_url_no_response(self, service):
        """Test URL navigation with no response."""
        mock_page = AsyncMock()
        mock_page.goto.return_value = None
        
        with pytest.raises(BrowserError, match="Failed to navigate to https://example.com: No response received"):
            await service.navigate_to_url(mock_page, "https://example.com")
    
    @pytest.mark.asyncio
    async def test_wait_for_page_load_success(self, service):
        """Test successful page load waiting."""
        mock_page = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()
        
        await service.wait_for_page_load(mock_page)
        
        mock_page.wait_for_load_state.assert_called_once_with("networkidle", timeout=30000)
        mock_page.wait_for_timeout.assert_called_once_with(1000)
    
    @pytest.mark.asyncio
    async def test_wait_for_page_load_timeout(self, service):
        """Test page load waiting timeout."""
        mock_page = AsyncMock()
        mock_page.wait_for_load_state.side_effect = PlaywrightTimeoutError("Load timeout")
        
        with pytest.raises(BrowserTimeoutError, match="Page load timed out"):
            await service.wait_for_page_load(mock_page)
    
    @pytest.mark.asyncio
    async def test_page_context_manager_success(self, service):
        """Test page context manager successful flow."""
        service._is_initialized = True
        service._browser = AsyncMock()
        
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        service._browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        
        mock_page.set_default_timeout = MagicMock()
        mock_page.set_default_navigation_timeout = MagicMock()
        mock_page.close = AsyncMock()
        mock_context.close = AsyncMock()
        
        async with service.page_context() as page:
            assert page is mock_page
        
        mock_page.close.assert_called_once()
        mock_context.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_page_context_manager_timeout_error(self, service):
        """Test page context manager with timeout error."""
        service._is_initialized = True
        service._browser = AsyncMock()
        
        mock_context = AsyncMock()
        service._browser.new_context.return_value = mock_context
        mock_context.new_page.side_effect = PlaywrightTimeoutError("Timeout")
        mock_context.close = AsyncMock()
        
        with pytest.raises(BrowserError, match="Page context error"):
            async with service.page_context() as page:
                pass
        
        mock_context.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_browser_info_initialized(self, service):
        """Test browser info when initialized."""
        service._browser = AsyncMock()
        service._browser.version = "1.40.0"
        service._browser.is_connected = MagicMock(return_value=True)
        service._contexts = [AsyncMock(), AsyncMock()]
        
        info = await service.get_browser_info()
        
        assert info["status"] == "initialized"
        assert info["browser_type"] == settings.BROWSER_TYPE
        assert info["version"] == "1.40.0"
        assert info["contexts_count"] == 2
        assert info["is_connected"] is True
    
    @pytest.mark.asyncio
    async def test_get_browser_info_not_initialized(self, service):
        """Test browser info when not initialized."""
        info = await service.get_browser_info()
        assert info["status"] == "not_initialized"
    
    @pytest.mark.asyncio
    async def test_cleanup_success(self, service):
        """Test successful cleanup."""
        service._is_initialized = True
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()
        service._browser = mock_browser
        service._playwright = mock_playwright
        
        mock_context1 = AsyncMock()
        mock_context2 = AsyncMock()
        service._contexts = [mock_context1, mock_context2]
        
        await service.cleanup()
        
        mock_context1.close.assert_called_once()
        mock_context2.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
        assert service._is_initialized is False
        assert service._browser is None
        assert service._playwright is None
        assert len(service._contexts) == 0
    
    @pytest.mark.asyncio
    async def test_async_context_manager(self, service):
        """Test browser service as async context manager."""
        with patch.object(service, 'initialize') as mock_init, \
             patch.object(service, 'cleanup') as mock_cleanup:
            
            async with service as s:
                assert s is service
            
            mock_init.assert_called_once()
            mock_cleanup.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_browser_service_integration():
    """
    Integration test for browser service.
    Requires actual Playwright installation.
    Run with: pytest -m integration
    """
    service = BrowserService()
    
    try:
        await service.initialize()
        info = await service.get_browser_info()
        
        assert info["status"] == "initialized"
        assert info["is_connected"] is True
        
        async with service.page_context() as page:
            await service.navigate_to_url(page, "https://httpbin.org/status/200")
            await service.wait_for_page_load(page)
            
            title = await page.title()
            assert title is not None
            
    finally:
        await service.cleanup()