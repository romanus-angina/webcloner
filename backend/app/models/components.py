from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

from .dom_extraction import ExtractedElementModel, ExtractedAssetModel

class ComponentType(str, Enum):
    """Enumeration of detectable UI component types."""
    BUTTON = "button"
    CARD = "card"
    NAVBAR = "navbar"
    FORM = "form"
    INPUT = "input"
    IMAGE = "image"
    UNKNOWN = "unknown"

class DetectedComponent(BaseModel):
    """Represents a detected UI component on the page."""
    
    component_type: ComponentType = Field(
        ...,
        description="The type of the detected component."
    )
    
    elements: List[ExtractedElementModel] = Field(
        ...,
        description="The list of DOM elements that make up this component."
    )
    
    label: Optional[str] = Field(
        None,
        description="A descriptive label for the component, e.g., button text."
    )

    bounding_box: Optional[Dict[str, float]] = Field(
        None, 
        description="The aggregated bounding box of all elements in the component."
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the component."
    )
    raw_html: Optional[str] = Field(None, description="The raw outerHTML of the component's root element.")
    associated_assets: List[ExtractedAssetModel] = Field(default_factory=list, description="Assets associated with this component.")

class ComponentDetectionResult(BaseModel):
    """The result of a component detection process."""

    session_id: str = Field(..., description="The session ID for the detection.")
    
    components: List[DetectedComponent] = Field(
        ...,
        description="A list of all components detected on the page."
    )

    total_components: int = Field(..., description="Total number of components found.")
    
    detection_time_seconds: float = Field(
        ..., 
        description="Time taken for the detection process."
    )