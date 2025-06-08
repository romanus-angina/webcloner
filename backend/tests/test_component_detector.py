import pytest
import time
from dataclasses import asdict

from app.services.browser_manager import BrowserManager
from app.services.dom_extraction_service import DOMExtractionService, DOMExtractionResult, ExtractedElement, PageStructure
from app.services.component_detector import ComponentDetector
from app.models.components import ComponentType


@pytest.fixture
def mock_dom_result_factory():
    """Factory to create mock DOMExtractionResult objects for unit tests."""
    def _factory(elements: list[ExtractedElement]):
        return DOMExtractionResult(
            url="https://example.com",
            session_id="test-session",
            timestamp=time.time(),
            extraction_time=1.0,
            page_structure=PageStructure(title="Test Page"),
            elements=elements,
            stylesheets=[],
            assets=[],
            layout_analysis={},
            color_palette=[],
            font_families=[],
            responsive_breakpoints=[],
            success=True
        )
    return _factory

class TestComponentDetector:
    """Unit tests for the ComponentDetector service."""

    def test_initialization_requires_successful_dom_result(self):
        """Verify that the detector raises an error with a failed DOM result."""
        failed_dom = DOMExtractionResult(
            url="", session_id="", timestamp=0, extraction_time=0,
            page_structure=PageStructure(), elements=[], stylesheets=[], assets=[],
            layout_analysis={}, color_palette=[], font_families=[], responsive_breakpoints=[],
            success=False
        )
        with pytest.raises(ValueError, match="A successful DOMExtractionResult is required"):
            ComponentDetector(failed_dom)

    def test_detect_no_components(self, mock_dom_result_factory):
        """Test with a DOM that has no detectable components."""
        elements = [ExtractedElement(tag_name='div', text_content='Just a div')]
        dom_result = mock_dom_result_factory(elements)
        
        detector = ComponentDetector(dom_result)
        result = detector.detect_components()
        
        assert result.total_components == 0
        assert len(result.components) == 0

    def test_detect_simple_button(self, mock_dom_result_factory):
        """Test detection of a standard <button> element."""
        button_element = ExtractedElement(
            tag_name='button',
            text_content='Click Me',
            xpath='/html/body/button[1]'
        )
        dom_result = mock_dom_result_factory([button_element])
        
        detector = ComponentDetector(dom_result)
        result = detector.detect_components()
        
        assert result.total_components == 1
        component = result.components[0]
        assert component.component_type == ComponentType.BUTTON
        assert component.label == 'Click Me'
        assert len(component.elements) == 1
        assert component.elements[0].tag_name == 'button'

    def test_detect_link_as_button(self, mock_dom_result_factory):
        """Test detection of an <a> tag styled as a button."""
        link_button = ExtractedElement(
            tag_name='a',
            text_content='Learn More',
            attributes={'role': 'button', 'href': '#'},
            class_names=['btn', 'btn-primary'],
            xpath='/html/body/a[1]'
        )
        dom_result = mock_dom_result_factory([link_button])
        
        detector = ComponentDetector(dom_result)
        result = detector.detect_components()
        
        assert result.total_components == 1
        component = result.components[0]
        assert component.component_type == ComponentType.BUTTON
        assert component.label == 'Learn More'

    def test_detect_input_field(self, mock_dom_result_factory):
        """Test detection of a text input field."""
        input_element = ExtractedElement(
            tag_name='input',
            attributes={'type': 'text', 'placeholder': 'Enter your name'},
            xpath='/html/body/input[1]'
        )
        dom_result = mock_dom_result_factory([input_element])
        
        detector = ComponentDetector(dom_result)
        result = detector.detect_components()
        
        assert result.total_components == 1
        component = result.components[0]
        assert component.component_type == ComponentType.INPUT
        assert component.label == 'Enter your name'

    def test_detect_card_component(self, mock_dom_result_factory):
        """Test detection of a card-like div."""
        card_element = ExtractedElement(
            tag_name='div',
            class_names=['card'],
            computed_styles={
                'box-shadow': '0 4px 8px rgba(0,0,0,0.1)',
                'padding': '16px'
            },
            children_count=3, # Cards usually have multiple children
            xpath='/html/body/div[1]'
        )
        dom_result = mock_dom_result_factory([card_element])
        
        detector = ComponentDetector(dom_result)
        result = detector.detect_components()
        
        assert result.total_components == 1
        component = result.components[0]
        assert component.component_type == ComponentType.CARD
        assert len(component.elements) == 1
        assert component.elements[0].class_names[0] == 'card'

    def test_detection_of_multiple_components(self, mock_dom_result_factory):
        """Test that multiple, distinct components are detected correctly."""
        elements = [
            ExtractedElement(tag_name='button', text_content='Submit', xpath='/form/button'),
            ExtractedElement(tag_name='input', attributes={'type': 'email'}, xpath='/form/input'),
            ExtractedElement(
                tag_name='div',
                computed_styles={'border-width': '1px', 'padding': '10px'},
                children_count=2,
                xpath='/body/div'
            )
        ]
        dom_result = mock_dom_result_factory(elements)
        detector = ComponentDetector(dom_result)
        result = detector.detect_components()
        
        assert result.total_components == 3
        
        component_types = sorted([c.component_type.value for c in result.components])
        assert component_types == ['button', 'card', 'input']


@pytest.mark.integration
@pytest.mark.asyncio
async def test_component_detection_integration_flow():
    """
    Integration test: DOM Extraction -> Component Detection.
    Verifies that the two services work together correctly using a real browser instance.
    """
    # 1. Define a self-contained HTML structure to test against
    test_html_content = """
    <html>
        <head><title>Integration Test</title></head>
        <body>
            <h1>Component Test Page</h1>
            <section>
                <div class="card" style="box-shadow: rgba(0, 0, 0, 0.1) 0px 4px 8px; padding: 15px; border: 1px solid rgb(221, 221, 221);">
                    <h2>Test Card</h2>
                    <p>This is a card component.</p>
                    <button class="btn">Click here</button>
                </div>
            </section>
            <form>
                <input type="text" placeholder="Your name" />
                <a href="#" role="button" class="button-link">Submit Link</a>
            </form>
        </body>
    </html>
    """
    # Use a data URL to avoid network requests
    test_url = f"data:text/html,{test_html_content}"
    
    # 2. Initialize the real services needed for the integration test
    browser_manager = BrowserManager()
    await browser_manager.initialize()

    try:
        # 3. Run the actual DOM Extraction Service to get real output
        dom_service = DOMExtractionService(browser_manager)
        dom_result = await dom_service.extract_dom_structure(
            url=test_url,
            session_id="integration-test-session"
        )
        
        assert dom_result.success, "DOM extraction failed during integration test"
        
        # --- DEBUGGING STEP ---
        # Let's inspect the data that the detector will receive.
        print("\n--- DEBUG: Inspecting extracted elements from DOMExtractionService ---")
        for element in dom_result.elements:
            if element.tag_name == 'a':
                print(f"Found <a> tag: Attributes={element.attributes}, Classes={element.class_names}")
        print("--- END DEBUG ---\n")
        # --- END DEBUGGING STEP ---

        # 4. Feed the real result into the Component Detector
        component_detector = ComponentDetector(dom_result)
        detection_result = component_detector.detect_components()

        # 5. Assert that the integrated flow produced the correct results
        print(f"Integration test found components: {[comp.component_type.value for comp in detection_result.components]}")
    
        assert detection_result.total_components == 4, "Should detect a card, two buttons, and one input"

        detected_types = sorted([comp.component_type.value for comp in detection_result.components])
        expected_types = sorted([
            ComponentType.CARD.value, 
            ComponentType.BUTTON.value,
            ComponentType.BUTTON.value,
            ComponentType.INPUT.value
        ])
        
        assert detected_types == expected_types

    finally:
        # 6. Ensure resources are cleaned up
        await browser_manager.cleanup()