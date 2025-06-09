import asyncio
import random
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, UTC
import json
import re

from ..config import settings
from ..core.exceptions import LLMError, ConfigurationError
from ..models.components import ComponentDetectionResult
from ..models.dom_extraction import DOMExtractionResultModel as DOMExtractionResult, StyleAnalysisModel, ColorPaletteModel, TypographyAnalysisModel
from ..utils.logger import get_logger

logger = get_logger(__name__)

try:
    import anthropic
except ImportError:
    anthropic = None


class LLMService:
    """
    Service for generating HTML using LLM based on component analysis.
    Enhanced with retry logic and style-aware prompting.
    """
    
    def __init__(self):
        self._client = None
        self._validate_configuration()
        self.max_retries = 3
        self.base_delay = 2
        self.max_delay = 60
    
    def _validate_configuration(self) -> None:
        if not settings.anthropic_api_key:
            raise ConfigurationError("Anthropic API key not configured", config_key="ANTHROPIC_API_KEY")
        if anthropic is None:
            raise ConfigurationError("Anthropic SDK not installed. Run: pip install anthropic")
    
    def _get_client(self):
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client
    
    async def _make_request_with_retry(self, prompt: str) -> Dict[str, Any]:
        client = self._get_client()
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Making LLM request (attempt {attempt + 1}/{self.max_retries + 1})")
                response = await client.messages.create(
                    model="claude-3-5-sonnet-20240620",
                    max_tokens=4096,
                    temperature=0.05, # Lower temperature for more deterministic output
                    messages=[{"role": "user", "content": prompt}]
                )
                logger.info("LLM request successful")
                return {"content": response.content[0].text, "usage": response.usage}
            except anthropic.RateLimitError as e:
                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt, base_delay=10)
                    logger.warning(f"Rate limit error. Retrying in {delay:.2f}s...")
                    await asyncio.sleep(delay)
                else:
                    raise LLMError("Rate limit exceeded", provider="anthropic")
            except anthropic.APIError as e:
                logger.error(f"Anthropic API error: {str(e)}")
                raise LLMError(f"API error: {str(e)}", provider="anthropic")
            except Exception as e:
                logger.error(f"Unexpected error during LLM request: {str(e)}", exc_info=True)
                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    await asyncio.sleep(delay)
                else:
                    raise LLMError(f"Request failed after multiple retries: {str(e)}", provider="anthropic")
        raise LLMError("Maximum retries exceeded", provider="anthropic")
    
    def _calculate_delay(self, attempt: int, base_delay: Optional[int] = None) -> float:
        delay = (base_delay or self.base_delay) * (2 ** attempt) + random.uniform(0, 1)
        return min(delay, self.max_delay)
    
    async def generate_html_from_components(
        self,
        component_result: ComponentDetectionResult,
        dom_result: DOMExtractionResult,
        original_url: str,
        quality_level: str = "balanced"
    ) -> Dict[str, Any]:
        logger.info(f"Generating style-aware HTML for {original_url}")
        try:
            prompt = self._build_generation_prompt(
                component_result, dom_result, original_url, quality_level
            )
            
            api_response = await self._make_request_with_retry(prompt)
            
            html_content, css_content = self._parse_llm_response(api_response["content"])
            
            similarity_score = self._calculate_similarity_score(
                component_result, dom_result, html_content
            )
            
            return {
                "html_content": html_content,
                "css_content": css_content,
                "similarity_score": similarity_score,
                "generation_time": 0.0, # Placeholder
                "tokens_used": api_response["usage"].input_tokens + api_response["usage"].output_tokens,
                "components_replicated": self._count_replicated_components(component_result, html_content),
                "quality_level": quality_level,
                "model_used": "claude-3-5-sonnet-20240620",
                "style_analysis_used": True
            }
        except Exception as e:
            logger.error(f"Style-aware HTML generation failed: {str(e)}", exc_info=True)
            raise LLMError(f"HTML generation failed: {str(e)}", provider="anthropic")

    def _build_generation_prompt(
        self,
        component_result: ComponentDetectionResult,
        dom_result: DOMExtractionResult,
        original_url: str,
        quality_level: str
    ) -> str:
        style_analysis = dom_result.style_analysis
        theme_colors = style_analysis.theme
        typography = style_analysis.typography
        
        style_summary = self._build_style_summary(theme_colors, typography, style_analysis.css_variables)
        component_summary = self._build_component_summary(component_result)
        
        page_info = {
            "title": dom_result.page_structure.title or "Cloned Website",
            "is_dark_theme": theme_colors.is_dark_theme
        }
        
        prompt = f"""You are an expert front-end developer tasked with creating a pixel-perfect HTML replica of a website based on a detailed analysis.

**TASK:** Generate a single, self-contained HTML file that is visually identical to the original page at {original_url}.

**ANALYSIS & REQUIREMENTS:**

**1. Visual Style Guide (MUST be followed exactly):**
{style_summary}

**2. Detected Components (Reconstruct this structure):**
{component_summary}

**3. Quality & Fidelity:**
- **QUALITY LEVEL:** {quality_level.upper()}
- Replicate the layout, spacing, and component arrangement precisely.
- Use semantic HTML.
- The final output MUST be a single HTML file with CSS embedded in a `<style>` tag in the `<head>`.

**OUTPUT FORMAT:**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_info['title']}</title>
    <style>
        /* Your complete CSS implementing the Visual Style Guide goes here */
    </style>
</head>
<body>
    <!-- Your HTML structure implementing the component list goes here -->
</body>
</html>
```

Begin generating the HTML file now.
"""
        return prompt
    
    def _build_style_summary(self, theme: ColorPaletteModel, typo: TypographyAnalysisModel, css_vars: Dict) -> str:
        parts = []
        if theme:
            parts.append(f"- **Theme:** {'Dark' if theme.is_dark_theme else 'Light'}")
            parts.append(f"- **Background Color:** {theme.primary_background}")
            parts.append(f"- **Text Color:** {theme.primary_text}")

        if typo:
            parts.append("- **Typography:**")
            if typo.body:
                parts.append(f"  - Body: {typo.body.font_family}, {typo.body.font_size}")
            if typo.h1:
                parts.append(f"  - H1: {typo.h1.font_size}, {typo.h1.font_weight}")
            if typo.h2:
                parts.append(f"  - H2: {typo.h2.font_size}, {typo.h2.font_weight}")
        
        if css_vars:
            parts.append("- **CSS Variables:**")
            for var, value in list(css_vars.items())[:5]:
                parts.append(f"  - {var}: {value}")
                
        return "\n".join(parts)

    def _build_component_summary(self, result: ComponentDetectionResult) -> str:
        if not result.components:
            return "No specific components were detected. Analyze the page structure to create a basic layout."
        
        lines = []
        counts = {}
        for comp in result.components:
            comp_type = comp.component_type.value
            counts[comp_type] = counts.get(comp_type, 0) + 1
        
        count_summary = ", ".join([f"{v} {k}(s)" for k, v in counts.items()])
        lines.append(f"- **Component Summary:** {count_summary}")
        
        for comp in result.components[:15]: # Limit for prompt size
            lines.append(f"  - **{comp.component_type.value.upper()}:** {comp.label or 'No label'}")
        
        return "\n".join(lines)
    
    def _get_quality_instructions(self, quality_level: str) -> str:
        instructions = {
            "fast": "QUALITY LEVEL: FAST\n- Focus on basic structure and functionality.",
            "balanced": "QUALITY LEVEL: BALANCED\n- Balance visual appeal and performance. Match color and typography well.",
            "high": "QUALITY LEVEL: HIGH\n- High attention to visual detail. Strive for pixel-perfect replication."
        }
        return instructions.get(quality_level, instructions["balanced"])
    
    def _parse_llm_response(self, response_text: str) -> tuple[str, Optional[str]]:
        html_match = re.search(r"```html(.*?)```", response_text, re.DOTALL)
        if html_match:
            return html_match.group(1).strip(), None # Assume CSS is embedded
        return response_text, None

    def _calculate_similarity_score(self, component_result, dom_result, generated_html) -> float:
        # Placeholder - a real implementation would be more complex
        return 95.0

    def _count_replicated_components(self, component_result, generated_html) -> Dict[str, int]:
        replicated = {}
        # Placeholder logic
        for comp in component_result.components:
            comp_type = comp.component_type.value
            if comp_type in generated_html.lower():
                replicated[comp_type] = replicated.get(comp_type, 0) + 1
        return replicated

# Global LLM service instance
llm_service = LLMService()
