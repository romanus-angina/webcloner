import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
import tempfile
from pathlib import Path
import time

# Make sure we import the router correctly
from app.api.routes.screenshot import router
from app.models.screenshot import (
    ScreenshotRequest,
    ViewportModel,
    ViewportType
)
from app.services.screenshot_service import (
    ScreenshotService,
    Viewport,
    ScreenshotResult,
    ScreenshotBatch
)
from app.dependencies import (
    ApplicationState,
    validate_session_id,
    get_browser_manager,
    get_logger,
    get_app_state,
    check_rate_limit
)


# Create a test app with our router
app = FastAPI()
app.include_router(router, prefix="/api/v1/screenshots")


class TestScreenshotRoutes:
    """Test suite for screenshot API routes."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_dependencies(self):
        """Mock all route dependencies."""
        mock_app_state = MagicMock(spec=ApplicationState)
        mock_app_state.get_session.return_value = {
            "request": {"url": "https://example.com"},
            "status": "pending"
        }
        mock_app_state.update_session = MagicMock()
        
        mock_browser_manager = AsyncMock()
        mock_logger = MagicMock()
        
        return {
            "app_state": mock_app_state,
            "browser_manager": mock_browser_manager,
            "logger": mock_logger
        }
    
    def test_get_viewport_presets(self, client):
        """Test getting viewport presets."""
        with patch('app.api.routes.screenshot.ScreenshotService') as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            
            # Mock viewport methods
            mock_viewport = Viewport("Desktop", 1920, 1080)
            mock_service.get_viewport_by_type.return_value = mock_viewport
            
            response = client.get("/api/v1/screenshots/viewports/presets")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "presets" in data
            assert "custom_supported" in data
            assert "max_custom_viewports" in data
            assert data["custom_supported"] is True
            assert data["max_custom_viewports"] == 10
    
    def test_capture_screenshots_with_custom_viewports(self, client, mock_dependencies):
        """Test screenshot capture with custom viewports."""
        # Mock the dependencies
        with patch.multiple(
            'app.api.routes.screenshot',
            get_app_state=lambda: mock_dependencies["app_state"],
            get_browser_manager=lambda: mock_dependencies["browser_manager"],
            get_logger=lambda: mock_dependencies["logger"],
            get_request_id=lambda: "test-request-id",
            validate_session_id=lambda session_id: session_id,
            check_rate_limit=lambda: None
        ):
            # Mock ScreenshotService
            with patch('app.api.routes.screenshot.ScreenshotService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                
                # Mock successful screenshot batch
                viewport = Viewport("Custom", 1440, 900)
                screenshot_result = ScreenshotResult(
                    viewport=viewport,
                    file_path="/test/screenshot.jpg",
                    file_size=12345,
                    capture_time=1.5,
                    url="https://example.com",
                    timestamp=time.time(),
                    page_title="Test Page",
                    page_dimensions=(1440, 2000),
                    success=True
                )
                
                screenshot_batch = ScreenshotBatch(
                    url="https://example.com",
                    session_id="test-session",
                    screenshots=[screenshot_result],
                    total_capture_time=2.0,
                    created_at=time.time()
                )
                
                mock_service.create_custom_viewport.return_value = viewport
                mock_service.capture_multi_viewport_screenshots.return_value = screenshot_batch
                
                # Test request
                request_data = {
                    "url": "https://example.com",
                    "session_id": "test-session",
                    "viewports": [
                        {
                            "name": "Custom",
                            "width": 1440,
                            "height": 900,
                            "device_scale_factor": 1.0,
                            "is_mobile": False
                        }
                    ],
                    "concurrent": True,
                    "max_concurrent": 3,
                    "wait_for_load": True,
                    "full_page": True,
                    "quality": 90
                }
                
                response = client.post("/api/v1/screenshots/capture", json=request_data)
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["success"] is True
                assert data["session_id"] == "test-session"
                assert "data" in data
                assert data["data"]["success_count"] == 1
                assert data["data"]["failure_count"] == 0
                assert data["data"]["success_rate"] == 100.0
    
    def test_capture_screenshots_with_viewport_types(self, client, mock_dependencies):
        """Test screenshot capture with viewport types."""
        with patch.multiple(
            'app.api.routes.screenshot',
            get_app_state=lambda: mock_dependencies["app_state"],
            get_browser_manager=lambda: mock_dependencies["browser_manager"],
            get_logger=lambda: mock_dependencies["logger"],
            get_request_id=lambda: "test-request-id",
            validate_session_id=lambda session_id: session_id,
            check_rate_limit=lambda: None
        ):
            with patch('app.api.routes.screenshot.ScreenshotService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                
                # Mock viewport retrieval
                mobile_viewport = Viewport("Mobile", 375, 667, is_mobile=True)
                desktop_viewport = Viewport("Desktop", 1920, 1080)
                
                mock_service.get_viewport_by_type.side_effect = [mobile_viewport, desktop_viewport]
                
                # Mock screenshot results
                mobile_result = ScreenshotResult(
                    viewport=mobile_viewport,
                    file_path="/test/mobile.jpg",
                    file_size=8000,
                    capture_time=1.2,
                    url="https://example.com",
                    timestamp=time.time(),
                    success=True
                )
                
                desktop_result = ScreenshotResult(
                    viewport=desktop_viewport,
                    file_path="/test/desktop.jpg",
                    file_size=15000,
                    capture_time=1.8,
                    url="https://example.com",
                    timestamp=time.time(),
                    success=True
                )
                
                screenshot_batch = ScreenshotBatch(
                    url="https://example.com",
                    session_id="test-session",
                    screenshots=[mobile_result, desktop_result],
                    total_capture_time=3.5,
                    created_at=time.time()
                )
                
                mock_service.capture_multi_viewport_screenshots.return_value = screenshot_batch
                
                request_data = {
                    "url": "https://example.com",
                    "session_id": "test-session",
                    "viewport_types": ["mobile", "desktop"]
                }
                
                response = client.post("/api/v1/screenshots/capture", json=request_data)
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["success"] is True
                assert data["data"]["success_count"] == 2
                assert len(data["data"]["screenshots"]) == 2
    
    def test_capture_screenshots_with_defaults(self, client, mock_dependencies):
        """Test screenshot capture with default viewports."""
        with patch.multiple(
            'app.api.routes.screenshot',
            get_app_state=lambda: mock_dependencies["app_state"],
            get_browser_manager=lambda: mock_dependencies["browser_manager"],
            get_logger=lambda: mock_dependencies["logger"],
            get_request_id=lambda: "test-request-id",
            validate_session_id=lambda session_id: session_id,
            check_rate_limit=lambda: None
        ):
            with patch('app.api.routes.screenshot.ScreenshotService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                
                # Mock default viewports
                default_viewports = [
                    Viewport("Mobile", 375, 667, is_mobile=True),
                    Viewport("Desktop", 1920, 1080)
                ]
                mock_service.get_default_viewports.return_value = default_viewports
                
                # Mock successful batch
                screenshot_batch = ScreenshotBatch(
                    url="https://example.com",
                    session_id="test-session",
                    screenshots=[],  # We'll focus on the call rather than results
                    total_capture_time=2.0,
                    created_at=time.time()
                )
                
                mock_service.capture_multi_viewport_screenshots.return_value = screenshot_batch
                
                request_data = {
                    "url": "https://example.com",
                    "session_id": "test-session"
                }
                
                response = client.post("/api/v1/screenshots/capture", json=request_data)
                
                assert response.status_code == 200
                
                # Verify that get_default_viewports was called
                mock_service.get_default_viewports.assert_called_once()
                mock_service.capture_multi_viewport_screenshots.assert_called_once()
    
    def test_capture_screenshots_validation_error(self, client, mock_dependencies):
        """Test screenshot capture with validation error."""
        with patch.multiple(
            'app.api.routes.screenshot',
            get_app_state=lambda: mock_dependencies["app_state"],
            get_browser_manager=lambda: mock_dependencies["browser_manager"],
            get_logger=lambda: mock_dependencies["logger"],
            get_request_id=lambda: "test-request-id",
            validate_session_id=lambda session_id: session_id,
            check_rate_limit=lambda: None
        ):
            # Test with no viewports specified and empty viewport types
            request_data = {
                "url": "https://example.com",
                "session_id": "test-session",
                "viewport_types": ["custom"]  # This should result in no valid viewports
            }
            
            response = client.post("/api/v1/screenshots/capture", json=request_data)
            
            assert response.status_code == 200  # Our endpoint handles errors gracefully
            data = response.json()
            assert data["success"] is False
            assert "No valid viewports specified" in data["message"]
    
    def test_get_session_screenshots(self, client):
        """Test getting session screenshots info."""
        
        # Proper dependency override for FastAPI
        def mock_validate_session_id(session_id: str = "test-session"):
            return session_id
        
        def mock_get_browser_manager():
            return AsyncMock()
        
        # Override dependencies at the app level
        app.dependency_overrides[validate_session_id] = mock_validate_session_id
        app.dependency_overrides[get_browser_manager] = mock_get_browser_manager
        
        try:
            with patch('app.api.routes.screenshot.ScreenshotService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                
                # Mock screenshot info
                mock_info = {
                    "session_id": "test-session",
                    "screenshot_count": 2,
                    "total_size": 25000,
                    "screenshots": [
                        {
                            "filename": "test_mobile.jpg",
                            "size": 8000,
                            "created": time.time(),
                            "viewport_name": "Mobile",
                            "dimensions": "375x667",
                            "path": "/test/mobile.jpg"
                        },
                        {
                            "filename": "test_desktop.jpg",
                            "size": 17000,
                            "created": time.time(),
                            "viewport_name": "Desktop",
                            "dimensions": "1920x1080",
                            "path": "/test/desktop.jpg"
                        }
                    ]
                }
                
                mock_service.get_screenshot_info.return_value = mock_info
                
                response = client.get("/api/v1/screenshots/session/test-session/screenshots")
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["session_id"] == "test-session"
                assert data["status"] == "available"
                assert data["screenshots_info"]["screenshot_count"] == 2
                assert len(data["screenshots_info"]["screenshots"]) == 2
                
        finally:
            # Clean up dependency overrides
            app.dependency_overrides.clear()
    
    def test_cleanup_session_screenshots(self, client):
        """Test cleaning up session screenshots."""
        
        # Proper dependency override for FastAPI
        def mock_validate_session_id(session_id: str = "test-session"):
            return session_id
        
        def mock_get_browser_manager():
            return AsyncMock()
        
        def mock_get_logger():
            return MagicMock()
        
        # Override dependencies at the app level
        app.dependency_overrides[validate_session_id] = mock_validate_session_id
        app.dependency_overrides[get_browser_manager] = mock_get_browser_manager
        app.dependency_overrides[get_logger] = mock_get_logger
        
        try:
            with patch('app.api.routes.screenshot.ScreenshotService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                
                # Mock info before cleanup
                mock_service.get_screenshot_info.return_value = {
                    "total_size": 25000
                }
                
                # Mock cleanup
                mock_service.cleanup_screenshots.return_value = 3
                
                response = client.delete("/api/v1/screenshots/session/test-session/screenshots")
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["cleaned_count"] == 3
                assert data["total_freed_bytes"] == 25000
                assert data["session_id"] == "test-session"
                
        finally:
            # Clean up dependency overrides
            app.dependency_overrides.clear()
    
    def test_cleanup_old_screenshots(self, client):
        """Test cleaning up old screenshots."""
        with patch.multiple(
            'app.api.routes.screenshot',
            get_browser_manager=lambda: AsyncMock(),
            get_logger=lambda: MagicMock()
        ):
            with patch('app.api.routes.screenshot.ScreenshotService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                
                # Mock cleanup
                mock_service.cleanup_screenshots.return_value = 5
                
                # Mock the Path class and settings for size calculation
                with patch('app.api.routes.screenshot.settings') as mock_settings:
                    mock_settings.temp_storage_path = "/fake/path"
                    
                    # Mock Path to simulate file system
                    screenshots_dir_mock = MagicMock()
                    screenshots_dir_mock.exists.return_value = True
                    
                    # Mock files with sizes
                    mock_file = MagicMock()
                    mock_file.stat.return_value.st_size = 1000
                    screenshots_dir_mock.glob.return_value = [mock_file] * 10  # 10 files
                    
                    with patch('app.api.routes.screenshot.Path') as mock_path_class:
                        mock_path_class.return_value = screenshots_dir_mock
                        
                        response = client.delete("/api/v1/screenshots/cleanup?older_than_hours=48")
                        
                        assert response.status_code == 200
                        data = response.json()
                        
                        assert data["cleaned_count"] == 5
                        assert data["session_id"] is None
    
    def test_regenerate_session_screenshots(self, client, mock_dependencies):
        """Test regenerating screenshots for a session."""
        
        # Proper dependency override for FastAPI
        def mock_validate_session_id(session_id: str = "test-session"):
            return session_id
        
        def mock_get_app_state():
            return mock_dependencies["app_state"]
        
        def mock_get_browser_manager():
            return mock_dependencies["browser_manager"]
        
        def mock_get_logger():
            return mock_dependencies["logger"]
        
        def mock_check_rate_limit():
            return None
        
        # Override dependencies at the app level
        app.dependency_overrides[validate_session_id] = mock_validate_session_id
        app.dependency_overrides[get_app_state] = mock_get_app_state
        app.dependency_overrides[get_browser_manager] = mock_get_browser_manager
        app.dependency_overrides[get_logger] = mock_get_logger
        app.dependency_overrides[check_rate_limit] = mock_check_rate_limit
        
        try:
            with patch('app.api.routes.screenshot.ScreenshotService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                
                # Mock cleanup
                mock_service.cleanup_screenshots.return_value = 2
                
                # Mock the regeneration response directly in the service
                mock_service.capture_multi_viewport_screenshots.return_value = MagicMock(
                    successful_screenshots=[MagicMock()],
                    screenshots=[MagicMock()]
                )
                
                response = client.post("/api/v1/screenshots/session/test-session/screenshots/regenerate")
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["success"] is True
                assert data["session_id"] == "test-session"
                
        finally:
            # Clean up dependency overrides
            app.dependency_overrides.clear()
    
    def test_get_screenshot_statistics(self, client):
        """Test getting screenshot statistics."""
        with patch('app.api.routes.screenshot.get_browser_manager', return_value=AsyncMock()):
            with tempfile.TemporaryDirectory() as temp_dir:
                # Mock the settings at the module level where it's imported
                with patch('app.api.routes.screenshot.settings') as mock_settings:
                    mock_settings.temp_storage_path = temp_dir
                    
                    # Create test files
                    screenshots_dir = Path(temp_dir) / "screenshots"
                    screenshots_dir.mkdir(parents=True, exist_ok=True)
                    
                    (screenshots_dir / "test1.jpg").write_bytes(b"x" * 1000)
                    (screenshots_dir / "test2.jpg").write_bytes(b"x" * 2000)
                    
                    response = client.get("/api/v1/screenshots/stats")
                    
                    assert response.status_code == 200
                    data = response.json()
                    
                    assert data["total_files"] == 2
                    assert data["total_size"] == 3000
                    assert "disk_usage" in data
                    assert "oldest_file" in data
                    assert "newest_file" in data
                    assert data["average_file_size"] == 1500


class TestScreenshotRequestValidation:
    """Test screenshot request validation."""
    
    def test_screenshot_request_valid(self):
        """Test valid screenshot request."""
        request = ScreenshotRequest(
            url="https://example.com",
            session_id="test-session",
            viewports=[
                ViewportModel(
                    name="Test",
                    width=1920,
                    height=1080
                )
            ]
        )
        
        assert request.url == "https://example.com"
        assert request.session_id == "test-session"
        assert len(request.viewports) == 1
        assert request.concurrent is True
        assert request.quality == 90
    
    def test_screenshot_request_too_many_viewports(self):
        """Test screenshot request with too many viewports."""
        with pytest.raises(ValueError, match="Maximum 10 viewports allowed"):
            viewports = [
                ViewportModel(name=f"Test{i}", width=800, height=600)
                for i in range(11)  # 11 viewports should fail
            ]
            
            ScreenshotRequest(
                url="https://example.com",
                session_id="test-session",
                viewports=viewports
            )
    
    def test_viewport_model_validation(self):
        """Test viewport model validation."""
        # Valid viewport
        viewport = ViewportModel(
            name="Test",
            width=1920,
            height=1080,
            device_scale_factor=2.0,
            is_mobile=False
        )
        
        assert viewport.width == 1920
        assert viewport.height == 1080
        assert viewport.device_scale_factor == 2.0
        
        # Invalid dimensions should be caught by Pydantic
        with pytest.raises(ValueError):
            ViewportModel(name="Invalid", width=0, height=1080)
        
        with pytest.raises(ValueError):
            ViewportModel(name="Invalid", width=1920, height=0)
    
    def test_viewport_model_scale_factor_validation(self):
        """Test device scale factor validation."""
        # Valid scale factors
        ViewportModel(name="Test", width=800, height=600, device_scale_factor=1.0)
        ViewportModel(name="Test", width=800, height=600, device_scale_factor=2.0)
        ViewportModel(name="Test", width=800, height=600, device_scale_factor=0.5)
        
        # Invalid scale factors
        with pytest.raises(ValueError):
            ViewportModel(name="Test", width=800, height=600, device_scale_factor=0)
        
        with pytest.raises(ValueError):
            ViewportModel(name="Test", width=800, height=600, device_scale_factor=-1)