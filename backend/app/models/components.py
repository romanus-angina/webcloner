from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class ComponentType(str, Enum):
    """Enumeration of detectable UI component types."""
    BUTTON = "button"
    CARD = "card"
    NAVBAR = "navbar"
    FORM = "form"
    INPUT = "input"
    IMAGE = "image"
    UNKNOWN = "unknown"
    LINK = "link"
    HEADER = "header"
    SECTION = "section"
    DIV = "div" # A generic container
    SVG = "svg"

class DetectedComponent(BaseModel):
    """Represents a detected UI component on the page."""
    
    component_type: ComponentType = Field(
        ...,
        description="The type of the detected component."
    )
    
    html_snippet: str = Field(..., description="The opening tag or full HTML for the component.")
    
    # NEW: Add fields from your proposed data structure
    relevant_css_rules: List[Dict[str, str]] = Field(default_factory=list, description="Specific CSS rules that style this component.")
    children: List['DetectedComponent'] = Field(default_factory=list, description="A list of child components, creating a tree.")
    
    # Optional fields
    label: Optional[str] = Field(None, description="A descriptive label for the component (e.g., button text).")
    asset_url: Optional[str] = Field(None, description="The URL for an image or other external asset.")
DetectedComponent.model_rebuild()

class ComponentDetectionResult(BaseModel):
    """The result of a component detection process."""
    session_id: str = Field(..., description="The session ID for the detection.")
    # The 'components' field will now hold the root of the blueprint tree
    blueprint: Optional[DetectedComponent] = Field(None, description="The root of the component blueprint.")
    detection_time_seconds: float = Field(..., description="Time taken for the detection process.")