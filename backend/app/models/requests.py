from typing import Optional, List
from pydantic import BaseModel, HttpUrl, Field, validator
import re


class CloneWebsiteRequest(BaseModel):
    """Request model for website cloning endpoint."""
    
    url: HttpUrl = Field(
        ..., 
        description="The URL of the website to clone",
        example="https://example.com"
    
    
    quality: str = Field(
        default="balanced",
        description="Quality level for cloning (fast, balanced, high)",
        regex="^(fast|balanced|high)$"
    )
    
    include_images: bool = Field(
        default=True,
        description="Whether to include images in the cloned website"
    )
    
    include_styling: bool = Field(
        default=True,
        description="Whether to include CSS styling"
    )
    
    max_depth: int = Field(
        default=1,
        description="Maximum depth of pages to clone (1 = single page)",
        ge=1,
        le=3
    )
    
    custom_instructions: Optional[str] = Field(
        default=None,
        description="Custom instructions for the cloning process",
        max_length=500
    )
    
    @validator('url')
    @classmethod
    def validate_url(cls, v):
        """Validate that the URL is accessible and not localhost."""
        url_str = str(v)
        
        # Check for localhost or internal IPs
        localhost_patterns = [
            r'localhost',
            r'127\.0\.0\.1',
            r'0\.0\.0\.0',
            r'192\.168\.',
            r'10\.',
            r'172\.(1[6-9]|2[0-9]|3[0-1])\.'
        ]
        
        for pattern in localhost_patterns:
            if re.search(pattern, url_str, re.IGNORECASE):
                raise ValueError("Local URLs are not allowed for security reasons")
        
        return v


class RefinementRequest(BaseModel):
    """Request model for refining generated HTML."""
    
    session_id: str = Field(
        ...,
        description="Session ID from the original clone request",
        min_length=1
    )
    
    feedback: str = Field(
        ...,
        description="User feedback for improvements",
        min_length=10,
        max_length=1000
    )
    
    focus_areas: Optional[List[str]] = Field(
        default=None,
        description="Specific areas to focus on (layout, colors, typography, etc.)"
    )


class HealthCheckRequest(BaseModel):
    """Request model for health check with optional details."""
    
    include_details: bool = Field(
        default=False,
        description="Whether to include detailed system information"
    )


class WebSocketConnectionRequest(BaseModel):
    """Request model for WebSocket connection parameters."""
    
    session_id: Optional[str] = Field(
        default=None,
        description="Existing session ID to reconnect to"
    )
    
    subscribe_to: List[str] = Field(
        default=["progress", "logs"],
        description="Event types to subscribe to"
    )
    
    @validator('subscribe_to')
    @classmethod
    def validate_subscribe_to(cls, v):
        """Validate subscription event types."""
        valid_events = ["progress", "logs", "errors", "completion"]
        for event in v:
            if event not in valid_events:
                raise ValueError(f"Invalid event type: {event}. Valid types: {valid_events}")
        return v