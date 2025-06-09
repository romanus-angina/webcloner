import asyncio
import random
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, UTC
import json
import re

from ..config import settings
from ..core.exceptions import LLMError, ConfigurationError
from ..models.components import ComponentDetectionResult, DetectedComponent
from ..models.dom_extraction import DOMExtractionResultModel as DOMExtractionResult
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
                    model="claude-3-5-sonnet-20240620",
                    max_tokens=4096,
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
                    delay = self._calculate_delay(attempt, base_delay=10)
                    logger.info(f"Waiting {delay} seconds before retry...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise LLMError(f"Rate limit exceeded after {self.max_retries + 1} attempts", provider="anthropic")
            
            except anthropic.APIError as e:
                error_message = str(e)
                logger.warning(f"API error on attempt {attempt + 1}: {error_message}")
                
                if "overloaded" in error_message.lower() or "529" in error_message:
                    if attempt < self.max_retries:
                        delay = self._calculate_delay(attempt, base_delay=5)
                        logger.info(f"API overloaded, waiting {delay} seconds before retry...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise LLMError(f"API overloaded after {self.max_retries + 1} attempts", provider="anthropic")
                
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
        
        raise LLMError("Maximum retries exceeded", provider="anthropic")
    
    def _calculate_delay(self, attempt: int, base_delay: Optional[int] = None) -> float:
        """Calculate delay with exponential backoff and jitter."""
        if base_delay is None:
            base_delay = self.base_delay
        delay = base_delay * (2 ** attempt)
        jitter = random.uniform(0.5, 1.5)
        delay *= jitter
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
            prompt = self._build_generation_prompt(
                component_result, dom_result, original_url, quality_level
            )
            
            api_response = await self._make_request_with_retry(prompt)
            
            generated_content = api_response["content"]
            usage = api_response["usage"]
            
            html_content, css_content = self._parse_llm_response(generated_content)
            
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
                "model_used": "claude-3-5-sonnet-20240620",
                "style_analysis_used": True
            }
            
            logger.info(f"Enhanced HTML generation completed: {similarity_score:.1f}% similarity")
            return result
            
        except Exception as e:
            logger.error(f"Enhanced HTML generation failed: {str(e)}", exc_info=True)
            raise LLMError(f"HTML generation failed: {str(e)}", provider="anthropic")
    
    def _build_generation_prompt(
        self,
        component_result: ComponentDetectionResult,
        dom_result: DOMExtractionResult,
        original_url: str,
        quality_level: str
    ) -> str:
        """Build an enhanced prompt with comprehensive style information."""
        
        style_analysis = dom_result.style_analysis
        
        theme_colors = style_analysis.theme
        typography = style_analysis.typography
        css_variables = style_analysis.css_variables
        
        component_summary = self._build_component_summary(component_result)
        
        style_summary = self._build_style_summary(theme_colors, typography, css_variables)
        
        page_info = {
            "title": dom_result.page_structure.title or "Cloned Website",
            "description": dom_result.page_structure.meta_description or "",
            "total_elements": dom_result.total_elements,
            "is_dark_theme": theme_colors.is_dark_theme
        }
        
        quality_instructions = self._get_quality_instructions(quality_level)
        
        prompt = f"""You are an expert web developer tasked with creating a visually identical HTML replica of a website.

    ORIGINAL WEBSITE: {original_url}

    PAGE ANALYSIS:
    - Title: {page_info['title']}
    - Description: {page_info['description']}
    - Theme: {"Dark" if page_info['is_dark_theme'] else "Light"} theme detected

    VISUAL STYLE ANALYSIS:
    {style_summary}

    DETECTED COMPONENTS ({component_result.total_components} total):
    {component_summary}

    {quality_instructions}

    CRITICAL STYLE REQUIREMENTS:
    - Theme Matching: {"Use dark backgrounds and light text." if page_info['is_dark_theme'] else "Use light backgrounds and dark text."}
    - Color Accuracy: Replicate the exact color palette provided.
    - Typography: Strictly use the font families, sizes, and weights defined.
    - Spacing: Visually match the margin and padding patterns.

    OUTPUT FORMAT:
    Provide a single, self-contained HTML file with embedded CSS.
    ```html
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{page_info['title']}</title>
        <style>
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

    Focus on perfect visual replication. The clone should be nearly indistinguishable from the original."""

        return prompt
    
    def _build_style_summary(self, theme_colors, typography, css_variables) -> str:
        """Build a comprehensive style summary for the prompt."""
        summary_parts = []
        
        if theme_colors:
            summary_parts.append("THEME COLORS:")
            if theme_colors.primary_background:
                summary_parts.append(f"- Primary Background: {theme_colors.primary_background}")
            if theme_colors.primary_text:
                summary_parts.append(f"- Primary Text: {theme_colors.primary_text}")
            summary_parts.append("")

        if typography:
            summary_parts.append("TYPOGRAPHY:")
            if typography.body:
                summary_parts.append(f"- Body Font: {typography.body.font_family}, Size: {typography.body.font_size}")
            if typography.h1:
                summary_parts.append(f"- H1 Font: {typography.h1.font_size}, Weight: {typography.h1.font_weight}")
            if typography.h2:
                summary_parts.append(f"- H2 Font: {typography.h2.font_size}, Weight: {typography.h2.font_weight}")
            summary_parts.append("")

        if css_variables:
            summary_parts.append("CSS VARIABLES:")
            for var, value in list(css_variables.items())[:10]:
                summary_parts.append(f"- {var}: {value}")
            summary_parts.append("")
        
        return "\n".join(summary_parts)
    
    def _generate_css_variables(self, css_variables, theme_colors) -> str:
        """Generate CSS custom properties for the theme."""
        variables = []
        if theme_colors.primary_background:
            variables.append(f"    --primary-bg: {theme_colors.primary_background};")
        if theme_colors.primary_text:
            variables.append(f"    --primary-text: {theme_colors.primary_text};")
        for var, value in list(css_variables.items())[:15]:
            variables.append(f"    {var}: {value};")
        return "\n".join(variables)

    def _build_component_summary(self, component_result: ComponentDetectionResult) -> str:
        """Build a detailed summary of detected components for the prompt."""
        if not component_result.components:
            return "No specific components detected. Create a simple, clean layout."
        
        summary_lines = []
        component_counts = {}
        for component in component_result.components:
            comp_type = component.component_type.value
            component_counts[comp_type] = component_counts.get(comp_type, 0) + 1
            label = component.label or f"{comp_type.title()} component"
            summary_lines.append(f"- {comp_type.upper()}: {label}")
        
        count_summary = ", ".join([f"{count} {t}(s)" for t, count in component_counts.items()])
        summary_lines.insert(0, f"Component breakdown: {count_summary}")
        summary_lines.append("")
        return "\n".join(summary_lines)
    
    def _get_quality_instructions(self, quality_level: str) -> str:
        instructions = {
            "fast": "QUALITY LEVEL: FAST\n- Focus on basic structure and functionality.",
            "balanced": "QUALITY LEVEL: BALANCED\n- Balance visual appeal and performance. Match color and typography well.",
            "high": "QUALITY LEVEL: HIGH\n- High attention to visual detail. Strive for pixel-perfect replication."
        }
        return instructions.get(quality_level, instructions["balanced"])
    
    def _parse_llm_response(self, response_text: str) -> tuple[str, Optional[str]]:
        """Parse HTML and CSS from LLM response."""
        html_content = ""
        css_content = None
        
        html_match = re.search(r"```html(.*?)```", response_text, re.DOTALL)
        if html_match:
            html_content = html_match.group(1).strip()
        
        css_match = re.search(r"```css(.*?)```", response_text, re.DOTALL)
        if css_match:
            css_content = css_match.group(1).strip()
        
        if not html_content and not css_match:
             html_content = response_text.strip()
             
        return html_content, css_content
    
    def _calculate_similarity_score(self, component_result: ComponentDetectionResult, dom_result: DOMExtractionResult, generated_html: str) -> float:
        """Calculate a rough similarity score based on component presence."""
        if not component_result.components:
            return 75.0
        
        score = 0.0
        total_components = len(component_result.components)
        
        for component in component_result.components:
            comp_type = component.component_type.value
            if comp_type in generated_html.lower():
                 score +=1
            elif comp_type == "navbar" and "<nav" in generated_html.lower():
                 score += 1
            elif comp_type == "form" and "<form" in generated_html.lower():
                 score += 1

        similarity_percentage = (score / total_components) * 100 if total_components > 0 else 0
        return max(60.0, min(95.0, similarity_percentage))
    
    def _count_replicated_components(self, component_result: ComponentDetectionResult, generated_html: str) -> Dict[str, int]:
        """Count how many components of each type were replicated."""
        replicated = {}
        for component in component_result.components:
            comp_type = component.component_type.value
            if comp_type not in replicated:
                replicated[comp_type] = 0
            if comp_type in generated_html.lower():
                 replicated[comp_type] += 1
        return replicated

# Global LLM service instance
llm_service = LLMService()
