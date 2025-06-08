import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.services.cloud_browser import CloudBrowserService
from app.services.browser_manager import BrowserManager, BrowserType
from app.core.exceptions import (
    BrowserError, 
    BrowserConnectionError,
    ConfigurationError
)
from app.config import settings


class TestCloudBrowserService:
    """Test suite for CloudBrowserService functionality."""
    
    @pytest.fixture
    async def service(self):
        """Create a fresh cloud browser service instance for testing."""
        service = CloudBrowserService()
        yield service
        # Cleanup after test
        await service.cleanup()
    
    def test_validate_configuration_missing_api_key(self, service):
        """Test configuration validation with missing API key."""
        with patch.object(settings, 'BROWSERBASE_API_KEY', None):
            with pytest.raises(ConfigurationError, match="Browserbase API key not configured"):
                service._validate_configuration()
    
    def test_validate_configuration_missing_project_id(self, service):
        """Test configuration validation with missing project ID."""
        with patch.object(settings, 'BROWSERBASE_API_KEY', 'test-key'), \
             patch.object(settings, 'BROWSERBASE_PROJECT_ID', None):
            with pytest.raises(ConfigurationError, match="Browserbase project ID not configured"):
                service._validate_configuration()
    
    def test_validate_configuration_success(self, service):
        """Test successful configuration validation."""
        with patch.object(settings, 'BROWSERBASE_API_KEY', 'test-key'), \
             patch.object(settings, 'BROWSERBASE_PROJECT_ID', 'test-project'):
            # Should not raise
            service._validate_configuration()
    
    @pytest.mark.asyncio
    async def test_create_session_sends_user_agent(self, service):
        """Test that session creation request includes a random user agent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test-session-ua",
            "connectUrl": "wss://test-ua-connect-url"
        }
        
        with patch.object(settings, 'BROWSERBASE_API_KEY', 'test-key'), \
             patch.object(settings, 'BROWSERBASE_PROJECT_ID', 'test-project'), \
             patch('httpx.AsyncClient') as mock_client:
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            await service._create_session()

            mock_post = mock_client.return_value.__aenter__.return_value.post
            mock_post.assert_called_once()
            
            post_kwargs = mock_post.call_args.kwargs
            assert "json" in post_kwargs
            
            payload = post_kwargs["json"]
            assert "browserSettings" in payload
            assert "fingerprint" in payload["browserSettings"]
            assert "userAgent" in payload["browserSettings"]["fingerprint"]
            
            sent_user_agent = payload["browserSettings"]["fingerprint"]["userAgent"]
            assert sent_user_agent in settings.USER_AGENTS
            
    @pytest.mark.asyncio
    async def test_create_session_success(self, service):
        """Test successful session creation."""
        # Fix: Mock response should include connectUrl like real Browserbase
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test-session-123",
            "connectUrl": "wss://test-connect-url"  # Add the missing connectUrl
        }
        
        with patch.object(settings, 'BROWSERBASE_API_KEY', 'test-key'), \
            patch.object(settings, 'BROWSERBASE_PROJECT_ID', 'test-project'), \
            patch('httpx.AsyncClient') as mock_client:
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            # Fix: Method now returns tuple (session_id, connect_url)
            session_id, connect_url = await service._create_session()
            
            assert session_id == "test-session-123"
            assert connect_url == "wss://test-connect-url"

    @pytest.mark.asyncio
    async def test_create_session_with_connection_url(self, service):
        """Test that session creation returns both session ID and connection URL."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "test-session-456",
            "connectUrl": "wss://test-connection-url",
            "status": "RUNNING"
        }
        
        with patch.object(settings, 'BROWSERBASE_API_KEY', 'test-key'), \
            patch.object(settings, 'BROWSERBASE_PROJECT_ID', 'test-project'), \
            patch('httpx.AsyncClient') as mock_client:
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            session_id, connect_url = await service._create_session()
            
            assert session_id == "test-session-456"
            assert connect_url == "wss://test-connection-url"
    

    @pytest.mark.asyncio
    async def test_create_session_missing_connect_url(self, service):
        """Test session creation failure when connectUrl is missing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test-session-789"
            # Missing connectUrl
        }
        
        with patch.object(settings, 'BROWSERBASE_API_KEY', 'test-key'), \
            patch.object(settings, 'BROWSERBASE_PROJECT_ID', 'test-project'), \
            patch('httpx.AsyncClient') as mock_client:
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            with pytest.raises(BrowserConnectionError, match="No connection URL returned"):
                await service._create_session()


    @pytest.mark.asyncio
    async def test_create_session_authentication_error(self, service):
        """Test session creation with authentication error."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        
        with patch.object(settings, 'BROWSERBASE_API_KEY', 'invalid-key'), \
             patch.object(settings, 'BROWSERBASE_PROJECT_ID', 'test-project'), \
             patch('httpx.AsyncClient') as mock_client:
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            with pytest.raises(BrowserConnectionError, match="Browserbase authentication failed"):
                await service._create_session()
    
    @pytest.mark.asyncio
    async def test_create_session_timeout(self, service):
        """Test session creation with timeout."""
        with patch.object(settings, 'BROWSERBASE_API_KEY', 'test-key'), \
             patch.object(settings, 'BROWSERBASE_PROJECT_ID', 'test-project'), \
             patch('httpx.AsyncClient') as mock_client:
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("Request timeout")
            )
            
            with pytest.raises(BrowserConnectionError, match="Timeout connecting to Browserbase"):
                await service._create_session()
    
    @pytest.mark.asyncio
    async def test_create_session_network_error(self, service):
        """Test session creation with network error."""
        with patch.object(settings, 'BROWSERBASE_API_KEY', 'test-key'), \
             patch.object(settings, 'BROWSERBASE_PROJECT_ID', 'test-project'), \
             patch('httpx.AsyncClient') as mock_client:
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.RequestError("Network error")
            )
            
            with pytest.raises(BrowserConnectionError, match="Network error"):
                await service._create_session()
    
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, service):
        """Test successful cloud browser initialization."""
        # Fix: Mock the new method signature and remove _get_connection_url
        with patch.object(service, '_create_session', return_value=("test-session", "wss://test-url")), \
            patch('app.services.cloud_browser.async_playwright') as mock_playwright:
            
            # Mock playwright components
            mock_playwright_instance = AsyncMock()
            mock_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)
            
            mock_browser = AsyncMock()
            mock_browser.is_connected.return_value = True
            mock_playwright_instance.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)
            
            await service.initialize()
            
            assert service._is_connected is True
            assert service._session_id == "test-session"
            assert service._connect_url == "wss://test-url"  # Test new attribute
            assert service._browser is mock_browser
        @pytest.mark.asyncio
        async def test_initialize_failure(self, service):
            """Test cloud browser initialization failure."""
            with patch.object(service, '_create_session', side_effect=Exception("Session creation failed")):
                
                with pytest.raises(BrowserConnectionError, match="Cloud browser initialization failed"):
                    await service.initialize()
                
                assert service._is_connected is False
                assert service._session_id is None
    
    @pytest.mark.asyncio
    async def test_create_context_success(self, service):
        """Test successful context creation."""
        # Mock connected state
        service._is_connected = True
        service._browser = AsyncMock()
        
        mock_context = AsyncMock()
        service._browser.new_context = AsyncMock(return_value=mock_context)
        
        context = await service.create_context()
        
        assert context is mock_context
        assert len(service._contexts) == 1
    
    @pytest.mark.asyncio
    async def test_create_context_not_connected(self, service):
        """Test context creation when not connected."""
        with pytest.raises(BrowserError, match="Cloud browser service not connected"):
            await service.create_context()
    
    @pytest.mark.asyncio
    async def test_create_page_success(self, service):
        """Test successful page creation."""
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        
        # Fix 3: Use MagicMock for sync methods
        mock_page.set_default_timeout = MagicMock()
        mock_page.set_default_navigation_timeout = MagicMock()
        
        page = await service.create_page(mock_context)
        
        assert page is mock_page
        mock_page.set_default_timeout.assert_called()
        mock_page.set_default_navigation_timeout.assert_called()
    
    @pytest.mark.asyncio
    async def test_page_context_manager(self, service):
        """Test page context manager."""
        service._is_connected = True
        service._browser = AsyncMock()
        
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        service._browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        
        # Mock page methods
        mock_page.set_default_timeout = MagicMock()
        mock_page.set_default_navigation_timeout = MagicMock()
        mock_page.close = AsyncMock()
        mock_context.close = AsyncMock()
        
        async with service.page_context() as page:
            assert page is mock_page
        
        # Verify cleanup
        mock_page.close.assert_called_once()
        mock_context.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_session_info_success(self, service):
        """Test successful session info retrieval."""
        service._session_id = "test-session"
        service._browser = AsyncMock()
        service._connect_url = "wss://test-url"  # Add missing attribute
        
        # Use MagicMock for sync method
        service._browser.is_connected = MagicMock(return_value=True)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "active", "id": "test-session"}
        
        with patch.object(settings, 'BROWSERBASE_API_KEY', 'test-key'), \
            patch('httpx.AsyncClient') as mock_client:
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            info = await service.get_session_info()
            
            assert info["status"] == "connected"
            assert info["session_id"] == "test-session"
            assert info["browser_connected"] is True
            assert info["connect_url_available"] is True  # Test new field
    
    @pytest.mark.asyncio
    async def test_get_session_info_not_connected(self, service):
        """Test session info when not connected."""
        info = await service.get_session_info()
        assert info["status"] == "not_connected"
    
    @pytest.mark.asyncio
    async def test_cleanup_success(self, service):
        """Test successful cleanup."""
        # Fix: Create proper mock objects that persist through cleanup
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()
        mock_context1 = AsyncMock()
        mock_context2 = AsyncMock()
        
        # Mock connected state with new attributes
        service._is_connected = True
        service._session_id = "test-session"
        service._connect_url = "wss://test-url"  # Add missing attribute
        service._browser = mock_browser
        service._playwright = mock_playwright
        service._contexts = [mock_context1, mock_context2]
        
        # Mock end session
        with patch.object(service, '_end_session', return_value=None):
            await service.cleanup()
        
        # Verify cleanup - the mocks should still exist
        mock_context1.close.assert_called_once()
        mock_context2.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
        
        assert service._is_connected is False
        assert service._session_id is None
        assert service._connect_url is None  # Test cleanup of new attribute
        assert len(service._contexts) == 0
    
    @pytest.mark.asyncio
    async def test_end_session_success(self, service):
        """Test successful session termination."""
        service._session_id = "test-session"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch.object(settings, 'BROWSERBASE_API_KEY', 'test-key'), \
             patch('httpx.AsyncClient') as mock_client:
            
            mock_client.return_value.__aenter__.return_value.delete = AsyncMock(return_value=mock_response)
            
            await service._end_session()
            
            # Should not raise
    