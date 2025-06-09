import time
from typing import List, Dict, Optional, Any, Set
from .dom_extraction_service import DOMExtractionResult, ExtractedElement
from ..models.components import DetectedComponent, ComponentType, ComponentDetectionResult
from ..utils.logger import get_logger

logger = get_logger(__name__)

class ComponentDetector:
    """
    Analyzes a DOM structure to detect UI components, including their raw HTML and associated assets.
    """

    def __init__(self, dom_result: DOMExtractionResult):
        if not dom_result or not dom_result.success:
            raise ValueError("A successful DOMExtractionResult is required for component detection.")
        self.dom_result = dom_result
        self.elements_map = {el.xpath: el for el in self.dom_result.elements if el.xpath}
        self.assets = self.dom_result.assets or []

    def detect_components(self) -> ComponentDetectionResult:
        """Runs the full component detection and asset association process."""
        start_time = time.time()
        
        detected_components: List[DetectedComponent] = []
        processed_elements: Set[str] = set()

        # Simple, tag-based detection loop (can be expanded with more rules)
        for element in self.dom_result.elements:
            if element.xpath in processed_elements:
                continue

            component_type = self._get_element_component_type(element)
            if component_type != ComponentType.UNKNOWN:
                # Capture the raw HTML of the component's root element
                raw_html = self._get_raw_html_for_element(element.xpath)
                
                # Find assets associated with this component
                associated_assets = self._find_associated_assets(element)

                detected_components.append(DetectedComponent(
                    component_type=component_type,
                    elements=[element],
                    label=element.text_content or element.attributes.get('alt'),
                    bounding_box=element.bounding_box,
                    raw_html=raw_html,
                    associated_assets=associated_assets
                ))
                processed_elements.add(element.xpath)
        
        detection_time = time.time() - start_time
        logger.info(f"Detected {len(detected_components)} components in {detection_time:.2f}s")

        return ComponentDetectionResult(
            session_id=self.dom_result.session_id,
            components=detected_components,
            total_components=len(detected_components),
            detection_time_seconds=detection_time
        )

    def _get_element_component_type(self, element: ExtractedElement) -> ComponentType:
        """Determine the component type for a single element."""
        tag = element.tag_name.lower()
        if tag == 'nav':
            return ComponentType.NAVBAR
        if tag == 'button' or element.attributes.get('role') == 'button':
            return ComponentType.BUTTON
        if tag == 'form':
            return ComponentType.FORM
        if tag in ['input', 'textarea', 'select']:
            return ComponentType.INPUT
        if tag == 'img' or tag == 'svg' or tag == 'picture':
            return ComponentType.IMAGE
        if 'card' in ' '.join(element.class_names):
            return ComponentType.CARD
        return ComponentType.UNKNOWN

    def _get_raw_html_for_element(self, xpath: str) -> Optional[str]:
        # This is a placeholder. A real implementation would need to
        # get the outerHTML during the initial browser extraction.
        # For now, we simulate it.
        element = self.elements_map.get(xpath)
        if not element:
            return None
        
        # Create a simplified HTML representation
        attrs = ' '.join([f'{k}="{v}"' for k, v in element.attributes.items()])
        return f"<{element.tag_name} {attrs}></{element.tag_name}>"


    def _find_associated_assets(self, component_element: ExtractedElement) -> List[Any]:
        """Finds assets that are children of the given component element."""
        associated = []
        root_xpath = component_element.xpath
        if not root_xpath:
            return []
            
        # Find assets that are direct children in the DOM tree
        for asset in self.assets:
            # A more robust solution would use bounding boxes, but XPath is a good start.
            asset_element = self._find_element_for_asset(asset)
            if asset_element and asset_element.xpath and asset_element.xpath.startswith(root_xpath):
                associated.append(asset)
        return associated

    def _find_element_for_asset(self, asset) -> Optional[ExtractedElement]:
        """Find the DOM element corresponding to a given asset."""
        for element in self.dom_result.elements:
            if asset.url and (asset.url == element.attributes.get('src') or asset.url == element.attributes.get('href')):
                return element
        return None