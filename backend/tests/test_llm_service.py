import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
from dataclasses import asdict

from app.services.llm_service import LLMService
from app.services.dom_extraction_service import DOMExtractionResult, ExtractedElement, PageStructure
from app.services.component_detector import ComponentDetector
from app.models.components import ComponentDetectionResult, DetectedComponent, ComponentType
from app.core.exceptions import LLMError, ConfigurationError


@pytest.fixture
def mock_component_result():
    """Create a mock component detection result."""
    components = [
        DetectedComponent(
            component_type=ComponentType.NAVBAR,
            elements=[{"tag_name": "nav", "class_names": ["navbar"]}],
            label="Main Navigation",
            metadata={"link_count": 3, "has_logo": True}
        ),
        DetectedComponent(
            component_type=ComponentType.BUTTON,
            elements=[{"tag_name": "button", "text_content": "Get Started"}],
            label="Get Started"
        )
    ]
    
    return ComponentDetectionResult(
        session_id="test-session",
        components=components,
        total_components=2,
        detection_time_seconds=0.5
    )


@pytest.fixture
def mock_dom_result():
    """Create a mock DOM extraction result."""
    return DOMExtractionResult(
        url="https://example.com",
        session_id="test-session",
        timestamp=time.time(),
        extraction_time=2.0,
        page_structure=PageStructure(
            title="Test Website",
            meta_description="A test website"
        ),
        elements=[],
        stylesheets=[],
        assets=[],
        layout_analysis={},
        color_palette=["#ffffff", "#000000", "#007bff"],
        font_families=["Arial", "Helvetica"],
        responsive_breakpoints=[768, 1024],
        total_elements=25,
        success=True
    )


@pytest.mark.unit
class TestLLMService:
    """Unit tests for LLM Service."""
    
    def test_initialization_without_api_key(self):
        """Test that service fails without API key."""
        with patch('app.services.llm_service.settings') as mock_settings:
            mock_settings.anthropic_api_key = None
            
            with pytest.raises(ConfigurationError, match="Anthropic API key not configured"):
                LLMService()
    
    def test_build_component_summary(self, mock_component_result):
        """Test component summary generation."""
        with patch('app.services.llm_service.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            
            service = LLMService()
            summary = service._build_component_summary(mock_component_result)
            
            assert "Component breakdown: 1 navbar(s), 1 button(s)" in summary
            assert "NAVBAR: Main Navigation" in summary
            assert "BUTTON: Get Started" in summary
            assert "link count: 3" in summary
    
    def test_build_component_summary_empty(self):
        """Test component summary with no components."""
        with patch('app.services.llm_service.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            
            empty_result = ComponentDetectionResult(
                session_id="test",
                components=[],
                total_components=0,
                detection_time_seconds=0.1
            )
            
            service = LLMService()
            summary = service._build_component_summary(empty_result)
            
            assert "No specific components detected" in summary
    
    def test_parse_llm_response_with_html_block(self):
        """Test parsing LLM response with HTML block."""
        with patch('app.services.llm_service.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            
            response_text = """
Here's the generated website:

```html
<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><h1>Hello World</h1></body>
</html>
```

This creates a simple webpage.
            """
            
            service = LLMService()
            html, css = service._parse_llm_response(response_text)
            
            assert "<!DOCTYPE html>" in html
            assert "<h1>Hello World</h1>" in html
            assert css is None
    
    def test_parse_llm_response_with_css_block(self):
        """Test parsing LLM response with separate CSS block."""
        with patch('app.services.llm_service.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            
            response_text = """
```html
<html><body>Content</body></html>
```

```css
body { margin: 0; }
.navbar { background: blue; }
```
            """
            
            service = LLMService()
            html, css = service._parse_llm_response(response_text)
            
            assert "<html><body>Content</body></html>" in html
            assert "body { margin: 0; }" in css
            assert ".navbar { background: blue; }" in css
    
    def test_calculate_similarity_score(self, mock_component_result):
        """Test similarity score calculation."""
        with patch('app.services.llm_service.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            
            service = LLMService()
            
            # HTML with navbar and button
            html_with_components = "<nav class='navbar'></nav><button>Click me</button>"
            score = service._calculate_similarity_score(mock_component_result, html_with_components)
            
            assert 90 <= score <= 100  # Should be high since both components present
            
            # HTML without components
            html_without_components = "<div>Just some text</div>"
            score = service._calculate_similarity_score(mock_component_result, html_without_components)
            
            assert 60 <= score <= 80  # Should be lower
    
    def test_count_replicated_components(self, mock_component_result):
        """Test component replication counting."""
        with patch('app.services.llm_service.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            
            service = LLMService()
            
            html = "<nav class='navbar'></nav><button>Submit</button><button>Cancel</button>"
            replicated = service._count_replicated_components(mock_component_result, html)
            
            assert replicated["navbar"] == 1
            assert replicated["button"] == 1  # Counts unique presence, not quantity
    
    def test_get_quality_instructions(self):
        """Test quality-specific instructions."""
        with patch('app.services.llm_service.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            
            service = LLMService()
            
            fast_instructions = service._get_quality_instructions("fast")
            assert "FAST" in fast_instructions
            assert "basic structure" in fast_instructions.lower()
            
            high_instructions = service._get_quality_instructions("high")
            assert "HIGH" in high_instructions
            assert "pixel-perfect" in high_instructions.lower()
    
    @patch('app.services.llm_service.anthropic')
    async def test_generate_html_success(self, mock_anthropic, mock_component_result, mock_dom_result):
        """Test successful HTML generation."""
        with patch('app.services.llm_service.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            
            # Mock Anthropic response
            mock_response = Mock()
            mock_response.content = [Mock(text="""
```html
<!DOCTYPE html>
<html>
<head><title>Generated Site</title></head>
<body>
    <nav class="navbar">Navigation</nav>
    <button>Get Started</button>
</body>
</html>
```
            """)]
            mock_response.usage = Mock(input_tokens=100, output_tokens=200)
            
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client
            
            service = LLMService()
            result = await service.generate_html_from_components(
                component_result=mock_component_result,
                dom_result=mock_dom_result,
                original_url="https://example.com"
            )
            
            assert result["html_content"]
            assert "<!DOCTYPE html>" in result["html_content"]
            assert "<nav class=\"navbar\">" in result["html_content"]
            assert result["tokens_used"] == 300
            assert result["similarity_score"] > 80
            assert result["model_used"] == "claude-3-5-sonnet-20241022"
    
    @patch('app.services.llm_service.anthropic')
    async def test_generate_html_api_failure(self, mock_anthropic, mock_component_result, mock_dom_result):
        """Test LLM API failure handling."""
        with patch('app.services.llm_service.settings') as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            
            mock_client = Mock()
            mock_client.messages.create.side_effect = Exception("API Error")
            mock_anthropic.Anthropic.return_value = mock_client
            
            service = LLMService()
            
            with pytest.raises(LLMError, match="HTML generation failed"):
                await service.generate_html_from_components(
                    component_result=mock_component_result,
                    dom_result=mock_dom_result,
                    original_url="https://example.com"
                )


# Integration test (optional - can be run separately)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_llm_service_integration():
    """
    Integration test for LLM service.
    Only runs if ANTHROPIC_API_KEY is set in environment or .env file.
    """
    import os
    
    # Load .env file if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # dotenv not available, that's ok
    
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set - skipping integration test")
    
    # Create real component result
    components = [
        DetectedComponent(
            component_type=ComponentType.NAVBAR,
            elements=[{"tag_name": "nav"}],
            label="Navigation"
        )
    ]
    
    component_result = ComponentDetectionResult(
        session_id="integration-test",
        components=components,
        total_components=1,
        detection_time_seconds=0.1
    )
    
    # Create real DOM result
    dom_result = DOMExtractionResult(
        url="https://example.com",
        session_id="integration-test",
        timestamp=time.time(),
        extraction_time=1.0,
        page_structure=PageStructure(title="Test Site"),
        elements=[], stylesheets=[], assets=[],
        layout_analysis={}, color_palette=[], font_families=[],
        responsive_breakpoints=[], total_elements=10, success=True
    )
    
    service = LLMService()
    result = await service.generate_html_from_components(
        component_result, dom_result, "https://example.com", "fast"
    )
    
    # Basic assertions
    assert result["html_content"]
    assert result["tokens_used"] > 0
    assert 0 <= result["similarity_score"] <= 100