from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, HttpUrl
from enum import Enum


class OutputFormat(str, Enum):
    """Output format options for DOM extraction results."""
    JSON = "json"
    HTML = "html"


class DOMExtractionRequest(BaseModel):
    """Request model for DOM extraction endpoint."""
    url: HttpUrl = Field(
        ..., 
        description="The URL to extract DOM structure from",
        json_schema_extra={"example": "https://example.com"}
    )
    
    session_id: str = Field(
        ...,
        description="Session identifier for organizing results",
        min_length=1
    )
    
    wait_for_load: bool = Field(
        default=True,
        description="Whether to wait for complete page load before extraction"
    )
    
    include_computed_styles: bool = Field(
        default=True,
        description="Whether to include computed CSS styles for elements"
    )
    
    max_depth: int = Field(
        default=10,
        description="Maximum DOM depth to extract",
        ge=1,
        le=20
    )
    
    save_result: bool = Field(
        default=True,
        description="Whether to save extraction result to file"
    )
    
    output_format: OutputFormat = Field(
        default=OutputFormat.JSON,
        description="Format for saved extraction result"
    )


class ExtractedElementModel(BaseModel):
    """Model for extracted DOM element."""
    tag_name: str = Field(..., description="HTML tag name")
    element_id: Optional[str] = Field(None, description="Element ID attribute")
    class_names: List[str] = Field(default_factory=list, description="CSS class names")
    computed_styles: Dict[str, str] = Field(default_factory=dict, description="Computed CSS styles")
    attributes: Dict[str, str] = Field(default_factory=dict, description="HTML attributes")
    text_content: Optional[str] = Field(None, description="Text content if applicable")
    children_count: int = Field(default=0, description="Number of child elements")
    xpath: Optional[str] = Field(None, description="XPath selector for element")
    bounding_box: Optional[Dict[str, float]] = Field(None, description="Element bounding box")
    is_visible: bool = Field(default=True, description="Whether element is visible")
    z_index: Optional[int] = Field(None, description="CSS z-index value")


class ExtractedStylesheetModel(BaseModel):
    """Model for extracted stylesheet."""
    href: Optional[str] = Field(None, description="Stylesheet URL")
    media: str = Field(default="all", description="Media query target")
    rules: List[Dict[str, Any]] = Field(default_factory=list, description="CSS rules")
    inline: bool = Field(default=False, description="Whether stylesheet is inline")
    content: Optional[str] = Field(None, description="Raw stylesheet content")
    



class ExtractedAssetModel(BaseModel):
    """Model for extracted asset."""
    url: Optional[str] = Field(None, description="Asset URL (if external)") # Make URL optional
    content: Optional[str] = Field(None, description="Inline asset content (e.g., for SVGs)") # Add content field
    asset_type: str = Field(..., description="Asset type (image, font, svg, etc.)")
    mime_type: Optional[str] = Field(None, description="MIME type")
    size: Optional[int] = Field(None, description="Asset size in bytes")
    dimensions: Optional[Tuple[int, int]] = Field(None, description="Asset dimensions (width, height)")
    alt_text: Optional[str] = Field(None, description="Alt text for images or identifier for inline assets")
    is_background: bool = Field(default=False, description="Whether asset is used as background")
    usage_context: List[str] = Field(default_factory=list, description="Usage context information")


class PageStructureModel(BaseModel):
    """Model for page structure metadata."""
    title: Optional[str] = Field(None, description="Page title")
    meta_description: Optional[str] = Field(None, description="Meta description")
    meta_keywords: Optional[str] = Field(None, description="Meta keywords")
    lang: Optional[str] = Field(None, description="Page language")
    charset: Optional[str] = Field(None, description="Character encoding")
    viewport: Optional[str] = Field(None, description="Viewport meta tag content")
    favicon_url: Optional[str] = Field(None, description="Favicon URL")
    canonical_url: Optional[str] = Field(None, description="Canonical URL")
    open_graph: Dict[str, str] = Field(default_factory=dict, description="Open Graph metadata")
    schema_org: List[Dict[str, Any]] = Field(default_factory=list, description="Schema.org structured data")


# --- New Models for Design System ---
class ColorPaletteModel(BaseModel):
    primary_background: Optional[str] = None
    primary_text: Optional[str] = None
    accent: Optional[str] = None
    secondary_accent: Optional[str] = None
    is_dark_theme: bool = False
    all_colors: List[str] = Field(default_factory=list)

class TypographyStyleModel(BaseModel):
    font_family: Optional[str] = None
    font_size: Optional[str] = None
    font_weight: Optional[str] = None
    line_height: Optional[str] = None
    color: Optional[str] = None

class TypographyAnalysisModel(BaseModel):
    body: TypographyStyleModel
    h1: Optional[TypographyStyleModel] = None
    h2: Optional[TypographyStyleModel] = None
    h3: Optional[TypographyStyleModel] = None
    all_families: List[str] = Field(default_factory=list)

class StyleAnalysisModel(BaseModel):
    theme: ColorPaletteModel
    typography: TypographyAnalysisModel
    css_variables: Dict[str, str] = Field(default_factory=dict)
    responsive_breakpoints: List[int] = Field(default_factory=list)
    layout_type: str = "unknown"
# --- End of New Models ---


class DOMExtractionResultModel(BaseModel):
    """Model for complete DOM extraction result."""
    url: str = Field(..., description="Extracted URL")
    session_id: str = Field(..., description="Session identifier")
    timestamp: float = Field(..., description="Extraction timestamp")
    extraction_time: float = Field(..., description="Time taken for extraction in seconds")
    
    # Core structure
    page_structure: PageStructureModel = Field(..., description="Page metadata and structure")
    elements: List[ExtractedElementModel] = Field(..., description="Extracted DOM elements")
    stylesheets: List[ExtractedStylesheetModel] = Field(..., description="Extracted stylesheets")
    assets: List[ExtractedAssetModel] = Field(..., description="Extracted assets")
    
    # Analysis data - REPLACED WITH STRUCTURED MODEL
    style_analysis: StyleAnalysisModel = Field(..., description="Comprehensive style analysis of the page")
    
    # Technical metrics
    dom_depth: int = Field(default=0, description="Maximum DOM depth")
    total_elements: int = Field(default=0, description="Total number of elements")
    total_stylesheets: int = Field(default=0, description="Total number of stylesheets")
    total_assets: int = Field(default=0, description="Total number of assets")
    success: bool = Field(default=True, description="Whether extraction was successful")
    error_message: Optional[str] = Field(None, description="Error message if extraction failed")


class DOMExtractionFileInfo(BaseModel):
    """Model for DOM extraction file information."""
    filename: str = Field(..., description="Extraction filename")
    size: int = Field(..., description="File size in bytes")
    created: datetime = Field(..., description="File creation time")
    path: str = Field(..., description="Full file path")


class DOMExtractionSessionInfo(BaseModel):
    """Model for session extraction information."""
    session_id: str = Field(..., description="Session identifier")
    extraction_count: int = Field(..., description="Number of extraction files")
    total_size: int = Field(..., description="Total size of all extraction files")
    extractions: List[DOMExtractionFileInfo] = Field(..., description="Individual extraction file info")


# Response models
class DOMExtractionResponse(BaseModel):
    """Response for DOM extraction operations."""
    success: bool = Field(..., description="Whether operation was successful")
    message: str = Field(..., description="Response message")
    extraction_result: Optional[DOMExtractionResultModel] = Field(None, description="Extraction result data")
    saved_file_path: Optional[str] = Field(None, description="Path to saved extraction file")
    session_id: str = Field(..., description="Session identifier")
    timestamp: datetime = Field(..., description="Response timestamp")


class DOMExtractionStatusResponse(BaseModel):
    """Response for DOM extraction status queries."""
    session_id: str = Field(..., description="Session identifier")
    status: str = Field(..., description="Current status")
    extraction_info: DOMExtractionSessionInfo = Field(..., description="Extraction information")
    timestamp: datetime = Field(..., description="Response timestamp")


class DOMExtractionCleanupResponse(BaseModel):
    """Response for DOM extraction cleanup operations."""
    cleaned_count: int = Field(..., description="Number of files cleaned")
    total_freed_bytes: int = Field(..., description="Total disk space freed")
    session_id: Optional[str] = Field(None, description="Session ID if specific cleanup")
    timestamp: datetime = Field(..., description="Cleanup timestamp")


class DOMComplexityResponse(BaseModel):
    """Response for page complexity analysis."""
    success: bool = Field(..., description="Whether analysis was successful")
    message: str = Field(..., description="Response message")
    complexity_analysis: Dict[str, Any] = Field(..., description="Complexity analysis results")
    extraction_metrics: Dict[str, Any] = Field(..., description="Basic extraction metrics")
    session_id: str = Field(..., description="Session identifier")
    timestamp: datetime = Field(..., description="Response timestamp")


class DOMExtractionInfoResponse(BaseModel):
    """Response for extraction information queries."""
    session_id: str = Field(..., description="Session identifier")
    extraction_info: DOMExtractionSessionInfo = Field(..., description="Extraction file information")
    timestamp: datetime = Field(..., description="Response timestamp")


# Specialized request models for different operations
class DOMComplexityRequest(BaseModel):
    """Request model for complexity analysis (lightweight extraction)."""
    url: HttpUrl = Field(..., description="URL to analyze")
    session_id: str = Field(..., description="Session identifier")
    wait_for_load: bool = Field(default=True, description="Wait for page load")
    
    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v):
        if not v or not v.strip():
            raise ValueError("Session ID cannot be empty")
        return v.strip()


class DOMRegenerationRequest(BaseModel):
    """Request model for DOM extraction regeneration."""
    url: Optional[HttpUrl] = Field(None, description="URL to extract (uses session URL if not provided)")
    wait_for_load: bool = Field(default=True, description="Wait for page load")
    include_computed_styles: bool = Field(default=True, description="Include computed styles")
    max_depth: int = Field(default=10, description="Maximum DOM depth", ge=1, le=20)
    save_result: bool = Field(default=True, description="Save result to file")
    output_format: OutputFormat = Field(default=OutputFormat.JSON, description="Output format")


# Validation models for nested data
class BoundingBoxModel(BaseModel):
    """Model for element bounding box."""
    x: float = Field(..., description="X coordinate")
    y: float = Field(..., description="Y coordinate")
    width: float = Field(..., description="Element width")
    height: float = Field(..., description="Element height")
    top: float = Field(..., description="Top coordinate")
    right: float = Field(..., description="Right coordinate")
    bottom: float = Field(..., description="Bottom coordinate")
    left: float = Field(..., description="Left coordinate")


class CSSRuleModel(BaseModel):
    """Model for CSS rule."""
    selector: str = Field(..., description="CSS selector")
    styles: str = Field(..., description="CSS styles as text")
    specificity: int = Field(default=0, description="CSS specificity score")


class LayoutAnalysisModel(BaseModel):
    """Model for layout analysis results."""
    layout_type: str = Field(..., description="Detected layout type (flex, grid, traditional)")
    color_palette: List[str] = Field(..., description="Extracted colors")
    font_families: List[str] = Field(..., description="Font families found")
    responsive_breakpoints: List[int] = Field(..., description="Media query breakpoints")
    total_colors: int = Field(default=0, description="Total unique colors found")
    total_fonts: int = Field(default=0, description="Total unique fonts found")


class ComplexityMetrics(BaseModel):
    """Model for complexity analysis metrics."""
    overall_score: float = Field(..., description="Overall complexity score (0-100)")
    dom_complexity: float = Field(..., description="DOM structure complexity (0-100)")
    style_complexity: float = Field(..., description="CSS complexity (0-100)")
    asset_complexity: float = Field(..., description="Asset complexity (0-100)")
    layout_complexity: float = Field(..., description="Layout complexity (0-100)")
    recommendations: List[str] = Field(..., description="Optimization recommendations")


# Configuration models
class ExtractionConfig(BaseModel):
    """Configuration model for extraction parameters."""
    max_elements: int = Field(default=5000, description="Maximum elements to extract")
    max_depth: int = Field(default=15, description="Maximum DOM depth")
    include_hidden_elements: bool = Field(default=False, description="Include hidden elements")
    extract_inline_styles: bool = Field(default=True, description="Extract inline styles")
    extract_computed_styles: bool = Field(default=True, description="Extract computed styles")
    extract_background_images: bool = Field(default=True, description="Extract background images")
    timeout_seconds: int = Field(default=30, description="Extraction timeout in seconds")


class AssetFilterConfig(BaseModel):
    """Configuration for asset filtering."""
    include_images: bool = Field(default=True, description="Include image assets")
    include_fonts: bool = Field(default=True, description="Include font assets")
    include_videos: bool = Field(default=False, description="Include video assets")
    include_audio: bool = Field(default=False, description="Include audio assets")
    max_asset_size: int = Field(default=10485760, description="Maximum asset size to process (bytes)")
    allowed_image_types: List[str] = Field(
        default=["jpg", "jpeg", "png", "gif", "svg", "webp"],
        description="Allowed image file types"
    )