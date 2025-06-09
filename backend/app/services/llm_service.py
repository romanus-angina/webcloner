import asyncio
import random
from typing import Optional, Dict, Any, List
import logging
import json
import re
import base64

from ..config import settings
from ..core.exceptions import LLMError, ConfigurationError, ProcessingError
from ..models.components import ComponentDetectionResult
from ..models.dom_extraction import DOMExtractionResultModel as DOMExtractionResult, StyleAnalysisModel, ColorPaletteModel, TypographyAnalysisModel
from ..utils.logger import get_logger

logger = get_logger(__name__)

try:
    import anthropic
except ImportError:
    anthropic = None

class LLMService:
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
    
    def _calculate_delay(self, attempt: int, base_delay: Optional[int] = None) -> float:
        delay = (base_delay or self.base_delay) * (2 ** attempt) + random.uniform(0, 1)
        return min(delay, self.max_delay)

    async def _make_request_with_retry(self, messages: List[Dict], model: str = "claude-sonnet-4-20250514", max_tokens: int = 4096) -> Dict[str, Any]:
        client = self._get_client()
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Making LLM request to {model} (attempt {attempt + 1})")
                response = await client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=messages
                )
                logger.info("LLM request successful")
                return {"content": response.content[0].text, "usage": response.usage}
            except Exception as e:
                logger.error(f"LLM request failed: {e}", exc_info=True)
                if attempt < self.max_retries:
                    await asyncio.sleep(self._calculate_delay(attempt))
                else:
                    raise LLMError(f"Request failed after multiple retries: {e}", provider="anthropic")
        raise LLMError("Maximum retries exceeded", provider="anthropic")

    async def generate_html_from_components(self, component_result, dom_result, original_url, quality_level="balanced") -> Dict[str, Any]:
        logger.info(f"Generating initial style-aware HTML for {original_url}")
        prompt = self._build_generation_prompt(component_result, dom_result, quality_level, original_url)
        messages = [{"role": "user", "content": prompt}]
        api_response = await self._make_request_with_retry(messages)
        html_content, _ = self._parse_llm_response(api_response["content"])
        return {
            "html_content": html_content,
            "tokens_used": api_response["usage"].input_tokens + api_response["usage"].output_tokens
        }

    async def analyze_visual_differences(self, original_image_path: str, generated_image_path: str) -> str:
        logger.info("Performing VQA to analyze visual differences.")
        try:
            with open(original_image_path, "rb") as f:
                original_image_data = base64.b64encode(f.read()).decode("utf-8")
            with open(generated_image_path, "rb") as f:
                generated_image_data = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            raise ProcessingError(f"Failed to read images for VQA: {e}")

        prompt = """You are a meticulous front-end QA engineer. Compare the two screenshots provided.
        - The first image is the 'Original' website.
        - The second image is the 'Generated' clone.
        Identify the top 3-5 most significant visual discrepancies. Be specific about colors, fonts, spacing, alignment, and missing elements. Provide your feedback as a concise, actionable list."""
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": original_image_data}},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": generated_image_data}},
                    {"type": "text", "text": prompt}
                ],
            }
        ]
        
        response = await self._make_request_with_retry(messages, max_tokens=1024)
        feedback = response["content"]
        logger.info(f"VQA feedback received: {feedback[:200]}...")
        return feedback

    async def refine_html_with_feedback(self, original_html: str, feedback: str) -> str:
        logger.info("Refining HTML based on VQA feedback.")
        
        formatted_feedback = "- " + "\n- ".join(feedback.strip().splitlines())

        prompt = f"""You are an expert front-end developer. You have generated an HTML file, but a QA review found some visual discrepancies.
        Your task is to fix the provided HTML code to address the feedback.

**Original HTML Code:**
```html
{original_html}
```

**QA Feedback (Visual Discrepancies to Fix):**
{formatted_feedback}

**Instructions:**
1.  Carefully analyze the feedback.
2.  Modify the HTML and embedded CSS to correct all the listed issues.
3.  Ensure your output is a single, complete, and valid HTML file.
4.  Do not add new features; only correct the existing code to match the original design intent described in the feedback.

**Return only the full, corrected HTML code inside a single ```html block.**"""
        
        messages = [{"role": "user", "content": prompt}]
        response = await self._make_request_with_retry(messages)
        refined_html, _ = self._parse_llm_response(response["content"])
        return refined_html

    def _build_generation_prompt(
        self,
        component_result: ComponentDetectionResult, # This will now contain the full blueprint
        dom_result: DOMExtractionResult,
        quality_level: str,
        original_url: str
    ) -> str:
        """
        Builds the final, prescriptive prompt for the LLM using the structured JSON blueprint.
        """
        # The new dom_extractor script directly returns the blueprint.
        # The component_result now holds this blueprint.
        # We need to serialize it to a JSON string for the prompt.
        json_blueprint = json.dumps(component_result, indent=2)

        # The System and User prompt as you designed it.
        prompt = f"""
SYSTEM: You are an expert front-end developer. Your sole task is to construct a single, self-contained HTML file by precisely assembling the components provided in a JSON data structure. You must follow all instructions without deviation.

USER:
You are provided with a JSON object that represents the complete blueprint for a webpage. Your task is to generate a single HTML file based on this blueprint.

**Instructions:**
1.  **Strict Adherence:** You MUST use the `html_snippet`, `relevant_css_rules`, and `children` data provided in the JSON blueprint. Do not invent your own HTML or CSS.
2.  **Assemble Components:** Construct the final HTML `<body>` by recursively assembling the components from the JSON blueprint.
3.  **Aggregate CSS:** Combine all the `relevant_css_rules` from all components into a single `<style>` block in the HTML `<head>`.
4.  **Handle Assets:** For components of type `IMAGE` or `SVG`, use their `html_snippet` directly. For `IMAGE` components with an `asset_url`, use that URL in the `src` attribute. Another system will handle making these links work.

Here is the JSON blueprint for the webpage:

```json
{json_blueprint}

**FINAL INSTRUCTION:**
Generate the complete HTML file based on the  json blueprint above.
"""
        return prompt
    
    def _build_style_summary(self, theme: ColorPaletteModel, typo: TypographyAnalysisModel, css_vars: Dict) -> str:
        parts = [
            f"- **Theme:** {'Dark' if theme.is_dark_theme else 'Light'}",
            f"- **Primary Background:** {theme.primary_background}",
            f"- **Primary Text:** {theme.primary_text}"
        ]

        if typo and typo.body and typo.body.font_family:
            parts.append("- **Typography:**")
            parts.append(f"  - Body: {typo.body.font_family}, {typo.body.font_size}")
            if typo.h1 and typo.h1.font_size:
                parts.append(f"  - H1: {typo.h1.font_size}, {typo.h1.font_weight}")
            if typo.h2 and typo.h2.font_size:
                parts.append(f"  - H2: {typo.h2.font_size}, {typo.h2.font_weight}")
        
        return "\n".join(parts)

    def _generate_css_variables(self, css_vars: Dict, theme: ColorPaletteModel) -> str:
        variables = []
        if theme.primary_background:
            variables.append(f"    --primary-bg: {theme.primary_background};")
        if theme.primary_text:
            variables.append(f"    --primary-text: {theme.primary_text};")
        
        return "\n".join(variables)

    def _build_component_summary(self, component_result: ComponentDetectionResult, dom_result: DOMExtractionResult) -> str:
        """Builds a summary of components and an asset manifest for the LLM."""
        if not component_result.components and not dom_result.assets:
            return "No specific components or assets were detected. Create a basic layout based on the page structure."

        lines = []
        
        # Create a manifest of available assets
        if dom_result.assets:
            lines.append("- **Asset Manifest (Use these files):**")
            for asset in dom_result.assets[:15]: # Limit for prompt size
                if asset.content: # Inline SVG
                    lines.append(f"  - Inline SVG (identifier: {asset.alt_text}): Use this content directly -> {asset.content}")
                elif asset.url: # External Image
                    # NOTE: We will tell the LLM to use the ORIGINAL URL. Our rewriter will handle replacement.
                    lines.append(f"  - Image: {asset.url} (alt: {asset.alt_text or 'image'})")
            lines.append("\n")


        if component_result.components:
            counts = {}
            for comp in component_result.components:
                comp_type = comp.component_type.value
                counts[comp_type] = counts.get(comp_type, 0) + 1
            
            count_summary = ", ".join([f"{v} {k}(s)" for k, v in counts.items()])
            lines.append(f"- **Component Summary:** {count_summary}")
            
            for comp in component_result.components[:15]:
                lines.append(f"  - **{comp.component_type.value.upper()}:** {comp.label or 'No label'}")
        
        return "\n".join(lines)
    
    def _parse_llm_response(self, response_text: str) -> tuple[str, Optional[str]]:
        html_match = re.search(r"```html(.*?)```", response_text, re.DOTALL)
        if html_match:
            return html_match.group(1).strip(), None
        return response_text, None

    def _calculate_similarity_score(self, component_result: ComponentDetectionResult, dom_result: DOMExtractionResult, generated_html: str) -> float:
        """
        Calculates a more accurate similarity score based on the replication of detected component types.
        The score is the percentage of unique component types from the original page
        that are found in the generated HTML.
        """
        if not component_result.components:
            # If there were no components to detect, we can assume it was a simple page.
            return 95.0 if len(generated_html) > 50 else 100.0

        # Get the set of unique component types that were detected in the original DOM
        original_types = {comp.component_type.value for comp in component_result.components}
        if not original_types:
            return 100.0

        replicated_types = set()
        # Check which of the original components appear to be in the generated HTML.
        # This check is basic and looks for the component's label within the generated code.
        for component in component_result.components:
            # A component is considered replicated if its label appears in the generated code
            if component.label and component.label.lower() in generated_html.lower():
                replicated_types.add(component.component_type.value)

        # Calculate the score based on the ratio of replicated types to original types
        score = (len(replicated_types) / len(original_types)) * 100.0
        
        # Cap the score at 99.0 to be more realistic, as a perfect 100% clone is rare.
        return min(score, 99.0)

    def _count_replicated_components(self, component_result, generated_html) -> Dict[str, int]:
        replicated = {}
        for comp in component_result.components:
            comp_type = comp.component_type.value
            if comp.label and comp.label.lower() in generated_html.lower():
                replicated[comp_type] = replicated.get(comp_type, 0) + 1
        return replicated

llm_service = LLMService()
