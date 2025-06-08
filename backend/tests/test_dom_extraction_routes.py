import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
import tempfile
from pathlib import Path
import time
import json

from app.api.routes.dom_extraction import router
from app.models.dom_extraction import (
    DOMExtractionRequest,
    OutputFormat
)
from app.services.dom_extraction_service import (
    DOMExtractionService,
    DOMExtractionResult,
    PageStructure,
    ExtractedElement,
    ExtractedAsset
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
app.include_router(router, prefix="/api/v1/dom")


class TestDOMExtractionRoutes:
    """Test suite for DOM extraction API routes."""
    
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
    
    def test_extract_dom_structure_success(self, client, mock_dependencies):
        """Test successful DOM structure extraction."""
        with patch.multiple(
            'app.api.routes.dom_extraction',
            get_app_state=lambda: mock_dependencies["app_state"],
            get_browser_manager=lambda: mock_dependencies["browser_manager"],
            get_logger=lambda: mock_dependencies["logger"],
            get_request_id=lambda: "test-request-id",
            check_rate_limit=lambda: None
        ):
            with patch('app.api.routes.dom_extraction.DOMExtractionService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                
                # Mock successful extraction result
                mock_result = DOMExtractionResult(
                    url="https://example.com",
                    session_id="test-session",
                    timestamp=time.time(),
                    extraction_time=2.5,
                    page_structure=PageStructure(title="Test Page"),
                    elements=[
                        ExtractedElement(
                            tag_name="div",
                            element_id="test-id",
                            class_names=["test-class"]
                        )
                    ],
                    stylesheets=[],
                    assets=[
                        ExtractedAsset(
                            url="https://example.com/image.jpg",
                            asset_type="image"
                        )
                    ],
                    layout_analysis={"layout_type": "flex"},
                    color_palette=["#ff0000"],
                    font_families=["Arial"],
                    responsive_breakpoints=[768],
                    dom_depth=5,
                    total_elements=1,
                    total_stylesheets=0,
                    total_assets=1,
                    success=True
                )
                
                mock_service.extract_dom_structure.return_value = mock_result
                mock_service.save_extraction_result.return_value = "/path/to/saved/file.json"
                
    def test_extract_dom_structure_failure(self, client, mock_dependencies):
        """Test DOM extraction failure."""
        with patch.multiple(
            'app.api.routes.dom_extraction',
            get_app_state=lambda: mock_dependencies["app_state"],
            get_browser_manager=lambda: mock_dependencies["browser_manager"],
            get_logger=lambda: mock_dependencies["logger"],
            get_request_id=lambda: "test-request-id",
            check_rate_limit=lambda: None
        ):
            with patch('app.api.routes.dom_extraction.DOMExtractionService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                
                # Mock failed extraction
                mock_service.extract_dom_structure.side_effect = Exception("Extraction failed")
                
                request_data = {
                    "url": "https://example.com",
                    "session_id": "test-session",
                    "wait_for_load": True,
                    "include_computed_styles": True,
                    "max_depth": 10,
                    "save_result": False,
                    "output_format": "json"
                }
                
                response = client.post("/api/v1/dom/extract", json=request_data)
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["success"] is False
                assert "Extraction failed" in data["message"]
                assert data["extraction_result"] is None
                assert data["saved_file_path"] is None
    
    def test_get_extraction_status_with_files(self, client, mock_dependencies):
        """Test getting extraction status with existing files."""
        with patch.multiple(
            'app.api.routes.dom_extraction',
            validate_session_id=lambda session_id: session_id,
            get_browser_manager=lambda: mock_dependencies["browser_manager"]
        ):
            with patch('app.api.routes.dom_extraction.DOMExtractionService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                
                # Mock extraction info
                mock_service.get_extraction_info.return_value = {
                    "session_id": "test-session",
                    "extraction_count": 2,
                    "total_size": 12345,
                    "extractions": [
                        {
                            "filename": "test-session_extraction_123.json",
                            "size": 6000,
                            "created": time.time(),
                            "path": "/path/to/file1.json"
                        },
                        {
                            "filename": "test-session_extraction_456.json",
                            "size": 6345,
                            "created": time.time(),
                            "path": "/path/to/file2.json"
                        }
                    ]
                }
                
                response = client.get("/api/v1/dom/session/test-session/status")
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["session_id"] == "test-session"
                assert data["status"] == "available"
                assert data["extraction_info"]["extraction_count"] == 2
                assert data["extraction_info"]["total_size"] == 12345
                assert len(data["extraction_info"]["extractions"]) == 2
    
    def test_get_extraction_status_no_files(self, client, mock_dependencies):
        """Test getting extraction status with no existing files."""
        with patch.multiple(
            'app.api.routes.dom_extraction',
            validate_session_id=lambda session_id: session_id,
            get_browser_manager=lambda: mock_dependencies["browser_manager"]
        ):
            with patch('app.api.routes.dom_extraction.DOMExtractionService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                
                # Mock no extraction files
                mock_service.get_extraction_info.return_value = {
                    "session_id": "test-session",
                    "extraction_count": 0,
                    "total_size": 0,
                    "extractions": []
                }
                
                response = client.get("/api/v1/dom/session/test-session/status")
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["session_id"] == "test-session"
                assert data["status"] == "no_extractions"
                assert data["extraction_info"]["extraction_count"] == 0
    
    def test_analyze_page_complexity_success(self, client, mock_dependencies):
        """Test successful page complexity analysis."""
        with patch.multiple(
            'app.api.routes.dom_extraction',
            get_browser_manager=lambda: mock_dependencies["browser_manager"],
            get_logger=lambda: mock_dependencies["logger"],
            check_rate_limit=lambda: None
        ):
            with patch('app.api.routes.dom_extraction.DOMExtractionService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                
                # Mock successful extraction for complexity analysis
                mock_result = DOMExtractionResult(
                    url="https://example.com",
                    session_id="test-session",
                    timestamp=time.time(),
                    extraction_time=1.5,
                    page_structure=PageStructure(title="Test Page"),
                    elements=[ExtractedElement(tag_name="div")] * 50,
                    stylesheets=[],
                    assets=[],
                    layout_analysis={"layoutType": "grid"},
                    color_palette=["#ff0000"] * 10,
                    font_families=["Arial"],
                    responsive_breakpoints=[768, 1024],
                    dom_depth=8,
                    total_elements=50,
                    total_stylesheets=2,
                    total_assets=15,
                    success=True
                )
                
                # Mock complexity analysis
                mock_complexity = {
                    "overall_score": 75.5,
                    "dom_complexity": 80,
                    "style_complexity": 70,
                    "asset_complexity": 60,
                    "layout_complexity": 85,
                    "recommendations": [
                        "High DOM complexity - consider element reduction",
                        "Large color palette - consider color consolidation"
                    ]
                }
                
                mock_service.extract_dom_structure.return_value = mock_result
                mock_service.analyze_page_complexity.return_value = mock_complexity
                
                request_data = {
                    "url": "https://example.com",
                    "session_id": "test-session",
                    "wait_for_load": True
                }
                
                response = client.post("/api/v1/dom/analyze-complexity", json=request_data)
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["success"] is True
                assert data["complexity_analysis"]["overall_score"] == 75.5
                assert len(data["complexity_analysis"]["recommendations"]) == 2
                assert data["extraction_metrics"]["total_elements"] == 50
                assert data["extraction_metrics"]["extraction_time"] == 1.5
    
    def test_cleanup_session_extractions(self, client, mock_dependencies):
        """Test cleaning up extraction files for a session."""
        with patch.multiple(
            'app.api.routes.dom_extraction',
            validate_session_id=lambda session_id: session_id,
            get_browser_manager=lambda: mock_dependencies["browser_manager"],
            get_logger=lambda: mock_dependencies["logger"]
        ):
            with patch('app.api.routes.dom_extraction.DOMExtractionService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                
                # Mock extraction info before cleanup
                mock_service.get_extraction_info.return_value = {
                    "session_id": "test-session",
                    "extraction_count": 3,
                    "total_size": 15000,
                    "extractions": []
                }
                
                # Mock cleanup
                mock_service.cleanup_extractions.return_value = 3
                
                response = client.delete("/api/v1/dom/session/test-session/extractions")
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["cleaned_count"] == 3
                assert data["total_freed_bytes"] == 15000
                assert data["session_id"] == "test-session"
    
    def test_cleanup_old_extractions(self, client, mock_dependencies):
        """Test cleaning up old extraction files."""
        with patch.multiple(
            'app.api.routes.dom_extraction',
            get_browser_manager=lambda: mock_dependencies["browser_manager"],
            get_logger=lambda: mock_dependencies["logger"]
        ):
            with patch('app.api.routes.dom_extraction.DOMExtractionService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                
                # Mock cleanup
                mock_service.cleanup_extractions.return_value = 5
                
                with tempfile.TemporaryDirectory() as temp_dir:
                    with patch('app.api.routes.dom_extraction.settings') as mock_settings:
                        mock_settings.temp_storage_path = temp_dir
                        
                        # Create some test files to calculate sizes
                        extractions_dir = Path(temp_dir) / "extractions"
                        extractions_dir.mkdir(parents=True, exist_ok=True)
                        
                        for i in range(3):
                            (extractions_dir / f"test_{i}.json").write_text('{"test": "data"}')
                        
                        response = client.delete("/api/v1/dom/cleanup?older_than_hours=24")
                        
                        assert response.status_code == 200
                        data = response.json()
                        
                        assert data["cleaned_count"] == 5
                        assert data["session_id"] is None
    
    def test_regenerate_extraction_success(self, client, mock_dependencies):
        """Test successful extraction regeneration."""
        with patch.multiple(
            'app.api.routes.dom_extraction',
            validate_session_id=lambda session_id: session_id,
            get_app_state=lambda: mock_dependencies["app_state"],
            get_browser_manager=lambda: mock_dependencies["browser_manager"],
            get_logger=lambda: mock_dependencies["logger"],
            check_rate_limit=lambda: None
        ):
            with patch('app.api.routes.dom_extraction.DOMExtractionService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                
                # Mock successful regeneration
                mock_result = DOMExtractionResult(
                    url="https://example.com",
                    session_id="test-session",
                    timestamp=time.time(),
                    extraction_time=3.0,
                    page_structure=PageStructure(title="Regenerated Page"),
                    elements=[ExtractedElement(tag_name="div")],
                    stylesheets=[],
                    assets=[],
                    layout_analysis={},
                    color_palette=[],
                    font_families=[],
                    responsive_breakpoints=[],
                    dom_depth=3,
                    total_elements=1,
                    total_stylesheets=0,
                    total_assets=0,
                    success=True
                )
                
                mock_service.cleanup_extractions.return_value = 2
                mock_service.extract_dom_structure.return_value = mock_result
                mock_service.save_extraction_result.return_value = "/path/to/regenerated.json"
                
                request_data = {
                    "url": "https://example.com",
                    "wait_for_load": True,
                    "include_computed_styles": True,
                    "max_depth": 10,
                    "save_result": True,
                    "output_format": "json"
                }
                
                response = client.post("/api/v1/dom/session/test-session/regenerate", json=request_data)
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["success"] is True
                assert "Regenerated extraction" in data["message"]
                assert data["extraction_result"] is not None
                assert data["saved_file_path"] == "/path/to/regenerated.json"
    
    def test_regenerate_extraction_no_session(self, client, mock_dependencies):
        """Test extraction regeneration with invalid session."""
        mock_dependencies["app_state"].get_session.return_value = None
        
        with patch.multiple(
            'app.api.routes.dom_extraction',
            validate_session_id=lambda session_id: session_id,
            get_app_state=lambda: mock_dependencies["app_state"],
            get_browser_manager=lambda: mock_dependencies["browser_manager"],
            get_logger=lambda: mock_dependencies["logger"],
            check_rate_limit=lambda: None
        ):
            request_data = {
                "url": "https://example.com",
                "wait_for_load": True,
                "include_computed_styles": True,
                "max_depth": 10,
                "save_result": True,
                "output_format": "json"
            }
            
            response = client.post("/api/v1/dom/session/invalid-session/regenerate", json=request_data)
            
            assert response.status_code == 404
            assert "Session invalid-session not found" in response.json()["detail"]
    
    def test_get_extraction_statistics(self, client, mock_dependencies):
        """Test getting extraction statistics."""
        with patch('app.api.routes.dom_extraction.get_browser_manager', return_value=mock_dependencies["browser_manager"]):
            with tempfile.TemporaryDirectory() as temp_dir:
                with patch('app.api.routes.dom_extraction.settings') as mock_settings:
                    mock_settings.temp_storage_path = temp_dir
                    
                    # Create test extraction files
                    extractions_dir = Path(temp_dir) / "extractions"
                    extractions_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Create files with known content
                    test_data = {"test": "data" * 100}  # Make it larger
                    for i in range(3):
                        (extractions_dir / f"test_{i}.json").write_text(json.dumps(test_data))
                    
                    response = client.get("/api/v1/dom/stats")
                    
                    assert response.status_code == 200
                    data = response.json()
                    
                    assert data["total_files"] == 3
                    assert data["total_size"] > 0
                    assert "disk_usage" in data
                    assert "average_file_size" in data
                    assert "oldest_file" in data
                    assert "newest_file" in data
    
    def test_get_extraction_statistics_no_files(self, client, mock_dependencies):
        """Test getting extraction statistics with no files."""
        with patch('app.api.routes.dom_extraction.get_browser_manager', return_value=mock_dependencies["browser_manager"]):
            with tempfile.TemporaryDirectory() as temp_dir:
                with patch('app.api.routes.dom_extraction.settings') as mock_settings:
                    mock_settings.temp_storage_path = temp_dir
                    
                    # Don't create extractions directory
                    response = client.get("/api/v1/dom/stats")
                    
                    assert response.status_code == 200
                    data = response.json()
                    
                    assert data["total_files"] == 0
                    assert data["total_size"] == 0
                    assert data["disk_usage"] == "0 bytes"
                    assert data["average_file_size"] == 0
                    assert data["oldest_file"] is None
                    assert data["newest_file"] is None
    
    def test_invalid_request_data(self, client, mock_dependencies):
        """Test API with invalid request data."""
        with patch.multiple(
            'app.api.routes.dom_extraction',
            get_app_state=lambda: mock_dependencies["app_state"],
            get_browser_manager=lambda: mock_dependencies["browser_manager"],
            get_logger=lambda: mock_dependencies["logger"],
            get_request_id=lambda: "test-request-id",
            check_rate_limit=lambda: None
        ):
            # Test missing required fields
            invalid_requests = [
                {},  # Empty request
                {"url": "https://example.com"},  # Missing session_id
                {"session_id": "test-session"},  # Missing url
                {"url": "invalid-url", "session_id": "test-session"},  # Invalid URL
                {"url": "https://example.com", "session_id": ""},  # Empty session_id
                {"url": "https://example.com", "session_id": "test", "max_depth": 25},  # Invalid max_depth
            ]
            
            for invalid_request in invalid_requests:
                response = client.post("/api/v1/dom/extract", json=invalid_request)
                assert response.status_code == 422  # Validation error
    
    def test_request_validation(self, client):
        """Test request validation for DOM extraction."""
        # Test valid request
        valid_request = {
            "url": "https://example.com",
            "session_id": "test-session",
            "wait_for_load": True,
            "include_computed_styles": True,
            "max_depth": 10,
            "save_result": True,
            "output_format": "json"
        }
        
        # This will fail at the service level, but should pass validation
        with patch.multiple(
            'app.api.routes.dom_extraction',
            get_app_state=lambda: MagicMock(),
            get_browser_manager=lambda: AsyncMock(),
            get_logger=lambda: MagicMock(),
            get_request_id=lambda: "test-request-id",
            check_rate_limit=lambda: None
        ):
            with patch('app.api.routes.dom_extraction.DOMExtractionService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                mock_service.extract_dom_structure.side_effect = Exception("Service error")
                
                response = client.post("/api/v1/dom/extract", json=valid_request)
                # Should pass validation but fail at service level
                assert response.status_code == 200
                assert not response.json()["success"]


@pytest.mark.integration
class TestDOMExtractionAPIIntegration:
    """Integration tests for DOM extraction API."""
    
    @pytest.fixture
    def app_with_dependencies(self):
        """Create app with real dependencies for integration testing."""
        from app.main import app
        return app
    
    @pytest.mark.asyncio
    async def test_full_extraction_flow(self, app_with_dependencies):
        """Test the complete DOM extraction flow with real services."""
        # This would require actual browser setup and is more of an e2e test
        # For now, we'll skip this as it requires complex setup
        pytest.skip("Integration test requires full application setup")
    
    def test_api_documentation_generation(self):
        """Test that the API routes generate proper OpenAPI documentation."""
        from fastapi.openapi.utils import get_openapi
        
        openapi_schema = get_openapi(
            title="DOM Extraction API",
            version="1.0.0",
            description="DOM extraction endpoints",
            routes=router.routes,
        )
        
        # Check that our endpoints are documented
        paths = openapi_schema["paths"]
        
        assert "/extract" in paths
        assert "/session/{session_id}/status" in paths
        assert "/analyze-complexity" in paths
        assert "/cleanup" in paths
        assert "/session/{session_id}/extractions" in paths
        assert "/session/{session_id}/regenerate" in paths
        assert "/stats" in paths
        
        # Check that POST /extract has proper request/response schemas
        extract_endpoint = paths["/extract"]["post"]
        assert "requestBody" in extract_endpoint
        assert "responses" in extract_endpoint
        assert "200" in extract_endpoint["responses"]

        # Verify request schema
        request_data = {
            "url": "https://example.com",
            "session_id": "test-session",
            "wait_for_load": True,
            "include_computed_styles": True,
            "max_depth": 10,
            "save_result": True,
            "output_format": "json"
        }

        response = client.post("/api/v1/dom/extract", json=request_data)

        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["session_id"] == "test-session"
        assert data["extraction_result"] is not None
        assert data["saved_file_path"] == "/path/to/saved/file.json"
        
        # Check extraction result details
        result_data = data["extraction_result"]
        assert result_data["url"] == "https://example.com"
        assert result_data["total_elements"] == 1
        assert result_data["total_assets"] == 1
        assert result_data["success"] is True
    
    def test_extract_dom_structure_failure(self, client, mock_dependencies):
        """Test DOM extraction failure."""
        with patch.multiple(
            'app.api.routes.dom_extraction',
            get_app_state=lambda: mock_dependencies["app_state"],
            get_browser_manager=lambda: mock_dependencies["browser_manager"],
            get_logger=lambda: mock_dependencies["logger"],
            get_request_id=lambda: "test-request-id",
            check_rate_limit=lambda: None
        ):
            with patch('app.api.routes.dom_extraction.DOMExtractionService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                
                # Mock failed extraction
                mock_service.extract_dom_structure.side_effect = Exception("Extraction failed")
                
                request_data = {
                    "url": "https://example.com",
                    "session_id": "test-session",
                    "wait_for_load": True,
                    "include_computed_styles": True,
                    "max_depth": 10,
                    "save_result": False,
                    "output_format": "json"
                }
                
                response = client.post("/api/v1/dom/extract", json=request_data)
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["success"] is False
                assert "Extraction failed" in data["message"]
                assert data["extraction_result"] is None
                assert data["saved_file_path"] is None