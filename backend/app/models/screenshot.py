from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class ViewportType(str, Enum):
    """Standard viewport types for responsive design."""
    MOBILE = "mobile"
    TABLET = "tablet" 
    DESKTOP = "desktop"
    LARGE_DESKTOP = "large_desktop"
    CUSTOM = "custom"


class ViewportModel(BaseModel):
    """Viewport configuration model."""
    name: str = Field(..., description="Viewport name")
    width: int = Field(..., description="Viewport width in pixels", ge=1, le=4096)
    height: int = Field(..., description="Viewport height in pixels", ge=1, le=4096)
    device_scale_factor: float = Field(1.0, description="Device pixel ratio", ge=0.1, le=4.0)
    is_mobile: bool = Field(False, description="Whether this is a mobile viewport")
    user_agent: Optional[str] = Field(None, description="Custom user agent string")


class ScreenshotRequest(BaseModel):
    """Request model for screenshot capture."""
    url: str = Field(..., description="URL to capture screenshot of")
    session_id: str = Field(..., description="Session identifier")
    viewports: Optional[List[ViewportModel]] = Field(
        None, 
        description="Custom viewports (uses defaults if not provided)"
    )
    viewport_types: Optional[List[ViewportType]] = Field(
        None,
        description="Standard viewport types to capture"
    )
    concurrent: bool = Field(True, description="Whether to capture screenshots concurrently")
    max_concurrent: int = Field(3, description="Maximum concurrent captures", ge=1, le=10)
    wait_for_load: bool = Field(True, description="Wait for page load completion")
    full_page: bool = Field(True, description="Capture full page or just viewport")
    quality: int = Field(90, description="JPEG quality", ge=1, le=100)
    
    @field_validator('viewports')
    @classmethod
    def validate_viewports(cls, v, info):
        """Validate viewport configuration."""
        if v is not None and len(v) > 10:
            raise ValueError("Maximum 10 viewports allowed per request")
        return v


class ScreenshotResultModel(BaseModel):
    """Model for individual screenshot result."""
    viewport_name: str = Field(..., description="Name of the viewport used")
    viewport_width: int = Field(..., description="Viewport width")
    viewport_height: int = Field(..., description="Viewport height")
    file_path: str = Field(..., description="Path to screenshot file")
    file_size: int = Field(..., description="File size in bytes")
    capture_time: float = Field(..., description="Time taken to capture (seconds)")
    page_title: Optional[str] = Field(None, description="Page title when captured")
    page_dimensions: Optional[Dict[str, int]] = Field(None, description="Actual page dimensions")
    success: bool = Field(..., description="Whether capture was successful")
    error: Optional[str] = Field(None, description="Error message if failed")
    timestamp: datetime = Field(..., description="When screenshot was taken")


class ScreenshotBatchModel(BaseModel):
    """Model for batch screenshot results."""
    url: str = Field(..., description="URL that was captured")
    session_id: str = Field(..., description="Session identifier")
    screenshots: List[ScreenshotResultModel] = Field(..., description="Individual screenshot results")
    total_capture_time: float = Field(..., description="Total time for all captures")
    created_at: datetime = Field(..., description="When batch was created")
    success_count: int = Field(..., description="Number of successful captures")
    failure_count: int = Field(..., description="Number of failed captures")
    success_rate: float = Field(..., description="Success rate as percentage")


class ScreenshotInfoModel(BaseModel):
    """Model for screenshot file information."""
    filename: str = Field(..., description="Screenshot filename")
    size: int = Field(..., description="File size in bytes") 
    created: datetime = Field(..., description="File creation time")
    viewport_name: Optional[str] = Field(None, description="Viewport name")
    dimensions: Optional[str] = Field(None, description="Image dimensions")
    path: str = Field(..., description="Full file path")


class ScreenshotSessionInfo(BaseModel):
    """Model for session screenshot information."""
    session_id: str = Field(..., description="Session identifier")
    screenshot_count: int = Field(..., description="Number of screenshots")
    total_size: int = Field(..., description="Total size of all screenshots")
    screenshots: List[ScreenshotInfoModel] = Field(..., description="Individual screenshot info")


class ViewportPresetResponse(BaseModel):
    """Response model for viewport presets."""
    viewport_type: ViewportType = Field(..., description="Viewport type")
    viewport: ViewportModel = Field(..., description="Viewport configuration")


class ViewportPresetsResponse(BaseModel):
    """Response model for all viewport presets."""
    presets: List[ViewportPresetResponse] = Field(..., description="Available viewport presets")
    custom_supported: bool = Field(True, description="Whether custom viewports are supported")
    max_custom_viewports: int = Field(10, description="Maximum custom viewports per request")


# Response models that extend the base response format
class ScreenshotResponse(BaseModel):
    """Response for screenshot capture operations."""
    success: bool = Field(..., description="Whether operation was successful")
    message: str = Field(..., description="Response message")
    data: Optional[ScreenshotBatchModel] = Field(None, description="Screenshot batch data")
    session_id: str = Field(..., description="Session identifier")
    timestamp: datetime = Field(..., description="Response timestamp")


class ScreenshotStatusResponse(BaseModel):
    """Response for screenshot status queries."""
    session_id: str = Field(..., description="Session identifier") 
    status: str = Field(..., description="Current status")
    screenshots_info: ScreenshotSessionInfo = Field(..., description="Screenshot information")
    timestamp: datetime = Field(..., description="Response timestamp")


class ScreenshotCleanupResponse(BaseModel):
    """Response for screenshot cleanup operations."""
    cleaned_count: int = Field(..., description="Number of files cleaned")
    total_freed_bytes: int = Field(..., description="Total disk space freed")
    session_id: Optional[str] = Field(None, description="Session ID if specific cleanup")
    timestamp: datetime = Field(..., description="Cleanup timestamp")