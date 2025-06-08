import time
from typing import List, Dict, Optional, Any
from dataclasses import asdict # Import the asdict function

from .dom_extraction_service import DOMExtractionResult, ExtractedElement
from ..models.components import DetectedComponent, ComponentType, ComponentDetectionResult

from ..models.dom_extraction import ExtractedElementModel 

class ComponentDetector:
    """
    Analyzes a DOM structure to detect and classify UI components.
    
    This service uses a set of heuristics to identify common UI patterns
    like buttons, cards, and navbars from a list of extracted DOM elements.
    """

    def __init__(self, dom_result: DOMExtractionResult):
        if not dom_result or not dom_result.success:
            raise ValueError("A successful DOMExtractionResult is required for component detection.")
        self.dom_result = dom_result
        self.elements = dom_result.elements
        self._element_map = {el.xpath: el for el in self.elements}

    def detect_components(self) -> ComponentDetectionResult:
        """
        Runs the full component detection process.

        Returns:
            A ComponentDetectionResult containing all found components.
        """
        start_time = time.time()
        
        detected_components: List[DetectedComponent] = []
        
        # Heuristic-based detection
        detected_components.extend(self._detect_buttons())
        detected_components.extend(self._detect_inputs())
        detected_components.extend(self._detect_cards())
        
        # TODO: Add detectors for more complex components like navbars, forms, etc.

        detection_time = time.time() - start_time
        
        return ComponentDetectionResult(
            session_id=self.dom_result.session_id,
            components=detected_components,
            total_components=len(detected_components),
            detection_time_seconds=detection_time
        )

    def _detect_buttons(self) -> List[DetectedComponent]:
        """Detects button-like elements."""
        buttons = []
        for element in self.elements:
            is_button = False
            tag = element.tag_name.lower()
            
            # Rule 1: <button> tags or <input type="submit|button|reset">
            if tag == 'button' or (tag == 'input' and element.attributes.get('type') in ['submit', 'button', 'reset']):
                is_button = True
            
            # Rule 2: <a> tags with button-like classes or roles
            if tag == 'a' and ('button' in (element.attributes.get('role', '')) or self._has_button_class(element)):
                is_button = True

            if is_button:
                # Convert dataclass to a dict for Pydantic validation
                element_dict = asdict(element)
                buttons.append(DetectedComponent(
                    component_type=ComponentType.BUTTON,
                    elements=[element_dict], # Pass the dictionary here
                    label=element.text_content or element.attributes.get('value'),
                    bounding_box=element.bounding_box
                ))
        return buttons
        
    def _detect_inputs(self) -> List[DetectedComponent]:
        """Detects input fields."""
        inputs = []
        for element in self.elements:
            tag = element.tag_name.lower()
            if tag == 'input' and element.attributes.get('type') not in ['submit', 'button', 'reset', 'hidden']:
                # Convert dataclass to a dict for Pydantic validation
                element_dict = asdict(element)
                inputs.append(DetectedComponent(
                    component_type=ComponentType.INPUT,
                    elements=[element_dict], # Pass the dictionary here
                    label=element.attributes.get('placeholder') or element.attributes.get('aria-label'),
                    bounding_box=element.bounding_box
                ))
        return inputs

    def _detect_cards(self) -> List[DetectedComponent]:
        """Detects card-like container elements."""
        cards = []
        for element in self.elements:
            if element.tag_name.lower() not in ['div', 'section', 'article']:
                continue

            styles = element.computed_styles
            
            # Rule: Has a box-shadow or a prominent border and some padding
            has_shadow = 'box-shadow' in styles and styles['box-shadow'] != 'none'
            has_border = 'border-width' in styles and not styles['border-width'].startswith('0')
            has_padding = 'padding' in styles and not styles['padding'].startswith('0')

            if (has_shadow or has_border) and has_padding and element.children_count > 1:
                # Convert dataclass to a dict for Pydantic validation
                element_dict = asdict(element)
                cards.append(DetectedComponent(
                    component_type=ComponentType.CARD,
                    elements=[element_dict], # Pass the dictionary here
                    bounding_box=element.bounding_box
                ))
        return cards
        
    def _has_button_class(self, element: ExtractedElement) -> bool:
        """Checks if an element has a common button-like CSS class."""
        button_class_keywords = ['btn', 'button']
        for class_name in element.class_names:
            for keyword in button_class_keywords:
                if keyword in class_name.lower():
                    return True
        return False