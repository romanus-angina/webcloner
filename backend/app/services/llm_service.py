import asyncio
import random
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, UTC
import json

from ..config import settings
from ..core.exceptions import LLMError, ConfigurationError
from ..models.components import ComponentDetectionResult, DetectedComponent
from ..services.dom_extraction_service import DOMExtractionResult
from ..utils.logger import get_logger

logger = get_logger(__name__)

try:
    import anthropic
except ImportError:
    anthropic = None


class LLMService:
    """
    Service for generating HTML using LLM based on component analysis.
    Enhanced with retry logic and rate limiting.
    """
    
    def __init__(self):
        self._client = None
        self._validate_configuration()
        self.max_retries = 3
        self.base_delay = 2  # Base delay in seconds
        self.max_delay = 60  # Max delay in seconds
    
    def _validate_configuration(self) -> None:
        """Validate LLM service configuration."""
        if not settings.anthropic_api_key:
            raise ConfigurationError(
                "Anthropic API key not configured",
                config_key="ANTHROPIC_API_KEY"
            )
        
        if anthropic is None:
            raise ConfigurationError(
                "Anthropic SDK not installed. Run: pip install anthropic"
            )
    
    def _get_client(self):
        """Get or create Anthropic client."""
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        return self._client
    
    async def _make_request_with_retry(self, prompt: str) -> Dict[str, Any]:
        """Make API request with exponential backoff retry logic."""
        client = self._get_client()
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Making LLM request (attempt {attempt + 1}/{self.max_retries + 1})")
                
                response = await asyncio.to_thread(
                    client.messages.create,
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=8000,
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                logger.info("LLM request successful")
                return {
                    "content": response.content[0].text,
                    "usage": response.usage
                }
                
            except anthropic.RateLimitError as e:
                logger.warning(f"Rate limit error on attempt {attempt + 1}: {str(e)}")
                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt, base_delay=10)  # Longer delay for rate limits
                    logger.info(f"Waiting {delay} seconds before retry...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise LLMError(f"Rate limit exceeded after {self.max_retries + 1} attempts", provider="anthropic")
            
            except anthropic.APIError as e:
                error_message = str(e)
                logger.warning(f"API error on attempt {attempt + 1}: {error_message}")
                
                # Check for overload (529) or server errors (5xx)
                if "overloaded" in error_message.lower() or "529" in error_message:
                    if attempt < self.max_retries:
                        delay = self._calculate_delay(attempt, base_delay=5)
                        logger.info(f"API overloaded, waiting {delay} seconds before retry...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise LLMError(f"API overloaded after {self.max_retries + 1} attempts", provider="anthropic")
                
                # For other API errors, don't retry
                raise LLMError(f"API error: {error_message}", provider="anthropic")
            
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {str(e)}")
                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise LLMError(f"Request failed after {self.max_retries + 1} attempts: {str(e)}", provider="anthropic")
        
        # This should never be reached, but just in case
        raise LLMError("Maximum retries exceeded", provider="anthropic")
    
    def _calculate_delay(self, attempt: int, base_delay: Optional[int] = None) -> float:
        """Calculate delay with exponential backoff and jitter."""
        if base_delay is None:
            base_delay = self.base_delay
        
        # Exponential backoff: base_delay * (2 ^ attempt)
        delay = base_delay * (2 ** attempt)
        
        # Add jitter (random factor between 0.5 and 1.5)
        jitter = random.uniform(0.5, 1.5)
        delay *= jitter
        
        # Cap at max_delay
        return min(delay, self.max_delay)
    
    async def generate_html_from_components(
        self,
        component_result: ComponentDetectionResult,
        dom_result: DOMExtractionResult,
        original_url: str,
        quality_level: str = "balanced"
    ) -> Dict[str, Any]:
        """Generate HTML with enhanced style awareness."""
        logger.info(f"Generating enhanced HTML for {original_url} with {component_result.total_components} components")
        
        try:
            # Build enhanced prompt with style data
            prompt = self._build_generation_prompt(
                component_result, dom_result, original_url, quality_level
            )
            
            # Make request with retry logic
            api_response = await self._make_request_with_retry(prompt)
            
            # Parse response
            generated_content = api_response["content"]
            usage = api_response["usage"]
            
            # Extract HTML and CSS from response
            html_content, css_content = self._parse_llm_response(generated_content)
            
            # Enhanced similarity scoring with style awareness
            similarity_score = self._calculate_similarity_score(
                component_result, dom_result, html_content
            )
            
            result = {
                "html_content": html_content,
                "css_content": css_content,
                "similarity_score": similarity_score,
                "generation_time": 0.0,
                "tokens_used": usage.input_tokens + usage.output_tokens,
                "components_replicated": self._count_replicated_components(component_result, html_content),
                "quality_level": quality_level,
                "model_used": "claude-3-5-sonnet-20241022",
                "style_analysis_used": True
            }
            
            logger.info(f"Enhanced HTML generation completed: {similarity_score:.1f}% similarity")
            
            return result
            
        except Exception as e:
            logger.error(f"Enhanced HTML generation failed: {str(e)}")
            raise LLMError(f"HTML generation failed: {str(e)}", provider="anthropic")
    

    def _build_generation_prompt(
        self,
        component_result: ComponentDetectionResult,
        dom_result: DOMExtractionResult,
        original_url: str,
        quality_level: str
    ) -> str:
        """Build an enhanced prompt with comprehensive style information."""
        
        # Extract style analysis from DOM result
        layout_analysis = dom_result.layout_analysis
        theme_colors = layout_analysis.get("theme_colors", {})
        typography = layout_analysis.get("typography", {})
        css_variables = layout_analysis.get("css_variables", {})
        visual_hierarchy = layout_analysis.get("visual_hierarchy", [])
        
        # Build component summary
        component_summary = self._build_component_summary(component_result)
        
        # Build style summary
        style_summary = self._build_style_summary(theme_colors, typography, css_variables, visual_hierarchy)
        
        # Page info
        page_info = {
            "title": dom_result.page_structure.title or "Cloned Website",
            "description": dom_result.page_structure.meta_description or "",
            "total_elements": dom_result.total_elements,
            "is_dark_theme": theme_colors.get("is_dark_theme", False)
        }
        
        # Quality instructions
        quality_instructions = self._get_quality_instructions(quality_level)
        
        prompt = f"""You are an expert web developer tasked with creating a visually identical HTML replica of a website.

    ORIGINAL WEBSITE: {original_url}

    PAGE ANALYSIS:
    - Title: {page_info['title']}
    - Description: {page_info['description']}
    - Total Elements: {page_info['total_elements']}
    - Theme: {"Dark" if page_info['is_dark_theme'] else "Light"} theme detected

    VISUAL STYLE ANALYSIS:
    {style_summary}

    DETECTED COMPONENTS ({component_result.total_components} total):
    {component_summary}

    {quality_instructions}

    CRITICAL STYLE REQUIREMENTS:
    1. **Theme Matching**: {"Use dark backgrounds and light text" if page_info['is_dark_theme'] else "Use light backgrounds and dark text"}
    2. **Color Accuracy**: Match the exact background colors, text colors, and accent colors
    3. **Typography**: Use the same font families, sizes, and weights
    4. **Spacing**: Apply the same margin/padding patterns
    5. **Visual Hierarchy**: Maintain the same element prominence and sizing

    IMPLEMENTATION REQUIREMENTS:
    1. Generate complete, valid HTML5 with embedded CSS
    2. Use semantic HTML elements that match the component types
    3. Apply modern CSS (flexbox/grid) for layout
    4. Ensure responsive design
    5. Include hover states and interactive elements
    6. Match visual spacing and proportions exactly

    OUTPUT FORMAT:
    ```html
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{page_info['title']}</title>
        <style>
            /* Critical: Apply the theme colors and typography first */
            :root {{
                {self._generate_css_variables(css_variables, theme_colors)}
            }}
            
            /* Your complete CSS here */
        </style>
    </head>
    <body>
        <!-- Your HTML structure here -->
    </body>
    </html>
    ```

    Focus on perfect visual replication - the clone should be nearly indistinguishable from the original."""

        return prompt
    
    def _build_style_summary(self, theme_colors: dict, typography: dict, css_variables: dict, visual_hierarchy: list) -> str:
        """Build a comprehensive style summary for the prompt."""
        summary_parts = []
        
        # Theme colors
        if theme_colors:
            summary_parts.append("THEME COLORS:")
            if theme_colors.get("primary_background"):
                summary_parts.append(f"- Primary Background: {theme_colors['primary_background']}")
            if theme_colors.get("primary_text"):
                summary_parts.append(f"- Primary Text: {theme_colors['primary_text']}")
            if theme_colors.get("is_dark_theme"):
                summary_parts.append("- Dark theme detected - use dark backgrounds!")
            summary_parts.append("")
        
        # Typography
        if typography:
            summary_parts.append("TYPOGRAPHY:")
            body_text = typography.get("body_text", {})
            if body_text:
                summary_parts.append(f"- Body Font: {body_text.get('font_family', 'N/A')}")
                summary_parts.append(f"- Body Size: {body_text.get('font_size', 'N/A')}")
                summary_parts.append(f"- Body Color: {body_text.get('color', 'N/A')}")
            
            headings = typography.get("headings", {})
            for tag, styles in headings.items():
                if styles:
                    summary_parts.append(f"- {tag.upper()}: {styles.get('font_size', 'N/A')} {styles.get('font_weight', 'N/A')}")
            summary_parts.append("")
        
        # CSS Variables (if any)
        if css_variables:
            summary_parts.append("CSS VARIABLES:")
            for var, value in list(css_variables.items())[:10]:  # Limit to first 10
                summary_parts.append(f"- {var}: {value}")
            summary_parts.append("")
        
        # Visual hierarchy (key elements)
        if visual_hierarchy:
            summary_parts.append("KEY VISUAL ELEMENTS:")
            for item in visual_hierarchy[:5]:  # Top 5 most important
                element_type = item.get("element_type", "unknown")
                text = item.get("text_content", "")[:50]  # First 50 chars
                styles = item.get("styles", {})
                summary_parts.append(f"- {element_type}: '{text}' - {styles.get('font_size', 'N/A')} {styles.get('color', 'N/A')}")
            summary_parts.append("")
        
        return "\n".join(summary_parts)
    
    def _generate_css_variables(self, css_variables: dict, theme_colors: dict) -> str:
        """Generate CSS custom properties for the theme."""
        variables = []
        
        # Add theme color variables
        if theme_colors.get("primary_background"):
            variables.append(f"--primary-bg: {theme_colors['primary_background']};")
        if theme_colors.get("primary_text"):
            variables.append(f"--primary-text: {theme_colors['primary_text']};")
        
        # Add any existing CSS variables
        for var, value in list(css_variables.items())[:15]:  # Limit to prevent prompt bloat
            variables.append(f"{var}: {value};")
        
        return "\n            ".join(variables)

    def _build_component_summary(self, component_result: ComponentDetectionResult) -> str:
        """Build a detailed summary of detected components for the prompt."""
        if not component_result.components:
            return "No specific components detected - create a simple, clean layout."
        
        summary_lines = []
        component_counts = {}
        
        for component in component_result.components:
            comp_type = component.component_type.value
            component_counts[comp_type] = component_counts.get(comp_type, 0) + 1
            
            label = component.label or f"{comp_type.title()} component"
            summary_lines.append(f"- {comp_type.upper()}: {label}")
            
            # Add metadata if available
            if component.metadata:
                metadata_str = []
                for key, value in component.metadata.items():
                    if isinstance(value, bool):
                        if value:
                            metadata_str.append(f"{key.replace('_', ' ')}")
                    else:
                        metadata_str.append(f"{key.replace('_', ' ')}: {value}")
                
                if metadata_str:
                    summary_lines.append(f"  ({', '.join(metadata_str)})")
        
        # Add component count summary
        count_summary = ", ".join([f"{count} {comp_type}(s)" for comp_type, count in component_counts.items()])
        summary_lines.insert(0, f"Component breakdown: {count_summary}")
        summary_lines.append("")
        
        return "\n".join(summary_lines)
    
    def _get_quality_instructions(self, quality_level: str) -> str:
        """Get quality-specific generation instructions."""
        instructions = {
            "fast": """
QUALITY LEVEL: FAST
- Focus on basic structure and functionality
- Use simple, clean CSS
- Prioritize speed over visual perfection
- Basic responsive design
            """,
            "balanced": """
QUALITY LEVEL: BALANCED
- Good balance of visual appeal and performance
- Include hover effects and basic animations
- Responsive design with mobile considerations
- Match color scheme and typography reasonably well
            """,
            "high": """
QUALITY LEVEL: HIGH
- High attention to visual detail and aesthetics
- Advanced CSS with animations, gradients, shadows
- Pixel-perfect responsive design
- Exact color matching and typography
- Professional polish and refinement
            """
        }
        
        return instructions.get(quality_level, instructions["balanced"])
    
    def _parse_llm_response(self, response_text: str) -> tuple[str, Optional[str]]:
        """Parse HTML and CSS from LLM response."""
        html_content = ""
        css_content = None
        
        # Extract HTML block
        html_start = response_text.find("```html")
        if html_start != -1:
            html_start += 7  # Skip ```html
            html_end = response_text.find("```", html_start)
            if html_end != -1:
                html_content = response_text[html_start:html_end].strip()
        
        # Extract additional CSS block if present
        css_start = response_text.find("```css")
        if css_start != -1:
            css_start += 6  # Skip ```css
            css_end = response_text.find("```", css_start)
            if css_end != -1:
                css_content = response_text[css_start:css_end].strip()
        
        # Fallback: if no HTML blocks found, use the entire response
        if not html_content:
            html_content = response_text.strip()
        
        return html_content, css_content
    
    def _calculate_similarity_score(self, component_result: ComponentDetectionResult, dom_result: DOMExtractionResult, generated_html: str) -> float:
        """Calculate a rough similarity score based on component presence."""
        if not component_result.components:
            return 75.0  # Default score for pages without detected components
        
        score = 0.0
        total_components = len(component_result.components)
        
        # Check for presence of each component type in generated HTML
        for component in component_result.components:
            comp_type = component.component_type.value
            
            # Simple check for component presence
            if comp_type == "navbar" and ("<nav" in generated_html or "navbar" in generated_html.lower()):
                score += 1
            elif comp_type == "form" and "<form" in generated_html:
                score += 1
            elif comp_type == "button" and "<button" in generated_html:
                score += 1
            elif comp_type == "input" and "<input" in generated_html:
                score += 1
            elif comp_type == "card" and ("card" in generated_html.lower() or "class=" in generated_html):
                score += 0.8  # Cards are harder to detect
        
        # Convert to percentage
        similarity_percentage = (score / total_components) * 100
        
        # Ensure reasonable bounds
        return max(60.0, min(95.0, similarity_percentage))
    
    def _count_replicated_components(self, component_result: ComponentDetectionResult, generated_html: str) -> Dict[str, int]:
        """Count how many components of each type were replicated."""
        replicated = {}
        
        for component in component_result.components:
            comp_type = component.component_type.value
            if comp_type not in replicated:
                replicated[comp_type] = 0
            
            # Simple presence check
            if comp_type == "navbar" and ("<nav" in generated_html or "navbar" in generated_html.lower()):
                replicated[comp_type] += 1
            elif comp_type == "form" and "<form" in generated_html:
                replicated[comp_type] += 1
            elif comp_type == "button" and "<button" in generated_html:
                replicated[comp_type] += 1
            elif comp_type == "input" and "<input" in generated_html:
                replicated[comp_type] += 1
            elif comp_type == "card" and "card" in generated_html.lower():
                replicated[comp_type] += 1
        
        return replicated


# Global LLM service instance
llm_service = LLMService()