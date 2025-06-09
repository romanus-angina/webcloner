from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class CloneStatus(str, Enum):
    """Enumeration of possible clone statuses."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    SCRAPING = "scraping"
    GENERATING = "generating"
    REFINING = "refining"
    COMPLETED = "completed"
    FAILED = "failed"


class ProgressStep(BaseModel):
    """Individual progress step information."""
    
    step_name: str = Field(..., description="Name of the current step")
    status: CloneStatus = Field(..., description="Status of this step")
    started_at: Optional[datetime] = Field(None, description="When this step started")
    completed_at: Optional[datetime] = Field(None, description="When this step completed")
    progress_percentage: float = Field(0.0, description="Progress percentage (0-100)", ge=0, le=100)
    message: Optional[str] = Field(None, description="Current status message")
    error: Optional[str] = Field(None, description="Error message if failed")


class CloneResult(BaseModel):
    """Result of a website cloning operation."""
    
    html_content: str = Field(..., description="Generated HTML content")
    css_content: Optional[str] = Field(None, description="Generated CSS content")
    assets: List[str] = Field(default_factory=list, description="List of asset URLs")
    similarity_score: Optional[float] = Field(None, description="Similarity score (0-100)", ge=0, le=100)
    generation_time: float = Field(..., description="Time taken to generate (seconds)")
    tokens_used: Optional[int] = Field(None, description="Number of LLM tokens used")


class CloneResponse(BaseModel):
    """Main response for website cloning operations."""
    
    session_id: str = Field(..., description="Unique session identifier")
    status: CloneStatus = Field(..., description="Current clone status")
    progress: List[ProgressStep] = Field(default_factory=list, description="Progress steps")
    result: Optional[CloneResult] = Field(None, description="Clone result (when completed)")
    created_at: datetime = Field(..., description="When the clone request was created")
    updated_at: datetime = Field(..., description="When the clone was last updated")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    component_analysis: Optional[Dict[str, Any]] = Field(None, description="Component detection analysis results")


    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(..., description="Current timestamp")
    version: str = Field(..., description="Application version")
    uptime: float = Field(..., description="Uptime in seconds")
    details: Optional[Dict[str, Any]] = Field(None, description="Detailed health information")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ErrorResponse(BaseModel):
    """Standard error response format."""
    
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(..., description="When the error occurred")
    request_id: Optional[str] = Field(None, description="Request identifier for tracking")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class RefinementResponse(BaseModel):
    """Response for refinement operations."""
    
    session_id: str = Field(..., description="Session identifier")
    status: CloneStatus = Field(..., description="Current refinement status")
    iterations: int = Field(..., description="Number of refinement iterations performed")
    improvements_made: List[str] = Field(..., description="List of improvements applied")
    updated_result: Optional[CloneResult] = Field(None, description="Updated clone result")
    feedback_processed: str = Field(..., description="How the feedback was interpreted")


class WebSocketMessage(BaseModel):
    """WebSocket message format."""
    
    type: str = Field(..., description="Message type")
    session_id: str = Field(..., description="Session identifier")
    timestamp: datetime = Field(..., description="Message timestamp")
    data: Dict[str, Any] = Field(..., description="Message payload")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SessionListResponse(BaseModel):
    """Response for listing sessions."""
    
    sessions: List[CloneResponse] = Field(..., description="List of clone sessions")
    total_count: int = Field(..., description="Total number of sessions")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")


class AssetInfo(BaseModel):
    """Information about a downloaded asset."""
    
    original_url: str = Field(..., description="Original asset URL")
    local_path: str = Field(..., description="Local file path")
    file_size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type of the asset")
    download_time: float = Field(..., description="Time taken to download (seconds)")


class AnalysisResult(BaseModel):
    """Result of website analysis."""
    
    page_title: Optional[str] = Field(None, description="Page title")
    description: Optional[str] = Field(None, description="Page description")
    main_colors: List[str] = Field(default_factory=list, description="Main colors used")
    font_families: List[str] = Field(default_factory=list, description="Font families detected")
    layout_type: Optional[str] = Field(None, description="Detected layout type")
    responsive_breakpoints: List[int] = Field(default_factory=list, description="Responsive breakpoints")
    assets_found: List[AssetInfo] = Field(default_factory=list, description="Assets discovered")
    complexity_score: float = Field(0.0, description="Page complexity score (0-100)", ge=0, le=100)