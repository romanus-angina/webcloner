import pytest
import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from dataclasses import asdict

from app.services.screenshot_service import (
    ScreenshotService,
    Viewport,
    ViewportType,
    ScreenshotResult,
    ScreenshotBatch
)
from app.services.browser_manager import BrowserManager
from app.core.exceptions import BrowserError, ProcessingError


class TestViewport:
    """Test viewport configuration."""
    
    def test_viewport_creation_valid(self):
        """Test creating valid viewport."""
        viewport = Viewport(
            name="Test Viewport",
            width=1920,
            height=1080,
            device_scale_factor=1.0,
            is_mobile=False
        )
        
        assert viewport.name == "Test Viewport"
        assert viewport.width == 1920
        assert viewport.height == 1080
        assert viewport.device_scale_factor == 1.0
        assert viewport.is_mobile is False
    
    def test_viewport_creation_invalid_dimensions(self):
        """Test viewport creation with invalid dimensions."""
        with pytest.raises(ValueError, match="Invalid viewport dimensions"):
            Viewport(name="Invalid", width=0, height=1080)
        
        with pytest.raises(ValueError, match="Invalid viewport dimensions"):
            Viewport(name="Invalid", width=1920, height=-100)
    
    def test_viewport_creation_invalid_scale_factor(self):
        """Test viewport creation with invalid scale factor."""
        with pytest.raises(ValueError, match="Invalid device scale factor"):
            Viewport(
                name="Invalid",
                width=1920,
                height=1080,
                device_scale_factor=0
            )


class TestScreenshotResult:
    """Test screenshot result data structures."""
    
    def test_screenshot_result_creation(self):
        """Test creating screenshot result."""
        viewport = Viewport("Test", 1920, 1080)
        result = ScreenshotResult(
            viewport=viewport,
            file_path="/test/path.jpg",
            file_size=12345,
            capture_time=1.5,
            url="https://example.com",
            timestamp=time.time(),
            success=True
        )
        
        assert result.viewport == viewport
        assert result.file_path == "/test/path.jpg"
        assert result.file_size == 12345
        assert result.capture_time == 1.5
        assert result.success is True


class TestScreenshotBatch:
    """Test screenshot batch functionality."""
    
    def test_screenshot_batch_properties(self):
        """Test screenshot batch calculated properties."""
        viewport1 = Viewport("Desktop", 1920, 1080)
        viewport2 = Viewport("Mobile", 375, 667)
        
        successful_result = ScreenshotResult(
            viewport=viewport1,
            file_path="/test1.jpg",
            file_size=1000,
            capture_time=1.0,
            url="https://example.com",
            timestamp=time.time(),
            success=True
        )
        
        failed_result = ScreenshotResult(
            viewport=viewport2,
            file_path="",
            file_size=0,
            capture_time=0.5,
            url="https://example.com",
            timestamp=time.time(),
            success=False,
            error="Capture failed"
        )
        
        batch = ScreenshotBatch(
            url="https://example.com",
            session_id="test-session",
            screenshots=[successful_result, failed_result],
            total_capture_time=2.0,
            created_at=time.time()
        )
        
        assert len(batch.successful_screenshots) == 1
        assert len(batch.failed_screenshots) == 1
        assert batch.success_rate == 50.0


class TestScreenshotService:
    """Test suite for ScreenshotService."""
    
    @pytest.fixture
    def service(self):
        """Create screenshot service instance."""
        return ScreenshotService()
    
    @pytest.fixture
    def mock_browser_manager(self):
        """Create mock browser manager."""
        manager = AsyncMock(spec=BrowserManager)
        return manager
    
    def test_default_viewports_creation(self, service):
        """Test that default viewports are created correctly."""
        viewports = service.get_default_viewports()
        
        assert len(viewports) == 4  # mobile, tablet, desktop, large_desktop
        
        # Check that we have expected viewport types
        viewport_names = [v.name for v in viewports]
        assert "Mobile" in viewport_names
        assert "Tablet" in viewport_names
        assert "Desktop" in viewport_names
        assert "Large Desktop" in viewport_names
    
    def test_get_viewport_by_type(self, service):
        """Test getting viewport by type."""
        mobile_viewport = service.get_viewport_by_type(ViewportType.MOBILE)
        
        assert mobile_viewport.name == "Mobile"
        assert mobile_viewport.width == 375
        assert mobile_viewport.height == 667
        assert mobile_viewport.is_mobile is True
    
    def test_create_custom_viewport(self, service):
        """Test creating custom viewport."""
        custom_viewport = service.create_custom_viewport(
            name="Custom Test",
            width=1440,
            height=900,
            device_scale_factor=1.5,
            is_mobile=False
        )
        
        assert custom_viewport.name == "Custom Test"
        assert custom_viewport.width == 1440
        assert custom_viewport.height == 900
        assert custom_viewport.device_scale_factor == 1.5
        assert custom_viewport.is_mobile is False
    
    @pytest.mark.asyncio
    async def test_capture_screenshot_success(self, service, mock_browser_manager):
        """Test successful screenshot capture."""
        service.browser_manager = mock_browser_manager
        
        # Mock page and context
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        
        # Mock page methods
        mock_page.title.return_value = "Test Page"
        mock_page.screenshot = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.evaluate.return_value = {"width": 1920, "height": 2000}
        
        # Mock browser manager methods
        mock_browser_manager.page_context.return_value.__aenter__.return_value = mock_page
        mock_browser_manager.navigate_to_url = AsyncMock()
        mock_browser_manager.wait_for_page_load = AsyncMock()
        
        # Mock file system
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('app.services.screenshot_service.settings') as mock_settings:
                mock_settings.temp_storage_path = temp_dir
                
                # Create test file to simulate screenshot
                test_file = Path(temp_dir) / "screenshots" / "test.jpg"
                test_file.parent.mkdir(parents=True, exist_ok=True)
                test_file.write_bytes(b"fake_image_data")
                
                # Mock screenshot to create our test file
                def mock_screenshot(**kwargs):
                    Path(kwargs['path']).write_bytes(b"fake_image_data")
                
                mock_page.screenshot.side_effect = mock_screenshot
                
                viewport = Viewport("Test", 1920, 1080)
                result = await service.capture_screenshot(
                    url="https://example.com",
                    viewport=viewport,
                    session_id="test-session"
                )
                
                assert result.success is True
                assert result.viewport == viewport
                assert result.page_title == "Test Page"
                assert result.file_size > 0
                assert result.page_dimensions == (1920, 2000)
    
    @pytest.mark.asyncio
    async def test_capture_screenshot_browser_error(self, service, mock_browser_manager):
        """Test screenshot capture with browser error."""
        service.browser_manager = mock_browser_manager
        
        # Mock browser manager to raise error
        mock_browser_manager.page_context.side_effect = BrowserError("Browser failed")
        
        viewport = Viewport("Test", 1920, 1080)
        result = await service.capture_screenshot(
            url="https://example.com",
            viewport=viewport,
            session_id="test-session"
        )
        
        assert result.success is False
        assert "Browser failed" in result.error
        assert result.file_size == 0
    
    @pytest.mark.asyncio
    async def test_capture_screenshot_no_browser_manager(self, service):
        """Test screenshot capture without browser manager."""
        viewport = Viewport("Test", 1920, 1080)
        
        result = await service.capture_screenshot(
            url="https://example.com",
            viewport=viewport,
            session_id="test-session"
        )
        
        assert result.success is False
        assert "Browser manager not available" in result.error
    
    @pytest.mark.asyncio
    async def test_capture_multi_viewport_screenshots_sequential(self, service, mock_browser_manager):
        """Test multi-viewport screenshot capture in sequential mode."""
        service.browser_manager = mock_browser_manager
        
        # Mock successful captures
        with patch.object(service, 'capture_screenshot') as mock_capture:
            viewport1 = Viewport("Desktop", 1920, 1080)
            viewport2 = Viewport("Mobile", 375, 667)
            
            mock_capture.side_effect = [
                ScreenshotResult(
                    viewport=viewport1,
                    file_path="/test1.jpg",
                    file_size=1000,
                    capture_time=1.0,
                    url="https://example.com",
                    timestamp=time.time(),
                    success=True
                ),
                ScreenshotResult(
                    viewport=viewport2,
                    file_path="/test2.jpg",
                    file_size=800,
                    capture_time=0.8,
                    url="https://example.com",
                    timestamp=time.time(),
                    success=True
                )
            ]
            
            batch = await service.capture_multi_viewport_screenshots(
                url="https://example.com",
                session_id="test-session",
                viewports=[viewport1, viewport2],
                concurrent=False
            )
            
            assert len(batch.screenshots) == 2
            assert batch.success_rate == 100.0
            assert len(batch.successful_screenshots) == 2
            assert mock_capture.call_count == 2
    
    @pytest.mark.asyncio
    async def test_capture_multi_viewport_screenshots_concurrent(self, service, mock_browser_manager):
        """Test multi-viewport screenshot capture in concurrent mode."""
        service.browser_manager = mock_browser_manager
        
        # Mock successful captures
        with patch.object(service, 'capture_screenshot') as mock_capture:
            viewport1 = Viewport("Desktop", 1920, 1080)
            viewport2 = Viewport("Mobile", 375, 667)
            
            async def mock_capture_func(*args, **kwargs):
                # Simulate some async work
                await asyncio.sleep(0.1)
                viewport = args[1]  # viewport is second argument
                return ScreenshotResult(
                    viewport=viewport,
                    file_path=f"/test_{viewport.name}.jpg",
                    file_size=1000,
                    capture_time=0.5,
                    url="https://example.com",
                    timestamp=time.time(),
                    success=True
                )
            
            mock_capture.side_effect = mock_capture_func
            
            batch = await service.capture_multi_viewport_screenshots(
                url="https://example.com",
                session_id="test-session",
                viewports=[viewport1, viewport2],
                concurrent=True,
                max_concurrent=2
            )
            
            assert len(batch.screenshots) == 2
            assert batch.success_rate == 100.0
            assert mock_capture.call_count == 2
    
    @pytest.mark.asyncio
    async def test_capture_multi_viewport_with_failures(self, service, mock_browser_manager):
        """Test multi-viewport capture with some failures."""
        service.browser_manager = mock_browser_manager
        
        with patch.object(service, 'capture_screenshot') as mock_capture:
            viewport1 = Viewport("Desktop", 1920, 1080)
            viewport2 = Viewport("Mobile", 375, 667)
            
            # First succeeds, second fails
            mock_capture.side_effect = [
                ScreenshotResult(
                    viewport=viewport1,
                    file_path="/test1.jpg",
                    file_size=1000,
                    capture_time=1.0,
                    url="https://example.com",
                    timestamp=time.time(),
                    success=True
                ),
                ScreenshotResult(
                    viewport=viewport2,
                    file_path="",
                    file_size=0,
                    capture_time=0.5,
                    url="https://example.com",
                    timestamp=time.time(),
                    success=False,
                    error="Capture failed"
                )
            ]
            
            batch = await service.capture_multi_viewport_screenshots(
                url="https://example.com",
                session_id="test-session",
                viewports=[viewport1, viewport2],
                concurrent=False
            )
            
            assert len(batch.screenshots) == 2
            assert batch.success_rate == 50.0
            assert len(batch.successful_screenshots) == 1
            assert len(batch.failed_screenshots) == 1
    
    def test_generate_filename(self, service):
        """Test filename generation."""
        viewport = Viewport("Test Viewport", 1920, 1080)
        filename = service._generate_filename(
            url="https://example.com",
            viewport=viewport,
            session_id="test-session"
        )
        
        assert filename.startswith("test-session_")
        assert "test_viewport" in filename
        assert "1920x1080" in filename
        assert filename.endswith(".jpg")
    
    @pytest.mark.asyncio
    async def test_cleanup_screenshots(self, service):
        """Test screenshot cleanup functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('app.services.screenshot_service.settings') as mock_settings:
                mock_settings.temp_storage_path = temp_dir
                
                # Create test screenshot files
                screenshots_dir = Path(temp_dir) / "screenshots"
                screenshots_dir.mkdir(parents=True, exist_ok=True)
                
                # Create files for different sessions
                (screenshots_dir / "session1_hash_mobile_375x667_123.jpg").touch()
                (screenshots_dir / "session1_hash_desktop_1920x1080_124.jpg").touch()
                (screenshots_dir / "session2_hash_mobile_375x667_125.jpg").touch()
                
                # Test session-specific cleanup
                cleaned_count = await service.cleanup_screenshots(session_id="session1")
                
                assert cleaned_count == 2
                assert not (screenshots_dir / "session1_hash_mobile_375x667_123.jpg").exists()
                assert not (screenshots_dir / "session1_hash_desktop_1920x1080_124.jpg").exists()
                assert (screenshots_dir / "session2_hash_mobile_375x667_125.jpg").exists()
    
    @pytest.mark.asyncio
    async def test_get_screenshot_info(self, service):
        """Test getting screenshot information."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('app.services.screenshot_service.settings') as mock_settings:
                mock_settings.temp_storage_path = temp_dir
                
                # Create test screenshot files
                screenshots_dir = Path(temp_dir) / "screenshots"
                screenshots_dir.mkdir(parents=True, exist_ok=True)
                
                test_file = screenshots_dir / "test-session_hash_mobile_375x667_123.jpg"
                test_file.write_bytes(b"test_data")
                
                info = await service.get_screenshot_info("test-session")
                
                assert info["session_id"] == "test-session"
                assert info["screenshot_count"] == 1
                assert info["total_size"] == 9  # len(b"test_data")
                assert len(info["screenshots"]) == 1
                
                screenshot_info = info["screenshots"][0]
                assert screenshot_info["filename"] == test_file.name
                assert screenshot_info["size"] == 9


# Integration tests that require actual browser functionality
@pytest.mark.integration
@pytest.mark.asyncio
async def test_screenshot_service_integration():
    """
    Integration test for screenshot service with real browser.
    Requires browser manager to be properly initialized.
    """
    from app.services.browser_manager import BrowserManager, BrowserType
    
    browser_manager = BrowserManager(BrowserType.AUTO)
    
    try:
        await browser_manager.initialize()
        
        service = ScreenshotService(browser_manager)
        
        # Test with a simple data URL to avoid network dependencies
        test_url = "data:text/html,<html><body><h1>Test Page</h1></body></html>"
        
        viewport = service.get_viewport_by_type(ViewportType.DESKTOP)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('app.services.screenshot_service.settings') as mock_settings:
                mock_settings.temp_storage_path = temp_dir
                
                result = await service.capture_screenshot(
                    url=test_url,
                    viewport=viewport,
                    session_id="integration-test"
                )
                
                assert result.success is True
                assert result.file_size > 0
                assert Path(result.file_path).exists()
                
    finally:
        await browser_manager.cleanup()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_viewport_integration():
    """
    Integration test for multi-viewport screenshot capture.
    """
    from app.services.browser_manager import BrowserManager, BrowserType
    
    browser_manager = BrowserManager(BrowserType.AUTO)
    
    try:
        await browser_manager.initialize()
        
        service = ScreenshotService(browser_manager)
        
        test_url = "data:text/html,<html><body><h1>Multi Viewport Test</h1></body></html>"
        
        viewports = [
            service.get_viewport_by_type(ViewportType.MOBILE),
            service.get_viewport_by_type(ViewportType.DESKTOP)
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('app.services.screenshot_service.settings') as mock_settings:
                mock_settings.temp_storage_path = temp_dir
                
                batch = await service.capture_multi_viewport_screenshots(
                    url=test_url,
                    session_id="multi-viewport-test",
                    viewports=viewports,
                    concurrent=True
                )
                
                assert len(batch.screenshots) == 2
                assert batch.success_rate == 100.0
                
                for result in batch.screenshots:
                    assert result.success is True
                    assert result.file_size > 0
                    assert Path(result.file_path).exists()
                
    finally:
        await browser_manager.cleanup()