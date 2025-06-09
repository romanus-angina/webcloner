import pytest
import asyncio
import time
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
import json

from app.main import app
from app.models.responses import CloneStatus
from app.dependencies import get_browser_manager

@pytest.fixture(autouse=True)
async def cleanup_browsers():
    """Cleanup browsers between tests to avoid connection issues."""
    yield  # Run the test
    
    # Cleanup after each test
    try:
        browser_manager = get_browser_manager()
        if browser_manager._is_initialized:
            await browser_manager.cleanup()
    except Exception as e:
        print(f"Browser cleanup warning: {e}")

@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_clone_request():
    """Sample clone request payload."""
    return {
        "url": "https://example.com",
        "quality": "balanced",
        "include_images": True,
        "include_styling": True,
        "max_depth": 1,
        "custom_instructions": "Make it modern and clean"
    }


@pytest.mark.integration
@pytest.mark.api
class TestCloneAPIEndpoints:
    """Integration tests for the clone API endpoints."""
    
    def test_clone_post_endpoint_success(self, client, sample_clone_request):
        """Test successful clone request initiation."""
        response = client.post("/api/v1/clone", json=sample_clone_request)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "session_id" in data
        assert data["status"] == "pending"
        assert "created_at" in data
        assert "updated_at" in data
        assert len(data["progress"]) >= 1
        
        # Verify progress step
        first_step = data["progress"][0]
        assert first_step["step_name"] == "Initialization"
        assert first_step["status"] == "pending"
        assert first_step["progress_percentage"] == 0.0
        
        # Don't return the session_id (was causing pytest warning)
    
    def test_clone_post_invalid_url(self, client):
        """Test clone request with invalid URL."""
        invalid_request = {
            "url": "not-a-valid-url",
            "quality": "balanced"
        }
        
        response = client.post("/api/v1/clone", json=invalid_request)
        assert response.status_code == 422  # Validation error
    
    def test_clone_post_localhost_url_blocked(self, client):
        """Test that localhost URLs are blocked for security."""
        localhost_request = {
            "url": "http://localhost:3000",
            "quality": "fast"
        }
        
        response = client.post("/api/v1/clone", json=localhost_request)
        assert response.status_code == 422
        assert "Local URLs are not allowed" in response.text
    
    def test_clone_get_status_nonexistent_session(self, client):
        """Test getting status for non-existent session."""
        response = client.get("/api/v1/clone/nonexistent-session-id")
        assert response.status_code == 404
    
    def test_clone_get_status_valid_session(self, client, sample_clone_request):
        """Test getting status for valid session."""
        # First create a session
        post_response = client.post("/api/v1/clone", json=sample_clone_request)
        session_id = post_response.json()["session_id"]
        
        # Then get its status
        response = client.get(f"/api/v1/clone/{session_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["session_id"] == session_id
        assert "status" in data
        assert "progress" in data
        assert "created_at" in data
    
    def test_clone_workflow_status_progression(self, client, sample_clone_request):
        """Test that clone status progresses through expected states."""
        # Start clone
        post_response = client.post("/api/v1/clone", json=sample_clone_request)
        session_id = post_response.json()["session_id"]
        
        # Check initial status
        response = client.get(f"/api/v1/clone/{session_id}")
        initial_data = response.json()
        assert initial_data["status"] == "pending"
        
        # Wait a bit for background processing to start
        time.sleep(2)
        
        # Check status progression
        response = client.get(f"/api/v1/clone/{session_id}")
        updated_data = response.json()
        
        # Status should have progressed
        valid_statuses = ["pending", "analyzing", "generating", "completed", "failed"]
        assert updated_data["status"] in valid_statuses
        
        # If still processing, updated_at should have changed
        if updated_data["status"] in ["analyzing", "generating"]:
            assert updated_data["updated_at"] != initial_data["updated_at"]
    
    def test_sessions_list_endpoint(self, client, sample_clone_request):
        """Test listing all sessions."""
        # Create a session first
        client.post("/api/v1/clone", json=sample_clone_request)
        
        # List sessions
        response = client.get("/api/v1/sessions")
        assert response.status_code == 200
        
        data = response.json()
        assert "sessions" in data
        assert "total_count" in data
        assert "page" in data
        assert "page_size" in data
        assert data["total_count"] >= 1
        assert len(data["sessions"]) >= 1
    
    def test_sessions_list_pagination(self, client, sample_clone_request):
        """Test session list pagination."""
        response = client.get("/api/v1/sessions?page=1&page_size=5")
        assert response.status_code == 200
        
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5
    
    def test_sessions_list_status_filter(self, client, sample_clone_request):
        """Test filtering sessions by status."""
        response = client.get("/api/v1/sessions?status=pending")
        assert response.status_code == 200
        
        data = response.json()
        # All returned sessions should have pending status
        for session in data["sessions"]:
            assert session["status"] == "pending"
    
    def test_delete_session_endpoint(self, client, sample_clone_request):
        """Test deleting a session."""
        # Create session
        post_response = client.post("/api/v1/clone", json=sample_clone_request)
        session_id = post_response.json()["session_id"]
        
        # Delete it
        response = client.delete(f"/api/v1/clone/{session_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert session_id in data["message"]
        assert "deleted_at" in data
        
        # Verify it's gone
        get_response = client.get(f"/api/v1/clone/{session_id}")
        assert get_response.status_code == 404
    
    def test_delete_nonexistent_session(self, client):
        """Test deleting non-existent session."""
        response = client.delete("/api/v1/clone/nonexistent-session")
        assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.slow
class TestCloneWorkflowEndToEnd:
    """End-to-end tests for the complete clone workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_clone_workflow_with_mocked_llm(self, client):
        """Test complete workflow with mocked LLM to avoid API costs."""
        
        # Mock the LLM service to return fake results
        mock_llm_result = {
            "html_content": """<!DOCTYPE html>
<html lang="en">
<head>
    <title>Generated Website</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
        .navbar { background: #333; color: white; padding: 1rem; }
        .button { background: #007bff; color: white; padding: 10px 20px; border: none; }
    </style>
</head>
<body>
    <nav class="navbar">
        <a href="/">Home</a>
        <a href="/about">About</a>
    </nav>
    <main>
        <h1>Welcome</h1>
        <button class="button">Get Started</button>
    </main>
</body>
</html>""",
            "css_content": None,
            "similarity_score": 87.5,
            "generation_time": 2.1,
            "tokens_used": 1234,
            "components_replicated": {"navbar": 1, "button": 1},
            "quality_level": "balanced",
            "model_used": "claude-3-5-sonnet-20241022"
        }
        
        with patch('app.services.llm_service.llm_service.generate_html_from_components') as mock_llm:
            mock_llm.return_value = mock_llm_result
            
            # Start clone
            clone_request = {
                "url": "https://example.com",
                "quality": "balanced",
                "include_styling": True
            }
            
            response = client.post("/api/v1/clone", json=clone_request)
            assert response.status_code == 200
            
            session_id = response.json()["session_id"]
            
            # Wait for background processing
            max_wait = 30  # seconds
            start_time = time.time()
            final_status = None
            
            while time.time() - start_time < max_wait:
                response = client.get(f"/api/v1/clone/{session_id}")
                data = response.json()
                status = data["status"]
                
                if status in ["completed", "failed"]:
                    final_status = status
                    break
                
                await asyncio.sleep(1)
            
            # Verify completion
            assert final_status == "completed", f"Expected completed, got {final_status}"
            
            # Get final result
            response = client.get(f"/api/v1/clone/{session_id}")
            final_data = response.json()
            
            # Verify result structure
            assert final_data["status"] == "completed"
            assert "result" in final_data
            
            result = final_data["result"]
            assert "html_content" in result
            assert "similarity_score" in result
            assert "generation_time" in result
            assert "tokens_used" in result
            
            # Verify HTML content
            assert "<!DOCTYPE html>" in result["html_content"]
            assert "<nav class=\"navbar\">" in result["html_content"]
            assert result["similarity_score"] == 87.5
            
            # Verify component analysis
            assert "component_analysis" in final_data
            comp_analysis = final_data["component_analysis"]
            assert "total_components" in comp_analysis
            assert "components_replicated" in comp_analysis
    
    def test_clone_workflow_with_invalid_url_processing(self, client):
        """Test workflow handles processing errors gracefully."""
        
        # Use a data URL that will cause processing issues
        problematic_request = {
            "url": "data:text/html,<html><body>Invalid content that might break processing</body></html>",
            "quality": "fast"
        }
        
        response = client.post("/api/v1/clone", json=problematic_request)
        assert response.status_code == 200
        
        session_id = response.json()["session_id"]
        
        # Wait for processing
        time.sleep(5)
        
        # Check final status
        response = client.get(f"/api/v1/clone/{session_id}")
        data = response.json()
        
        # Should either complete or fail gracefully
        assert data["status"] in ["completed", "failed"]
        
        if data["status"] == "failed":
            assert "error_message" in data
            assert data["error_message"] is not None


@pytest.mark.integration
@pytest.mark.api
class TestCloneAPIErrorHandling:
    """Test error handling in clone API endpoints."""
    
    def test_rate_limiting(self, client, sample_clone_request):
        """Test that rate limiting works."""
        # Make multiple requests quickly
        responses = []
        for i in range(15):  # More than rate limit
            response = client.post("/api/v1/clone", json=sample_clone_request)
            responses.append(response)
        
        # Should get some rate limit errors
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes  # Too Many Requests
    
    def test_malformed_request_body(self, client):
        """Test handling of malformed request body."""
        response = client.post("/api/v1/clone", json={"invalid": "data"})
        assert response.status_code == 422  # Validation error
    
    def test_missing_required_fields(self, client):
        """Test handling of missing required fields."""
        response = client.post("/api/v1/clone", json={})
        assert response.status_code == 422
        
        error_detail = response.json()["detail"]
        # Should mention missing URL field
        assert any("url" in str(error).lower() for error in error_detail)


# Test runner functions
def test_all_api_endpoints():
    """Run all API endpoint tests."""
    pytest.main([
        "tests/test_api_endpoints.py::TestCloneAPIEndpoints",
        "-v"
    ])

def test_end_to_end_workflow():
    """Run end-to-end workflow tests."""
    pytest.main([
        "tests/test_api_endpoints.py::TestCloneWorkflowEndToEnd::test_complete_clone_workflow_with_mocked_llm",
        "-v", "-s"
    ])

def test_error_handling():
    """Run error handling tests."""
    pytest.main([
        "tests/test_api_endpoints.py::TestCloneAPIErrorHandling",
        "-v"
    ])