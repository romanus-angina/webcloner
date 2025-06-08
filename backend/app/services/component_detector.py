import time
from typing import List, Dict, Optional, Any, Set
from dataclasses import asdict

from .dom_extraction_service import DOMExtractionResult, ExtractedElement
from ..models.components import DetectedComponent, ComponentType, ComponentDetectionResult
from ..models.dom_extraction import ExtractedElementModel 

class ComponentDetector:
    """
    Analyzes a DOM structure to detect and classify UI components.
    
    This service uses a set of heuristics to identify common UI patterns
    like buttons, cards, navbars, and forms from extracted DOM elements.
    """

    def __init__(self, dom_result: DOMExtractionResult):
        if not dom_result or not dom_result.success:
            raise ValueError("A successful DOMExtractionResult is required for component detection.")
        self.dom_result = dom_result
        self.elements = dom_result.elements
        self._element_map = {el.xpath: el for el in self.elements if el.xpath}
        
        # Create a simple parent-child mapping for structural analysis
        self._children_map = self._build_children_map()

    def _build_children_map(self) -> Dict[str, List[ExtractedElement]]:
        """Build a mapping of parent elements to their children."""
        children_map = {}
        
        for element in self.elements:
            if not element.xpath:
                continue
                
            # Simple xpath-based parent detection
            xpath_parts = element.xpath.split('/')
            if len(xpath_parts) > 1:
                parent_xpath = '/'.join(xpath_parts[:-1])
                if parent_xpath not in children_map:
                    children_map[parent_xpath] = []
                children_map[parent_xpath].append(element)
        
        return children_map

    def detect_components(self) -> ComponentDetectionResult:
        """
        Runs the full component detection process.

        Returns:
            A ComponentDetectionResult containing all found components.
        """
        start_time = time.time()
        
        detected_components: List[DetectedComponent] = []
        processed_elements: Set[str] = set()  # Track processed elements to avoid duplicates
        
        # Detect complex components first (they may contain simpler ones)
        detected_components.extend(self._detect_navbars(processed_elements))
        detected_components.extend(self._detect_forms(processed_elements))
        
        # Then detect individual components
        detected_components.extend(self._detect_buttons(processed_elements))
        detected_components.extend(self._detect_inputs(processed_elements))
        detected_components.extend(self._detect_cards(processed_elements))

        detection_time = time.time() - start_time
        
        return ComponentDetectionResult(
            session_id=self.dom_result.session_id,
            components=detected_components,
            total_components=len(detected_components),
            detection_time_seconds=detection_time
        )

    def _detect_navbars(self, processed_elements: Set[str]) -> List[DetectedComponent]:
        """Detects navigation bar components."""
        navbars = []
        
        for element in self.elements:
            if element.xpath in processed_elements:
                continue
                
            is_navbar = False
            tag = element.tag_name.lower()
            
            # Rule 1: Semantic nav elements
            if tag == 'nav':
                is_navbar = True
            
            # Rule 2: Elements with navigation-related roles or classes
            elif self._has_nav_indicators(element):
                # Additional checks for navbar-like structure
                children = self._children_map.get(element.xpath, [])
                link_count = sum(1 for child in children if child.tag_name.lower() == 'a')
                
                # Must have multiple links and horizontal-like styling
                if link_count >= 2 and self._looks_horizontal(element):
                    is_navbar = True
            
            if is_navbar:
                # Get all child elements that are part of this navbar
                navbar_elements = self._get_component_elements(element)
                
                # Mark all these elements as processed
                for nav_el in navbar_elements:
                    if nav_el.xpath:
                        processed_elements.add(nav_el.xpath)
                
                # Convert to dictionaries for Pydantic validation
                element_dicts = [asdict(el) for el in navbar_elements]
                
                navbars.append(DetectedComponent(
                    component_type=ComponentType.NAVBAR,
                    elements=element_dicts,
                    label=self._extract_navbar_label(element),
                    bounding_box=element.bounding_box,
                    metadata={
                        "link_count": len([el for el in navbar_elements if el.tag_name.lower() == 'a']),
                        "has_logo": self._has_logo_element(navbar_elements)
                    }
                ))
        
        return navbars

    def _detect_forms(self, processed_elements: Set[str]) -> List[DetectedComponent]:
        """Detects form components."""
        forms = []
        
        for element in self.elements:
            if element.xpath in processed_elements:
                continue
                
            is_form = False
            tag = element.tag_name.lower()
            
            # Rule 1: Semantic form elements
            if tag == 'form':
                is_form = True
            
            # Rule 2: Containers with multiple form inputs
            elif tag in ['div', 'section', 'fieldset']:
                children = self._children_map.get(element.xpath, [])
                input_count = sum(1 for child in children 
                                if child.tag_name.lower() in ['input', 'textarea', 'select'])
                button_count = sum(1 for child in children 
                                 if child.tag_name.lower() == 'button' or 
                                 (child.tag_name.lower() == 'input' and 
                                  child.attributes.get('type') in ['submit', 'button']))
                
                # Must have at least 2 inputs and ideally a submit button
                if input_count >= 2 and (button_count >= 1 or input_count >= 3):
                    is_form = True
            
            if is_form:
                # Get all child elements that are part of this form
                form_elements = self._get_component_elements(element)
                
                # Mark all these elements as processed
                for form_el in form_elements:
                    if form_el.xpath:
                        processed_elements.add(form_el.xpath)
                
                # Convert to dictionaries for Pydantic validation
                element_dicts = [asdict(el) for el in form_elements]
                
                forms.append(DetectedComponent(
                    component_type=ComponentType.FORM,
                    elements=element_dicts,
                    label=self._extract_form_label(element),
                    bounding_box=element.bounding_box,
                    metadata={
                        "input_count": len([el for el in form_elements if el.tag_name.lower() in ['input', 'textarea', 'select']]),
                        "has_submit": any(el.tag_name.lower() == 'button' or 
                                        (el.tag_name.lower() == 'input' and el.attributes.get('type') == 'submit')
                                        for el in form_elements)
                    }
                ))
        
        return forms

    def _detect_buttons(self, processed_elements: Set[str]) -> List[DetectedComponent]:
        """Detects button-like elements."""
        buttons = []
        
        for element in self.elements:
            if element.xpath in processed_elements:
                continue
                
            is_button = False
            tag = element.tag_name.lower()
            
            # Rule 1: <button> tags or <input type="submit|button|reset">
            if tag == 'button' or (tag == 'input' and element.attributes.get('type') in ['submit', 'button', 'reset']):
                is_button = True
            
            # Rule 2: <a> tags with button-like classes or roles
            elif tag == 'a' and ('button' in (element.attributes.get('role', '')) or self._has_button_class(element)):
                is_button = True

            if is_button:
                processed_elements.add(element.xpath)
                element_dict = asdict(element)
                buttons.append(DetectedComponent(
                    component_type=ComponentType.BUTTON,
                    elements=[element_dict],
                    label=element.text_content or element.attributes.get('value'),
                    bounding_box=element.bounding_box
                ))
        
        return buttons
        
    def _detect_inputs(self, processed_elements: Set[str]) -> List[DetectedComponent]:
        """Detects input fields."""
        inputs = []
        
        for element in self.elements:
            if element.xpath in processed_elements:
                continue
                
            tag = element.tag_name.lower()
            if tag in ['input', 'textarea', 'select'] and element.attributes.get('type') not in ['submit', 'button', 'reset', 'hidden']:
                processed_elements.add(element.xpath)
                element_dict = asdict(element)
                inputs.append(DetectedComponent(
                    component_type=ComponentType.INPUT,
                    elements=[element_dict],
                    label=element.attributes.get('placeholder') or element.attributes.get('aria-label'),
                    bounding_box=element.bounding_box
                ))
        
        return inputs

    def _detect_cards(self, processed_elements: Set[str]) -> List[DetectedComponent]:
        """Detects card-like container elements with improved logic."""
        cards = []
        
        for element in self.elements:
            if element.xpath in processed_elements:
                continue
                
            if element.tag_name.lower() not in ['div', 'section', 'article']:
                continue

            is_card = False
            styles = element.computed_styles
            
            # Method 1: Check computed styles for card indicators
            has_shadow = (
                'box-shadow' in styles and 
                styles['box-shadow'] != 'none' and 
                styles['box-shadow'] != ''
            )
            has_border = (
                'border-width' in styles and 
                not styles['border-width'].startswith('0') and
                styles['border-width'] != ''
            ) or (
                'border' in styles and 
                styles['border'] != 'none' and
                styles['border'] != ''
            )
            has_padding = (
                'padding' in styles and 
                not styles['padding'].startswith('0') and
                styles['padding'] != ''
            )

            # Method 2: Check inline styles (fallback for when computed styles fail)
            inline_style = element.attributes.get('style', '').lower()
            has_inline_shadow = 'box-shadow' in inline_style and 'none' not in inline_style
            has_inline_border = 'border' in inline_style and ('px' in inline_style or 'solid' in inline_style)
            has_inline_padding = 'padding' in inline_style and 'px' in inline_style

            # Method 3: Check class names for card indicators
            has_card_class = any('card' in class_name.lower() for class_name in element.class_names)

            # Card detection logic
            if has_card_class:
                # If it has a card class, it's likely a card
                is_card = True
            elif (has_shadow or has_inline_shadow) and (has_padding or has_inline_padding):
                # Shadow + padding = likely a card
                is_card = True
            elif (has_border or has_inline_border) and (has_padding or has_inline_padding) and element.children_count > 1:
                # Border + padding + multiple children = likely a card
                is_card = True

            if is_card:
                processed_elements.add(element.xpath)
                element_dict = asdict(element)
                
                cards.append(DetectedComponent(
                    component_type=ComponentType.CARD,
                    elements=[element_dict],
                    bounding_box=element.bounding_box,
                    metadata={
                        "detection_method": self._get_card_detection_method(element, styles, inline_style),
                        "has_shadow": has_shadow or has_inline_shadow,
                        "has_border": has_border or has_inline_border,
                        "has_padding": has_padding or has_inline_padding,
                        "children_count": element.children_count
                    }
                ))
        
        return cards

    def _get_card_detection_method(self, element: ExtractedElement, styles: Dict[str, str], inline_style: str) -> str:
        """Determine how the card was detected for debugging."""
        if any('card' in class_name.lower() for class_name in element.class_names):
            return "class_name"
        elif 'box-shadow' in inline_style:
            return "inline_shadow"
        elif 'box-shadow' in styles and styles['box-shadow'] != 'none':
            return "computed_shadow"
        elif 'border' in inline_style:
            return "inline_border"
        else:
            return "computed_styles"

    # Helper methods for navbar detection
    def _has_nav_indicators(self, element: ExtractedElement) -> bool:
        """Check if element has navigation-related indicators."""
        nav_keywords = ['nav', 'navigation', 'menu', 'header', 'topbar']
        
        # Check classes
        for class_name in element.class_names:
            for keyword in nav_keywords:
                if keyword in class_name.lower():
                    return True
        
        # Check id
        if element.element_id:
            for keyword in nav_keywords:
                if keyword in element.element_id.lower():
                    return True
        
        # Check role
        role = element.attributes.get('role', '').lower()
        if role in ['navigation', 'menubar']:
            return True
        
        return False

    def _looks_horizontal(self, element: ExtractedElement) -> bool:
        """Check if element appears to be horizontally oriented."""
        styles = element.computed_styles
        
        # Check for flex with row direction
        display = styles.get('display', '')
        flex_direction = styles.get('flex-direction', '')
        
        if 'flex' in display and flex_direction in ['row', '']:
            return True
        
        # Check for horizontal positioning patterns
        float_val = styles.get('float', '')
        if float_val in ['left', 'right']:
            return True
        
        return False

    def _extract_navbar_label(self, element: ExtractedElement) -> Optional[str]:
        """Extract a descriptive label for navbar."""
        # Try to find text content or aria-label
        if element.text_content:
            return element.text_content[:50]  # Limit length
        
        aria_label = element.attributes.get('aria-label')
        if aria_label:
            return aria_label
        
        return "Navigation"

    def _extract_form_label(self, element: ExtractedElement) -> Optional[str]:
        """Extract a descriptive label for form."""
        # Check for form title or legend
        children = self._children_map.get(element.xpath, [])
        
        for child in children:
            if child.tag_name.lower() in ['legend', 'h1', 'h2', 'h3'] and child.text_content:
                return child.text_content
        
        aria_label = element.attributes.get('aria-label')
        if aria_label:
            return aria_label
        
        return "Form"

    def _has_logo_element(self, elements: List[ExtractedElement]) -> bool:
        """Check if navbar contains a logo element."""
        logo_indicators = ['logo', 'brand', 'title']
        
        for element in elements:
            # Check img tags
            if element.tag_name.lower() == 'img':
                alt_text = element.attributes.get('alt', '').lower()
                for indicator in logo_indicators:
                    if indicator in alt_text:
                        return True
            
            # Check classes
            for class_name in element.class_names:
                for indicator in logo_indicators:
                    if indicator in class_name.lower():
                        return True
        
        return False

    def _get_component_elements(self, root_element: ExtractedElement) -> List[ExtractedElement]:
        """Get all elements that belong to a component, including the root."""
        component_elements = [root_element]
        
        # Add direct children (simple approach for MVP)
        if root_element.xpath in self._children_map:
            component_elements.extend(self._children_map[root_element.xpath])
        
        return component_elements

    def _has_button_class(self, element: ExtractedElement) -> bool:
        """Checks if an element has a common button-like CSS class."""
        button_class_keywords = ['btn', 'button']
        for class_name in element.class_names:
            for keyword in button_class_keywords:
                if keyword in class_name.lower():
                    return True
        return False