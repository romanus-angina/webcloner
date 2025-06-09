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
        """
        Generate HTML based on detected components and DOM structure.
        Enhanced with retry logic for better reliability.
        """
        logger.info(f"Generating HTML for {original_url} with {component_result.total_components} components")
        
        try:
            # Build component-aware prompt
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
            
            # Calculate metrics
            similarity_score = self._calculate_similarity_score(component_result, html_content)
            
            result = {
                "html_content": html_content,
                "css_content": css_content,
                "similarity_score": similarity_score,
                "generation_time": 0.0,  # Will be set by caller
                "tokens_used": usage.input_tokens + usage.output_tokens,
                "components_replicated": self._count_replicated_components(component_result, html_content),
                "quality_level": quality_level,
                "model_used": "claude-3-5-sonnet-20241022"
            }
            
            logger.info(f"HTML generation completed: {similarity_score:.1f}% similarity, {result['tokens_used']} tokens")
            
            return result
            
        except Exception as e:
            logger.error(f"LLM HTML generation failed: {str(e)}")
            raise LLMError(f"HTML generation failed: {str(e)}", provider="anthropic")
    
    def _build_generation_prompt(
        self,
        component_result: ComponentDetectionResult,
        dom_result: DOMExtractionResult,
        original_url: str,
        quality_level: str
    ) -> str:
        """Build a component-aware prompt for HTML generation."""
        
        # Component summary
        component_summary = self._build_component_summary(component_result)
        
        # Page structure summary
        page_info = {
            "title": dom_result.page_structure.title or "Cloned Website",
            "description": dom_result.page_structure.meta_description or "",
            "color_palette": dom_result.color_palette[:10],  # Top 10 colors
            "font_families": dom_result.font_families[:5],   # Top 5 fonts
            "total_elements": dom_result.total_elements
        }
        
        # Quality-specific instructions
        quality_instructions = self._get_quality_instructions(quality_level)
        
        prompt = f"""You are an expert web developer tasked with creating a visually similar HTML replica of a website.

ORIGINAL WEBSITE: {original_url}

PAGE ANALYSIS:
- Title: {page_info['title']}
- Description: {page_info['description']}
- Total Elements: {page_info['total_elements']}
- Color Palette: {', '.join(page_info['color_palette']) if page_info['color_palette'] else 'Not detected'}
- Font Families: {', '.join(page_info['font_families']) if page_info['font_families'] else 'Not detected'}

DETECTED COMPONENTS ({component_result.total_components} total):
{component_summary}

{quality_instructions}

REQUIREMENTS:
1. Generate complete, valid HTML5 with embedded CSS
2. Preserve the component structure and hierarchy detected above
3. Use semantic HTML elements that match the component types
4. Create responsive design with modern CSS (flexbox/grid where appropriate)
5. Ensure all interactive elements (buttons, forms, links) are functional
6. Match the color palette and typography where possible
7. Include proper meta tags and document structure

OUTPUT FORMAT:
Provide your response with the HTML first, followed by additional CSS if needed:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_info['title']}</title>
    <style>
        /* Embedded CSS here */
    </style>
</head>
<body>
    <!-- Generated HTML structure here -->
</body>
</html>
```

If you need additional CSS beyond the embedded styles, provide it after the HTML block:

```css
/* Additional CSS if needed */
```

Focus on creating a professional, visually appealing website that captures the essence and functionality of the original."""

        return prompt
    
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
    
    def _calculate_similarity_score(self, component_result: ComponentDetectionResult, generated_html: str) -> float:
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