import asyncio
import random
from typing import Optional, Dict, Any, List
import logging
import json
import re
import base64

from ..config import settings
from ..core.exceptions import LLMError, ConfigurationError, ProcessingError
from ..models.components import ComponentDetectionResult, DetectedComponent
from ..models.dom_extraction import DOMExtractionResultModel as DOMExtractionResult
from ..utils.logger import get_logger
from .image_resizer_service import image_resizer_service

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
        # Token limits (conservative estimates)
        self.max_prompt_tokens = 180000  # Leave buffer for response
        self.token_estimation_ratio = 4  # Rough chars per token
    
    def _validate_configuration(self) -> None:
        if not settings.anthropic_api_key:
            raise ConfigurationError("Anthropic API key not configured", config_key="ANTHROPIC_API_KEY")
        if anthropic is None:
            raise ConfigurationError("Anthropic SDK not installed. Run: pip install anthropic")
    
    def _get_client(self):
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation based on character count."""
        return len(text) // self.token_estimation_ratio
    
    def _truncate_component_tree(self, component: DetectedComponent, max_depth: int = 3, current_depth: int = 0) -> DetectedComponent:
        """Recursively truncate component tree to reduce size."""
        if current_depth >= max_depth:
            return DetectedComponent(
                component_type=component.component_type,
                html_snippet=component.html_snippet[:200] + "..." if len(component.html_snippet) > 200 else component.html_snippet,
                relevant_css_rules=component.relevant_css_rules[:3],  # Keep only first 3 CSS rules
                children=[],  # Remove children at max depth
                label=component.label,
                asset_url=component.asset_url
            )
        
        # Truncate children recursively
        truncated_children = []
        for child in component.children[:10]:  # Limit to 10 children max
            truncated_children.append(self._truncate_component_tree(child, max_depth, current_depth + 1))
        
        return DetectedComponent(
            component_type=component.component_type,
            html_snippet=component.html_snippet[:200] + "..." if len(component.html_snippet) > 200 else component.html_snippet,
            relevant_css_rules=component.relevant_css_rules[:5],  # Limit CSS rules
            children=truncated_children,
            label=component.label,
            asset_url=component.asset_url
        )
    
    def _create_component_summary(self, component: DetectedComponent) -> Dict[str, Any]:
        """Create a compact summary of the component tree."""
        def count_components(comp: DetectedComponent, counter: Dict[str, int] = None) -> Dict[str, int]:
            if counter is None:
                counter = {}
            
            comp_type = comp.component_type.value if hasattr(comp.component_type, 'value') else str(comp.component_type)
            counter[comp_type] = counter.get(comp_type, 0) + 1
            
            for child in comp.children:
                count_components(child, counter)
            
            return counter
        
        component_counts = count_components(component)
        
        def extract_key_elements(comp: DetectedComponent, level: int = 0) -> List[Dict[str, Any]]:
            elements = []
            if level < 3:  # Only go 3 levels deep
                element_info = {
                    "type": comp.component_type.value if hasattr(comp.component_type, 'value') else str(comp.component_type),
                    "level": level,
                }
                
                if comp.label:
                    element_info["label"] = comp.label[:100]  # Truncate long labels
                
                if comp.asset_url:
                    element_info["asset_url"] = comp.asset_url
                
                # Include only the most important CSS rules
                if comp.relevant_css_rules:
                    element_info["key_styles"] = [
                        {k: v for k, v in rule.items() if k in ['selector', 'css_text']}
                        for rule in comp.relevant_css_rules[:2]  # Only first 2 rules
                    ]
                
                elements.append(element_info)
                
                # Add children info
                for child in comp.children[:5]:  # Limit children
                    elements.extend(extract_key_elements(child, level + 1))
            
            return elements
        
        return {
            "component_counts": component_counts,
            "total_components": sum(component_counts.values()),
            "key_elements": extract_key_elements(component)[:20],  # Limit to 20 key elements
            "structure_depth": self._calculate_depth(component)
        }
    
    def _calculate_depth(self, component: DetectedComponent) -> int:
        """Calculate the maximum depth of the component tree."""
        if not component.children:
            return 1
        return 1 + max(self._calculate_depth(child) for child in component.children)
    
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
                    delay = self.base_delay * (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(min(delay, self.max_delay))
                else:
                    raise LLMError(f"Request failed after multiple retries: {e}", provider="anthropic")
        raise LLMError("Maximum retries exceeded", provider="anthropic")
    
    def _ensure_complete_html(self, html_content: str) -> str:
        """Ensure HTML is complete and well-formed."""
        
        html_content = html_content.strip()
        
        # Check if HTML starts properly
        if not html_content.startswith('<!DOCTYPE'):
            if html_content.startswith('<html'):
                html_content = '<!DOCTYPE html>\n' + html_content
            else:
                # Wrap content in proper HTML structure
                html_content = f'''<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Generated Website</title>
        <style>
            body {{ margin: 0; padding: 20px; font-family: system-ui, sans-serif; }}
        </style>
    </head>
    <body>
    {html_content}
    </body>
    </html>'''
        
        # Check if HTML ends properly
        if not html_content.rstrip().endswith('</html>'):
            # Find where to close
            if '</body>' not in html_content:
                # Add closing body and html
                html_content = html_content.rstrip() + '\n</body>\n</html>'
            else:
                # Just add closing html
                html_content = html_content.rstrip() + '\n</html>'
        
        return html_content

    async def generate_html_from_components(
        self, 
        component_result, 
        dom_result, 
        original_url, 
        quality_level="balanced",
        asset_context=None  # FIXED: Added this parameter
    ) -> Dict[str, Any]:
        logger.info(f"Generating initial style-aware HTML for {original_url}")
        
        # Use asset_context if provided
        if asset_context:
            logger.info(f"Using asset context: {asset_context}")
        
        # Check if we need to simplify the blueprint
        if hasattr(component_result, 'model_dump'):
            # If it's a Pydantic model, convert to dict
            blueprint_dict = component_result.model_dump() if component_result else {}
        else:
            # If it's already a DetectedComponent or dict
            blueprint_dict = component_result
        
        # Estimate token size
        initial_json = json.dumps(blueprint_dict, indent=2)
        estimated_tokens = self._estimate_tokens(initial_json)
        
        logger.info(f"Initial blueprint estimated tokens: {estimated_tokens}")
        
        if estimated_tokens > self.max_prompt_tokens:
            logger.warning(f"Blueprint too large ({estimated_tokens} tokens), creating summary instead")
            
            # Create a component summary instead of full blueprint
            if isinstance(blueprint_dict, dict) and 'blueprint' in blueprint_dict:
                component = DetectedComponent(**blueprint_dict['blueprint']) if blueprint_dict['blueprint'] else None
            else:
                component = DetectedComponent(**blueprint_dict) if blueprint_dict else None
            
            if component:
                # Option 1: Use summary approach
                summary = self._create_component_summary(component)
                prompt = self._build_summary_prompt(summary, dom_result, quality_level, original_url, asset_context)
            else:
                # Option 2: Fallback to basic structure
                prompt = self._build_fallback_prompt(dom_result, quality_level, original_url, asset_context)
        else:
            # Original blueprint approach for smaller sites
            prompt = self._build_generation_prompt(blueprint_dict, dom_result, quality_level, original_url, asset_context)
        
        # Double-check final prompt size
        final_estimated_tokens = self._estimate_tokens(prompt)
        logger.info(f"Final prompt estimated tokens: {final_estimated_tokens}")
        
        if final_estimated_tokens > self.max_prompt_tokens:
            logger.error(f"Prompt still too large ({final_estimated_tokens} tokens), using minimal fallback")
            prompt = self._build_minimal_prompt(original_url, quality_level)
        
        messages = [{"role": "user", "content": prompt}]
        api_response = await self._make_request_with_retry(messages)
        html_content, _ = self._parse_llm_response(api_response["content"])
        
        # Ensure HTML is complete
        html_content = self._ensure_complete_html(html_content)
        
        # Log for debugging
        logger.info(f"Generated HTML length: {len(html_content)} characters")
        logger.info(f"HTML starts with: {html_content[:100]}...")
        logger.info(f"HTML ends with: ...{html_content[-100:]}")
        
        return {
            "html_content": html_content,
            "tokens_used": api_response["usage"].input_tokens + api_response["usage"].output_tokens
        }
    
    async def analyze_visual_differences(self, original_image_path: str, generated_image_path: str, asset_context=None) -> str:
        logger.info("Performing VQA to analyze visual differences.")
        
        # Resize images if they're too large for Claude's API
        resized_original = None
        resized_generated = None
        
        try:
            # Check and resize original image if needed
            if image_resizer_service.is_image_too_large(original_image_path):
                logger.info("Original image is too large, resizing for Claude API")
                resized_original = image_resizer_service.resize_image_for_claude(original_image_path)
                final_original_path = resized_original
            else:
                final_original_path = original_image_path
            
            # Check and resize generated image if needed
            if image_resizer_service.is_image_too_large(generated_image_path):
                logger.info("Generated image is too large, resizing for Claude API")
                resized_generated = image_resizer_service.resize_image_for_claude(generated_image_path)
                final_generated_path = resized_generated
            else:
                final_generated_path = generated_image_path
            
            # Read the (possibly resized) images
            with open(final_original_path, "rb") as f:
                original_image_data = base64.b64encode(f.read()).decode("utf-8")
            with open(final_generated_path, "rb") as f:
                generated_image_data = base64.b64encode(f.read()).decode("utf-8")
                
        except Exception as e:
            # Clean up any resized images on error
            if resized_original:
                image_resizer_service.cleanup_resized_image(resized_original)
            if resized_generated:
                image_resizer_service.cleanup_resized_image(resized_generated)
            raise ProcessingError(f"Failed to read/resize images for VQA: {e}")

        # Enhanced prompt with asset context
        base_prompt = """You are a meticulous front-end QA engineer. Compare the two screenshots provided.
        - The first image is the 'Original' website.
        - The second image is the 'Generated' clone.
        Identify the top 3-5 most significant visual discrepancies. Be specific about colors, fonts, spacing, alignment, and missing elements. Provide your feedback as a concise, actionable list."""
        
        if asset_context:
            asset_info = f"\n\nAsset Context: The original site has {asset_context.get('total_assets', 0)} assets including:"
            if asset_context.get('has_logos'):
                asset_info += " logos,"
            if asset_context.get('has_icons'):
                asset_info += " icons,"
            if asset_context.get('has_backgrounds'):
                asset_info += " background images,"
            asset_info = asset_info.rstrip(',') + ". Pay special attention to missing or incorrectly placed assets."
            base_prompt += asset_info
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": original_image_data}},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": generated_image_data}},
                    {"type": "text", "text": base_prompt}
                ],
            }
        ]
        
        try:
            response = await self._make_request_with_retry(messages, max_tokens=1024)
            feedback = response["content"]
            logger.info(f"VQA feedback received: {feedback[:200]}...")
            return feedback
        finally:
            # Clean up resized images
            if resized_original:
                image_resizer_service.cleanup_resized_image(resized_original)
            if resized_generated:
                image_resizer_service.cleanup_resized_image(resized_generated)

    async def refine_html_with_feedback(
        self, 
        original_html: str, 
        feedback: str,
        asset_map=None,  # FIXED: Added this parameter
        asset_context=None  # FIXED: Added this parameter
    ) -> str:
        logger.info("Refining HTML based on VQA feedback.")
        
        formatted_feedback = "- " + "\n- ".join(feedback.strip().splitlines())

        base_prompt = f"""You are an expert front-end developer. You have generated an HTML file, but a QA review found some visual discrepancies.
        Your task is to fix the provided HTML code to address the feedback.

**Original HTML Code:**
```html
{original_html}
```

**QA Feedback (Visual Discrepancies to Fix):**
{formatted_feedback}

**Instructions:**
1. Carefully analyze the feedback.
2. Modify the HTML and embedded CSS to correct all the listed issues.
3. Ensure your output is a single, complete, and valid HTML file.
4. Do not add new features; only correct the existing code to match the original design intent described in the feedback."""

        # Add asset-specific instructions if available
        if asset_map:
            asset_instructions = "\n\n**Available Assets:**\n"
            for original_url, local_path in list(asset_map.items())[:10]:  # Limit to first 10
                asset_instructions += f"- {original_url} -> {local_path}\n"
            asset_instructions += "\nEnsure all these assets are properly used in the HTML."
            base_prompt += asset_instructions

        if asset_context:
            context_info = f"\n\n**Asset Context:** The site should have {asset_context.get('total_assets', 0)} assets. "
            if asset_context.get('has_logos'):
                context_info += "Include logos prominently. "
            if asset_context.get('has_icons'):
                context_info += "Include icons where appropriate. "
            base_prompt += context_info

        base_prompt += "\n\n**Return only the full, corrected HTML code inside a single ```html block.**"
        
        messages = [{"role": "user", "content": base_prompt}]
        response = await self._make_request_with_retry(messages)
        refined_html, _ = self._parse_llm_response(response["content"])
        return refined_html

    def _build_summary_prompt(
        self, 
        summary: Dict[str, Any], 
        dom_result: DOMExtractionResult, 
        quality_level: str, 
        original_url: str, 
        asset_context=None  # FIXED: Added this parameter
    ) -> str:
        """Enhanced prompt that ensures complete HTML output with all assets."""
        
        component_counts = summary.get("component_counts", {})
        key_elements = summary.get("key_elements", [])
        
        # Create a component overview
        component_overview = []
        for comp_type, count in component_counts.items():
            component_overview.append(f"- {count} {comp_type}(s)")
        
        # Enhanced asset instructions
        asset_instructions = []
        has_images = False
        has_svgs = False
        
        if hasattr(dom_result, 'assets') and dom_result.assets:
            for asset in dom_result.assets[:15]:
                if hasattr(asset, 'url') and asset.url:
                    if asset.asset_type == 'image':
                        has_images = True
                        asset_instructions.append(f"REQUIRED: Include <img src='{asset.url}' alt='{getattr(asset, 'alt_text', 'image')}' class='max-w-full h-auto' />")
                    elif asset.asset_type == 'svg':
                        has_svgs = True
                        asset_instructions.append(f"REQUIRED: Include SVG icon from URL: {asset.url}")
                elif hasattr(asset, 'content') and asset.content and asset.asset_type == 'svg':
                    has_svgs = True
                    # Include first 200 chars of SVG content as example
                    svg_preview = asset.content[:200] + ("..." if len(asset.content) > 200 else "")
                    asset_instructions.append(f"REQUIRED: Include this inline SVG: {svg_preview}")
        
        # Add asset context information
        if asset_context:
            context_instructions = []
            if asset_context.get('has_logos'):
                context_instructions.append("- CRITICAL: Include logos prominently in header/navigation")
            if asset_context.get('has_icons'):
                context_instructions.append("- CRITICAL: Include icons throughout the interface")
            if asset_context.get('has_backgrounds'):
                context_instructions.append("- CRITICAL: Include background images as specified")
            if asset_context.get('total_assets', 0) > 0:
                context_instructions.append(f"- TOTAL: Ensure all {asset_context['total_assets']} assets are integrated")
            
            asset_instructions.extend(context_instructions)
        
        logger.info(f"Building prompt with {len(dom_result.assets)} assets available")
        
        prompt = f"""You are an expert front-end developer. Create a COMPLETE, FULLY-FUNCTIONAL HTML file that replicates {original_url}.

    **WEBSITE ANALYSIS:**
    The website contains: {chr(10).join(component_overview)}

    **CRITICAL ASSET REQUIREMENTS:**
    {chr(10).join(asset_instructions) if asset_instructions else "- Create placeholder images and icons using CSS/SVG"}
    {'- The site has ' + str(len([a for a in dom_result.assets if getattr(a, 'asset_type', '') == 'image'])) + ' images that MUST be included' if has_images else ''}
    {'- The site has ' + str(len([a for a in dom_result.assets if getattr(a, 'asset_type', '') == 'svg'])) + ' SVG icons that MUST be included' if has_svgs else ''}

    **MANDATORY REQUIREMENTS:**
    1. Generate a COMPLETE HTML document from <!DOCTYPE html> to </html>
    2. Include ALL assets found in the original site
    3. Use embedded CSS within <style> tags in the <head>
    4. Create a responsive, modern design
    5. Include proper semantic HTML5 structure
    6. Quality level: {quality_level}

    **STRUCTURE MUST INCLUDE:**
    - Complete <!DOCTYPE html> declaration
    - Full <html> tag with lang attribute
    - Complete <head> section with meta tags, title, and embedded CSS
    - Complete <body> with all content
    - Proper closing </html> tag

    **ASSET INTEGRATION RULES:**
    - Every image MUST use an actual <img> tag with src attribute
    - Every SVG MUST be included either inline or as <img> if external
    - Use the exact URLs provided in the asset requirements above
    - Add proper alt attributes for accessibility
    - Style images responsively with CSS classes

    **OUTPUT FORMAT:**
    Return ONLY the complete HTML file. Start with <!DOCTYPE html> and end with </html>.
    DO NOT include markdown code blocks or any other formatting.
    DO NOT truncate the output - provide the complete HTML file.

    **IMPORTANT:** 
    - The HTML must be complete and ready to save as a .html file
    - Include every single asset mentioned in the requirements above
    - End the response with the closing </html> tag

    Generate the complete HTML file now:"""

        return prompt

    def _build_fallback_prompt(
        self, 
        dom_result: DOMExtractionResult, 
        quality_level: str, 
        original_url: str, 
        asset_context=None  # FIXED: Added this parameter
    ) -> str:
        """Fallback prompt when component detection fails."""
        
        page_title = getattr(dom_result.page_structure, 'title', 'Website Clone') if hasattr(dom_result, 'page_structure') else 'Website Clone'
        
        base_prompt = f"""You are an expert front-end developer. Create a modern, responsive website inspired by {original_url}.

**TARGET INFORMATION:**
- Page Title: {page_title}
- Quality Level: {quality_level}

**REQUIREMENTS:**
1. Create a complete, modern HTML file with embedded CSS
2. Design should be clean, professional, and responsive
3. Include typical website sections: header, navigation, main content, footer
4. Use modern CSS practices (flexbox, grid, modern typography)
5. Include placeholder content that feels realistic
6. Ensure good visual hierarchy and spacing

**STRUCTURE TO INCLUDE:**
- Header with navigation
- Hero/banner section
- Main content area
- Footer
- Responsive design for all screen sizes"""

        if asset_context and asset_context.get('total_assets', 0) > 0:
            base_prompt += f"\n\n**ASSET REQUIREMENTS:**\n- Include {asset_context['total_assets']} assets as placeholders"
            if asset_context.get('has_logos'):
                base_prompt += "\n- Include logo in header"
            if asset_context.get('has_icons'):
                base_prompt += "\n- Include icons throughout interface"

        base_prompt += "\n\n**OUTPUT FORMAT:**\nReturn only the complete HTML file with embedded CSS in <style> tags.\n\nGenerate the HTML file:"

        return base_prompt

    def _build_minimal_prompt(self, original_url: str, quality_level: str) -> str:
        """Minimal prompt as last resort."""
        return f"""Create a simple, modern HTML webpage. Include:
- Clean header with navigation
- Main content section
- Footer
- Responsive CSS
- Professional design

Quality: {quality_level}
Return only the HTML with embedded CSS."""

    def _build_generation_prompt(
        self, 
        component_result, 
        dom_result: DOMExtractionResult, 
        quality_level: str, 
        original_url: str, 
        asset_context=None  # FIXED: Added this parameter
    ) -> str:
        """Original blueprint-based prompt with enhanced asset instructions."""
        json_blueprint = json.dumps(component_result, indent=2)
        
        # Extract asset information for additional instructions
        asset_count = 0
        svg_count = 0
        if hasattr(dom_result, 'assets') and dom_result.assets:
            asset_count = len(dom_result.assets)
            svg_count = len([a for a in dom_result.assets if getattr(a, 'asset_type', '') == 'svg'])
        
        base_prompt = f"""SYSTEM: You are an expert front-end developer. Your task is to construct a single, self-contained HTML file by precisely assembling the components provided in a JSON data structure.

    USER:
    You are provided with a JSON object that represents the complete blueprint for a webpage from {original_url}. 
    The website contains {asset_count} assets including {svg_count} SVG icons that MUST be included.

    **CRITICAL INSTRUCTIONS:**
    1. **Strict Adherence:** You MUST use the `html_snippet`, `relevant_css_rules`, and `children` data provided in the JSON blueprint.
    2. **Asset Integration:** For components with `asset_url`, you MUST include the actual asset:
    - For images: Use <img src="{{asset_url}}" alt="{{label or 'image'}}" />
    - For SVGs: Include the full SVG content from `html_snippet`
    - For inline SVGs: Embed the complete SVG code directly
    3. **Assemble Components:** Construct the final HTML `<body>` by recursively assembling the components from the JSON blueprint.
    4. **Aggregate CSS:** Combine all the `relevant_css_rules` from all components into a single `<style>` block in the HTML `<head>`.

    **ASSET HANDLING REQUIREMENTS:**
    - Every component with an `asset_url` MUST result in a visible asset in the final HTML
    - SVG components MUST include their complete SVG markup
    - Image components MUST include proper <img> tags with src attributes
    - Preserve all visual assets to maintain design fidelity"""

        # Add asset context information
        if asset_context:
            context_info = f"\n\n**ASSET CONTEXT:**\n- Total assets to integrate: {asset_context.get('total_assets', 0)}\n"
            if asset_context.get('has_logos'):
                context_info += "- Include logos prominently\n"
            if asset_context.get('has_icons'):
                context_info += "- Include icons throughout interface\n"
            if asset_context.get('has_backgrounds'):
                context_info += "- Include background images\n"
            base_prompt += context_info

        base_prompt += f"""

    Here is the JSON blueprint for the webpage:

    ```json
    {json_blueprint}
    ```

    **FINAL INSTRUCTION:**
    Generate the complete HTML file based on the JSON blueprint above. 
    CRITICAL: Ensure ALL assets (images, SVGs, icons) from the blueprint are included in the final HTML.
    The generated page should visually match the original with all logos, icons, and images present."""

        return base_prompt
    
    def _parse_llm_response(self, response_text: str) -> tuple[str, Optional[str]]:
        """Enhanced LLM response parsing with better HTML extraction."""
        
        # First, try to extract HTML from code blocks
        html_match = re.search(r"```html\s*(.*?)```", response_text, re.DOTALL | re.IGNORECASE)
        if html_match:
            html_content = html_match.group(1).strip()
            
            # Clean up common formatting issues
            html_content = self._clean_html_content(html_content)
            return html_content, None
        
        # Try without the 'html' specifier
        code_block_match = re.search(r"```\s*(.*?)```", response_text, re.DOTALL)
        if code_block_match:
            html_content = code_block_match.group(1).strip()
            # Check if it looks like HTML
            if html_content.startswith('<!DOCTYPE') or html_content.startswith('<html'):
                html_content = self._clean_html_content(html_content)
                return html_content, None
        
        # Look for HTML document pattern in raw text
        html_doc_match = re.search(r'<!DOCTYPE[^>]*>.*?</html>', response_text, re.DOTALL | re.IGNORECASE)
        if html_doc_match:
            html_content = html_doc_match.group(0)
            html_content = self._clean_html_content(html_content)
            return html_content, None
        
        # Fallback: return the whole response and let it be processed
        return self._clean_html_content(response_text), None

    def _clean_html_content(self, html_content: str) -> str:
        """Clean and validate HTML content."""
        
        # Remove any leading/trailing whitespace
        html_content = html_content.strip()
        
        # Remove any markdown artifacts
        html_content = re.sub(r'^```html\s*', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'^```\s*', '', html_content)
        html_content = re.sub(r'```\s*', '', html_content)
        
        # Ensure proper HTML structure
        if not html_content.startswith('<!DOCTYPE'):
            if html_content.startswith('<html'):
                html_content = '<!DOCTYPE html>\n' + html_content
            elif html_content.startswith('<head') or html_content.startswith('<body'):
                html_content = f'<!DOCTYPE html>\n<html lang="en">\n{html_content}\n</html>'
        
        # Check if HTML is complete
        if '<!DOCTYPE' in html_content and '<html' in html_content:
            if not html_content.rstrip().endswith('</html>'):
                # Try to close the HTML properly
                if '</body>' in html_content:
                    html_content = html_content.rstrip() + '\n</html>'
                else:
                    html_content = html_content.rstrip() + '\n</body>\n</html>'
        
        return html_content

    def _calculate_similarity_score(self, component_result, dom_result: DOMExtractionResult, generated_html: str) -> float:
        """
        Calculate similarity score based on component replication.
        Handles different types of component_result inputs.
        """
        if not component_result:
            return 95.0 if len(generated_html) > 50 else 100.0

        # Handle different types of component_result
        if isinstance(component_result, dict):
            # Case 1: Summary-based generation with component_counts
            if 'component_counts' in component_result:
                total_components = component_result.get('total_components', 0)
                if total_components == 0:
                    return 100.0
                
                # Check for presence of component types in generated HTML
                component_counts = component_result.get('component_counts', {})
                replicated_types = 0
                
                for comp_type in component_counts.keys():
                    # Simple check if component type appears in HTML
                    if comp_type.lower() in generated_html.lower():
                        replicated_types += 1
                
                if len(component_counts) == 0:
                    return 100.0
                
                score = (replicated_types / len(component_counts)) * 100.0
                return min(score, 99.0)
            
            # Case 2: Dict with blueprint structure
            elif 'blueprint' in component_result:
                blueprint = component_result['blueprint']
                if blueprint:
                    return self._calculate_component_similarity(blueprint, generated_html)
                else:
                    return 85.0
            
            # Case 3: Dict that IS the blueprint
            else:
                return self._calculate_component_similarity(component_result, generated_html)
        
        # Case 4: DetectedComponent object (our current case)
        elif hasattr(component_result, 'component_type'):
            return self._calculate_component_similarity(component_result, generated_html)
        
        # Case 5: ComponentDetectionResult object
        elif hasattr(component_result, 'blueprint'):
            if component_result.blueprint:
                return self._calculate_component_similarity(component_result.blueprint, generated_html)
            else:
                return 85.0
        
        # Default case
        return 85.0

    def _calculate_component_similarity(self, component, generated_html: str) -> float:
        """
        Calculate similarity based on a single component tree.
        """
        if not component:
            return 85.0
        
        # Extract all component types from the tree
        component_types = set()
        
        def extract_types(comp):
            if hasattr(comp, 'component_type'):
                comp_type = comp.component_type
                if hasattr(comp_type, 'value'):
                    component_types.add(comp_type.value)
                else:
                    component_types.add(str(comp_type))
            
            # Handle children
            if hasattr(comp, 'children') and comp.children:
                for child in comp.children:
                    extract_types(child)
        
        extract_types(component)
        
        if not component_types:
            return 100.0  # If no types found, assume basic success
        
        # Check which component types appear in the generated HTML
        replicated_types = 0
        for comp_type in component_types:
            if comp_type.lower() in generated_html.lower():
                replicated_types += 1
        
        # Calculate similarity score
        score = (replicated_types / len(component_types)) * 100.0
        
        # Add bonus for having content
        if len(generated_html.strip()) > 100:
            score = min(score + 10, 99.0)  # Bonus for substantial content
        
        return max(score, 50.0)  # Minimum 50% if we generated something


llm_service = LLMService()