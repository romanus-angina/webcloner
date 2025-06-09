import pytest
import asyncio
import tempfile
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from dataclasses import asdict

from app.services.dom_extraction_service import (
    DOMExtractionService,
    ExtractedElement,
    ExtractedStylesheet,
    ExtractedAsset,
    PageStructure,
    DOMExtractionResult
)
from app.services.browser_manager import BrowserManager
from app.core.exceptions import BrowserError, ProcessingError


class TestExtractedElement:
    """Test ExtractedElement data structure."""
    
    def test_extracted_element_creation(self):
        """Test creating extracted element."""
        element = ExtractedElement(
            tag_name="div",
            element_id="test-id",
            class_names=["class1", "class2"],
            computed_styles={"color": "red", "background": "blue"},
            attributes={"data-test": "value"},
            text_content="Test content",
            children_count=3,
            xpath="//div[@id='test-id']",
            bounding_box={"x": 10, "y": 20, "width": 100, "height": 50},
            is_visible=True,
            z_index=10
        )
        
        assert element.tag_name == "div"
        assert element.element_id == "test-id"
        assert element.class_names == ["class1", "class2"]
        assert element.computed_styles["color"] == "red"
        assert element.children_count == 3
        assert element.is_visible is True
        assert element.z_index == 10
    
    def test_extracted_element_defaults(self):
        """Test extracted element with default values."""
        element = ExtractedElement(tag_name="span")
        
        assert element.tag_name == "span"
        assert element.element_id is None
        assert element.class_names == []
        assert element.computed_styles == {}
        assert element.attributes == {}
        assert element.children_count == 0
        assert element.is_visible is True


class TestExtractedAsset:
    """Test ExtractedAsset data structure."""
    
    def test_extracted_asset_creation(self):
        """Test creating extracted asset."""
        asset = ExtractedAsset(
            url="https://example.com/image.jpg",
            asset_type="image",
            mime_type="image/jpeg",
            size=12345,
            dimensions=(800, 600),
            alt_text="Test image",
            is_background=False,
            usage_context=["img-tag", "hero-section"]
        )
        
        assert asset.url == "https://example.com/image.jpg"
        assert asset.asset_type == "image"
        assert asset.mime_type == "image/jpeg"
        assert asset.size == 12345
        assert asset.dimensions == (800, 600)
        assert asset.alt_text == "Test image"
        assert asset.is_background is False
        assert asset.usage_context == ["img-tag", "hero-section"]


class TestDOMExtractionResult:
    """Test DOMExtractionResult data structure."""
    
    def test_dom_extraction_result_creation(self):
        """Test creating DOM extraction result."""
        page_structure = PageStructure(
            title="Test Page",
            meta_description="Test description",
            lang="en"
        )
        
        element = ExtractedElement(tag_name="div")
        stylesheet = ExtractedStylesheet(href="style.css")
        asset = ExtractedAsset(url="image.jpg", asset_type="image")
        
        result = DOMExtractionResult(
            url="https://example.com",
            session_id="test-session",
            timestamp=time.time(),
            extraction_time=2.5,
            page_structure=page_structure,
            elements=[element],
            stylesheets=[stylesheet],
            assets=[asset],
            layout_analysis={"layout_type": "flex"},
            color_palette=["#ff0000", "#00ff00"],
            font_families=["Arial", "Helvetica"],
            responsive_breakpoints=[768, 1024],
            dom_depth=5,
            total_elements=1,
            total_stylesheets=1,
            total_assets=1,
            success=True
        )
        
        assert result.url == "https://example.com"
        assert result.session_id == "test-session"
        assert result.success is True
        assert result.total_elements == 1
        assert result.total_stylesheets == 1
        assert result.total_assets == 1
        assert result.dom_depth == 5
        assert len(result.color_palette) == 2
        assert len(result.font_families) == 2


class TestDOMExtractionService:
    """Test suite for DOMExtractionService."""
    
    @pytest.fixture
    def service(self):
        """Create DOM extraction service instance."""
        return DOMExtractionService()
    
    @pytest.fixture
    def mock_browser_manager(self):
        """Create mock browser manager."""
        manager = AsyncMock(spec=BrowserManager)
        return manager
    
    @pytest.mark.asyncio
    async def test_extract_assets_with_images_and_inline_svgs(self, service, mock_browser_manager):
        """Test that both external images and inline SVGs are extracted correctly."""
        service.browser_manager = mock_browser_manager
        test_url = "data:text/html,..." # URL is not important for the mock

        # 1. Mock the page context and evaluation
        mock_page = AsyncMock()
        mock_browser_manager.page_context.return_value.__aenter__.return_value = mock_page
        
        # We don't need to mock navigate_to_url if we mock the evaluate calls that follow it.
        
        # 2. Define the exact, ordered sequence of return values for `page.evaluate`
        dom_extractor_result = {
            "elements": [
                # Add a dummy element to make the test more realistic
                {"tag_name": "img", "element_id": None, "class_names": [], "text_content": None, "children_count": 0, "xpath": "/html/body/img[1]"}
            ],
            "total_elements": 1,
            "dom_depth": 3
        }

        asset_extractor_result = {
            "assets": [
                {"url": "/logo.png", "asset_type": "image", "usage_context": ["img-tag"], "alt_text": "Company Logo"},
                {"url": None, "asset_type": "svg", "content": '<svg width="100" height="100"><circle/></svg>', "usage_context": ["inline-svg"]}
            ],
            "totalAssets": 2
        }
        
        # This mock is now fully compliant with the StyleAnalysisModel
        style_analyzer_result = {
            "theme": {"primary_background": "rgb(255, 255, 255)", "primary_text": "rgb(0, 0, 0)", "is_dark_theme": False, "all_colors": []},
            "typography": {"body": {"font_family": "Arial"}, "all_families": ["Arial"]},
            "css_variables": {},
            "responsive_breakpoints": [],
            "layout_type": "unknown"
        }
        
        # Assign the list of results to the mock's side_effect
        mock_page.evaluate.side_effect = [
            None,
            dom_extractor_result,
            asset_extractor_result,
            style_analyzer_result
        ]

        # 3. Mock the page structure extraction to prevent its own `evaluate` call
        with patch.object(service, '_extract_page_structure', return_value=PageStructure(title="Test")):
            # 4. Run the extraction
            result = await service.extract_dom_structure(
                url=test_url,
                session_id="asset-test-session"
            )

        # 5. Assert the results
        assert result.success is True
        assert len(result.assets) == 2, "Should have extracted one image and one SVG"

        # Check the image asset
        img_asset = next((a for a in result.assets if a.asset_type == 'image'), None)
        assert img_asset is not None
        assert img_asset.url.endswith("/logo.png")
        assert img_asset.content is None

        # Check the SVG asset
        svg_asset = next((a for a in result.assets if a.asset_type == 'svg'), None)
        assert svg_asset is not None
        assert svg_asset.url is None
        assert '<svg' in svg_asset.content
    
    def test_dom_extractor_script_structure(self, service):
        """Test DOM extractor script has required structure."""
        script = service._get_dom_extractor_script()
        
        # Check for key functions and features
        assert "extractAllElements" in script 
        assert "querySelectorAll" in script
        assert "getComputedStyle" in script
        
    def test_style_extractor_script_structure(self, service):
        """Test style extractor script has required structure."""
        script = service._get_style_extractor_script()
        
        assert "extractStylesheets" in script
        assert "calculateSpecificity" in script
        assert "link[rel=\"stylesheet\"]" in script
        assert "CSSRule.STYLE_RULE" in script
        assert "cssRules" in script
    
    def test_asset_extractor_script_structure(self, service):
        """Test asset extractor script has required structure."""
        script = service._get_asset_extractor_script()
        
        assert "extractAssets" in script
        assert "addAsset" in script
        assert "img[src]" in script
        assert "backgroundImage" in script
        assert "font-face" in script
        assert "video" in script
        assert "audio" in script
    
    def test_layout_analyzer_script_structure(self, service):
        """Test layout analyzer script has required structure."""
        script = service._get_layout_analyzer_script()
        
        assert "analyzeLayout" in script
        assert "colorPalette" in script
        assert "fontFamilies" in script
        assert "responsiveBreakpoints" in script
        assert "layoutType" in script
        assert "getComputedStyle" in script
    
    @pytest.mark.asyncio
    async def test_extract_dom_structure_success(self, service, mock_browser_manager):
        """Test successful DOM structure extraction."""
        service.browser_manager = mock_browser_manager
        
        # Mock page and context
        mock_page = AsyncMock()
        
        # Mock page methods
        mock_page.wait_for_timeout = AsyncMock()
        
        # Mock JavaScript evaluation results
        dom_result = {
            "elements": [
                {
                    "tag_name": "div",
                    "element_id": "test-id",
                    "class_names": ["test-class"],
                    "computed_styles": {"color": "red"},
                    "attributes": {"data-test": "value"},
                    "text_content": "Test content",
                    "children_count": 0,
                    "xpath": "//div[@id='test-id']",
                    "bounding_box": {"x": 0, "y": 0, "width": 100, "height": 50},
                    "is_visible": True,
                    "z_index": None
                }
            ],
            "dom_depth": 3,
            "total_elements": 1
        }
        
        style_result = {
            "stylesheets": [
                {
                    "href": "https://example.com/style.css",
                    "media": "all",
                    "inline": False,
                    "rules": [
                        {
                            "selector": ".test-class",
                            "styles": "color: red;",
                            "specificity": 10
                        }
                    ]
                }
            ],
            "totalStylesheets": 1
        }
        
        asset_result = {
            "assets": [
                {
                    "url": "/image.jpg",
                    "assetType": "image",
                    "usageContext": ["img-tag"],
                    "isBackground": False,
                    "altText": "Test image",
                    "dimensions": [800, 600]
                }
            ],
            "totalAssets": 1
        }
        
        layout_result = {
            "colorPalette": ["#ff0000", "#00ff00"],
            "fontFamilies": ["Arial", "Helvetica"],
            "responsiveBreakpoints": [768, 1024],
            "layoutType": "flex"
        }
        
        # Mock page structure extraction
        structure_result = {
            "title": "Test Page",
            "metaDescription": "Test description",
            "lang": "en",
            "charset": "UTF-8",
            "openGraph": {"og:title": "Test"},
            "schemaOrg": []
        }
        
        # Set up page evaluation mocks
        mock_page.evaluate.side_effect = [
            dom_result,
            style_result,
            asset_result,
            layout_result,
            structure_result
        ]
        
        # Mock browser manager methods
        mock_browser_manager.page_context.return_value.__aenter__.return_value = mock_page
        mock_browser_manager.navigate_to_url = AsyncMock()
        mock_browser_manager.wait_for_page_load = AsyncMock()
        
        # Mock page structure extraction method
        with patch.object(service, '_extract_page_structure') as mock_extract_structure:
            mock_extract_structure.return_value = PageStructure(
                title="Test Page",
                meta_description="Test description",
                lang="en"
            )
            
            # Perform extraction
            result = await service.extract_dom_structure(
                url="https://example.com",
                session_id="test-session"
            )
        
        # Assertions
        assert result.success is True
        assert result.url == "https://example.com"
        assert result.session_id == "test-session"
        assert result.total_elements == 1
        assert result.total_stylesheets == 1
        assert result.total_assets == 1
        assert result.dom_depth >= 0
        assert len(result.elements) == 1
        assert len(result.stylesheets) == 1
        assert len(result.assets) == 1
        
        # Check extracted element
        element = result.elements[0]
        assert element.tag_name == "div"
        assert element.element_id == "test-id"
        assert element.class_names == ["test-class"]
        
        # Check extracted asset URL resolution
        asset = result.assets[0]
        assert asset.url == "https://example.com/image.jpg"  # Should be resolved to absolute URL
        assert asset.asset_type == "image"
    
    @pytest.mark.asyncio
    async def test_extract_dom_structure_browser_error(self, service, mock_browser_manager):
        """Test DOM extraction with browser error."""
        service.browser_manager = mock_browser_manager
        
        # Mock browser manager to raise error
        mock_browser_manager.page_context.side_effect = BrowserError("Browser failed")
        
        result = await service.extract_dom_structure(
            url="https://example.com",
            session_id="test-session"
        )
        
        assert result.success is False
        assert "DOM extraction failed" in result.error_message
        assert result.total_elements == 0
        assert result.total_stylesheets == 0
        assert result.total_assets == 0
    
    @pytest.mark.asyncio
    async def test_extract_dom_structure_no_browser_manager(self, service):
        """Test DOM extraction without browser manager."""
        with pytest.raises(BrowserError, match="Browser manager not available"):
            await service.extract_dom_structure(
                url="https://example.com",
                session_id="test-session"
            )
    
    @pytest.mark.asyncio
    async def test_extract_page_structure(self, service, mock_browser_manager):
        """Test page structure extraction."""
        mock_page = AsyncMock()
        
        # Mock page structure evaluation
        structure_data = {
            "title": "Test Page Title",
            "metaDescription": "Test page description",
            "metaKeywords": "test, keywords",
            "lang": "en-US",
            "charset": "UTF-8",
            "viewport": "width=device-width, initial-scale=1",
            "faviconUrl": "https://example.com/favicon.ico",
            "canonicalUrl": "https://example.com/canonical",
            "openGraph": {
                "og:title": "Test Page",
                "og:description": "Test description"
            },
            "schemaOrg": [
                {"@type": "WebPage", "name": "Test Page"}
            ]
        }
        
        mock_page.evaluate.return_value = structure_data
        
        result = await service._extract_page_structure(mock_page, "https://example.com")
        
        assert result.title == "Test Page Title"
        assert result.meta_description == "Test page description"
        assert result.meta_keywords == "test, keywords"
        assert result.lang == "en-US"
        assert result.charset == "UTF-8"
        assert result.viewport == "width=device-width, initial-scale=1"
        assert result.favicon_url == "https://example.com/favicon.ico"
        assert result.canonical_url == "https://example.com/canonical"
        assert result.open_graph["og:title"] == "Test Page"
        assert len(result.schema_org) == 1
    
    @pytest.mark.asyncio
    async def test_extract_page_structure_error(self, service, mock_browser_manager):
        """Test page structure extraction with error."""
        mock_page = AsyncMock()
        mock_page.evaluate.side_effect = Exception("Evaluation failed")
        
        result = await service._extract_page_structure(mock_page, "https://example.com")
        
        # Should return empty structure on error
        assert result.title is None
        assert result.meta_description is None
        assert result.lang is None
    
    @pytest.mark.asyncio
    async def test_save_extraction_result_json(self, service):
        """Test saving extraction result as JSON."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('app.services.dom_extraction_service.settings') as mock_settings:
                mock_settings.temp_storage_path = temp_dir
                
                # Create test result
                result = DOMExtractionResult(
                    url="https://example.com",
                    session_id="test-session",
                    timestamp=time.time(),
                    extraction_time=1.5,
                    page_structure=PageStructure(title="Test"),
                    elements=[],
                    stylesheets=[],
                    assets=[],
                    layout_analysis={},
                    color_palette=[],
                    font_families=[],
                    responsive_breakpoints=[],
                    success=True
                )
                
                # Save result
                file_path = await service.save_extraction_result(result, "json")
                
                # Verify file exists and contains correct data
                assert Path(file_path).exists()
                
                with open(file_path, 'r') as f:
                    saved_data = json.load(f)
                
                assert saved_data["url"] == "https://example.com"
                assert saved_data["session_id"] == "test-session"
                assert saved_data["success"] is True
    
    @pytest.mark.asyncio
    async def test_save_extraction_result_html(self, service):
        """Test saving extraction result as HTML."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('app.services.dom_extraction_service.settings') as mock_settings:
                mock_settings.temp_storage_path = temp_dir
                
                # Create test result with some data
                element = ExtractedElement(
                    tag_name="div",
                    element_id="test",
                    class_names=["test-class"],
                    computed_styles={"color": "red"}
                )
                
                asset = ExtractedAsset(
                    url="https://example.com/image.jpg",
                    asset_type="image",
                    alt_text="Test image"
                )
                
                result = DOMExtractionResult(
                    url="https://example.com",
                    session_id="test-session",
                    timestamp=time.time(),
                    extraction_time=2.5,
                    page_structure=PageStructure(title="Test Page"),
                    elements=[element],
                    stylesheets=[],
                    assets=[asset],
                    layout_analysis={"layout_type": "flex"},
                    color_palette=["#ff0000", "#00ff00"],
                    font_families=["Arial"],
                    responsive_breakpoints=[768],
                    total_elements=1,
                    total_assets=1,
                    success=True
                )
                
                # Save as HTML
                file_path = await service.save_extraction_result(result, "html")
                
                # Verify file exists and contains HTML
                assert Path(file_path).exists()
                
                with open(file_path, 'r') as f:
                    html_content = f.read()
                
                assert "<!DOCTYPE html>" in html_content
                assert "DOM Extraction Report" in html_content
                assert "https://example.com" in html_content
                assert "test-session" in html_content
                assert "Test Page" in html_content
    
    @pytest.mark.asyncio
    async def test_save_extraction_result_invalid_format(self, service):
        """Test saving extraction result with invalid format."""
        result = DOMExtractionResult(
            url="https://example.com",
            session_id="test-session",
            timestamp=time.time(),
            extraction_time=1.0,
            page_structure=PageStructure(),
            elements=[],
            stylesheets=[],
            assets=[],
            layout_analysis={},
            color_palette=[],
            font_families=[],
            responsive_breakpoints=[],
            success=True
        )
        
        with pytest.raises(ProcessingError, match="Failed to save extraction result"):
            await service.save_extraction_result(result, "invalid")
    
    @pytest.mark.asyncio
    async def test_analyze_page_complexity(self, service):
        """Test page complexity analysis."""
        # Create test result with various complexity factors
        elements = [
            ExtractedElement(tag_name="div") for _ in range(50)
        ]
        
        stylesheets = [
            ExtractedStylesheet(
                href="style1.css",
                rules=[{"selector": ".class1", "styles": "color: red"}] * 20
            ),
            ExtractedStylesheet(
                href="style2.css", 
                rules=[{"selector": ".class2", "styles": "background: blue"}] * 30
            )
        ]
        
        assets = [
            ExtractedAsset(url=f"image{i}.jpg", asset_type="image") 
            for i in range(25)
        ]
        
        result = DOMExtractionResult(
            url="https://example.com",
            session_id="test-session",
            timestamp=time.time(),
            extraction_time=1.0,
            page_structure=PageStructure(),
            elements=elements,
            stylesheets=stylesheets,
            assets=assets,
            layout_analysis={"layoutType": "grid"},
            color_palette=["#ff0000"] * 20,  # Large color palette
            font_families=["Arial", "Helvetica"],
            responsive_breakpoints=[768, 1024, 1440],
            dom_depth=8,
            total_elements=50,
            total_stylesheets=2,
            total_assets=25,
            success=True
        )
        
        complexity = await service.analyze_page_complexity(result)
        
        assert "overall_score" in complexity
        assert "dom_complexity" in complexity
        assert "style_complexity" in complexity
        assert "asset_complexity" in complexity
        assert "layout_complexity" in complexity
        assert "recommendations" in complexity
        
        # Check that complexity scores are reasonable
        assert 0 <= complexity["overall_score"] <= 100
        assert 0 <= complexity["dom_complexity"] <= 100
        assert 0 <= complexity["style_complexity"] <= 100
        assert 0 <= complexity["asset_complexity"] <= 100
        assert 0 <= complexity["layout_complexity"] <= 100
        
        # Should have some recommendations for high complexity
        assert len(complexity["recommendations"]) > 0
    
    @pytest.mark.asyncio
    async def test_analyze_page_complexity_failed_extraction(self, service):
        """Test complexity analysis with failed extraction."""
        result = DOMExtractionResult(
            url="https://example.com",
            session_id="test-session",
            timestamp=time.time(),
            extraction_time=0.5,
            page_structure=PageStructure(),
            elements=[],
            stylesheets=[],
            assets=[],
            layout_analysis={},
            color_palette=[],
            font_families=[],
            responsive_breakpoints=[],
            success=False,
            error_message="Extraction failed"
        )
        
        complexity = await service.analyze_page_complexity(result)
        
        assert "error" in complexity
        assert "Cannot analyze failed extraction" in complexity["error"]
    
    @pytest.mark.asyncio
    async def test_get_extraction_info(self, service):
        """Test getting extraction information."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('app.services.dom_extraction_service.settings') as mock_settings:
                mock_settings.temp_storage_path = temp_dir
                
                # Create test extraction files
                extractions_dir = Path(temp_dir) / "extractions"
                extractions_dir.mkdir(parents=True, exist_ok=True)
                
                test_data = {"test": "data"}
                
                file1 = extractions_dir / "test-session_extraction_123.json"
                file2 = extractions_dir / "test-session_extraction_456.json"
                file3 = extractions_dir / "other-session_extraction_789.json"
                
                file1.write_text(json.dumps(test_data))
                file2.write_text(json.dumps(test_data))
                file3.write_text(json.dumps(test_data))
                
                # Get info for specific session
                info = await service.get_extraction_info("test-session")
                
                assert info["session_id"] == "test-session"
                assert info["extraction_count"] == 2
                assert info["total_size"] > 0
                assert len(info["extractions"]) == 2
                
                # Check extraction file info
                extraction_info = info["extractions"][0]
                assert "filename" in extraction_info
                assert "size" in extraction_info
                assert "created" in extraction_info
                assert "path" in extraction_info
    
    @pytest.mark.asyncio
    async def test_cleanup_extractions(self, service):
        """Test extraction files cleanup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('app.services.dom_extraction_service.settings') as mock_settings:
                mock_settings.temp_storage_path = temp_dir
                
                # Create test extraction files
                extractions_dir = Path(temp_dir) / "extractions"
                extractions_dir.mkdir(parents=True, exist_ok=True)
                
                # Create files for different sessions
                files_to_create = [
                    "session1_extraction_123.json",
                    "session1_extraction_456.json",
                    "session2_extraction_789.json",
                    "session3_extraction_101.json"
                ]
                
                for filename in files_to_create:
                    (extractions_dir / filename).write_text('{"test": "data"}')
                
                # Test session-specific cleanup
                cleaned_count = await service.cleanup_extractions(session_id="session1")
                
                assert cleaned_count == 2
                assert not (extractions_dir / "session1_extraction_123.json").exists()
                assert not (extractions_dir / "session1_extraction_456.json").exists()
                assert (extractions_dir / "session2_extraction_789.json").exists()
                assert (extractions_dir / "session3_extraction_101.json").exists()
                
                # Test cleanup all remaining
                cleaned_count = await service.cleanup_extractions()
                
                assert cleaned_count == 2
                remaining_files = list(extractions_dir.glob("*.json"))
                assert len(remaining_files) == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_extractions_by_age(self, service):
        """Test cleanup by file age."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('app.services.dom_extraction_service.settings') as mock_settings:
                mock_settings.temp_storage_path = temp_dir
                
                extractions_dir = Path(temp_dir) / "extractions"
                extractions_dir.mkdir(parents=True, exist_ok=True)
                
                # Create files and modify their timestamps
                old_file = extractions_dir / "old_extraction_123.json"
                new_file = extractions_dir / "new_extraction_456.json"
                
                old_file.write_text('{"test": "old"}')
                new_file.write_text('{"test": "new"}')
                
                # Make one file appear old (more than 25 hours ago)
                old_time = time.time() - (26 * 3600)  # 26 hours ago
                import os
                os.utime(old_file, (old_time, old_time))
                
                # Cleanup files older than 24 hours
                cleaned_count = await service.cleanup_extractions(older_than_hours=24)
                
                assert cleaned_count == 1
                assert not old_file.exists()
                assert new_file.exists()


# Integration tests that require actual browser functionality
@pytest.mark.integration
@pytest.mark.asyncio
async def test_dom_extraction_integration():
    """
    Integration test for DOM extraction service with real browser.
    Requires browser manager to be properly initialized.
    """
    from app.services.browser_manager import BrowserManager, BrowserType
    
    browser_manager = BrowserManager(BrowserType.AUTO)
    
    try:
        await browser_manager.initialize()
        
        service = DOMExtractionService(browser_manager)
        
        test_url = "data:text/html,<html><head><title>Test Page</title></head><body><h1>Test</h1><p>Content</p></body></html>"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('app.services.dom_extraction_service.settings') as mock_settings:
                mock_settings.temp_storage_path = temp_dir
                
                result = await service.extract_dom_structure(
                    url=test_url,
                    session_id="integration-test"
                )
                
                assert result.success is True
                assert result.total_elements > 0
                
                # Updated assertion - the test shows 6 elements are extracted:
                # html, head, title, body, h1, p
                assert len(result.elements) == 6  # Changed from 5 to 6
                
                # Verify specific elements exist
                element_tags = [el.tag_name for el in result.elements]
                assert "html" in element_tags
                assert "head" in element_tags  # head is now included
                assert "title" in element_tags  # title is now included
                assert "body" in element_tags
                assert "h1" in element_tags
                assert "p" in element_tags
                
                assert result.page_structure.title == "Test Page"
                
                # Test saving result
                saved_path = await service.save_extraction_result(result, "json")
                assert Path(saved_path).exists()
                
                # Verify saved content
                with open(saved_path, 'r') as f:
                    saved_data = json.load(f)
                
                assert saved_data["success"] is True
                assert saved_data["url"] == test_url
                
    finally:
        await browser_manager.cleanup()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complexity_analysis_integration():
    """
    Integration test for complexity analysis with real browser.
    """
    from app.services.browser_manager import BrowserManager, BrowserType
    
    browser_manager = BrowserManager(BrowserType.AUTO)
    
    try:
        await browser_manager.initialize()
        
        service = DOMExtractionService(browser_manager)
        
        # Create a simple test page using about:blank and inject content
        test_url = "about:blank"
        
        result = await service.extract_dom_structure(
            url=test_url,
            session_id="complexity-test"
        )
        
        # For about:blank, we expect minimal content
        assert result.success is True
        assert result.url == test_url
        
    finally:
        await browser_manager.cleanup()

