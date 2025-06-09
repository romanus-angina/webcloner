from typing import Dict, List, Optional, Any, Set, Tuple
import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urljoin, urlparse
import re
import time

from ..config import settings
from ..core.exceptions import (
    BrowserError,
    ProcessingError,
    NetworkError
)
from ..utils.logger import get_logger
from .browser_manager import BrowserManager

logger = get_logger(__name__)


@dataclass
class ExtractedElement:
    """Represents an extracted DOM element with computed styles."""
    tag_name: str
    element_id: Optional[str] = None
    class_names: List[str] = None
    computed_styles: Dict[str, str] = None
    attributes: Dict[str, str] = None
    text_content: Optional[str] = None
    children_count: int = 0
    xpath: Optional[str] = None
    bounding_box: Optional[Dict[str, float]] = None
    is_visible: bool = True
    z_index: Optional[int] = None
    
    def __post_init__(self):
        if self.class_names is None:
            self.class_names = []
        if self.computed_styles is None:
            self.computed_styles = {}
        if self.attributes is None:
            self.attributes = {}


@dataclass
class ExtractedStylesheet:
    """Represents an extracted stylesheet."""
    href: Optional[str] = None
    media: str = "all"
    rules: List[Dict[str, Any]] = None
    inline: bool = False
    content: Optional[str] = None
    
    def __post_init__(self):
        if self.rules is None:
            self.rules = []


@dataclass
class ExtractedAsset:
    """Represents an extracted asset (image, font, etc.)."""
    url: str
    asset_type: str  # 'image', 'font', 'video', 'audio', 'icon'
    mime_type: Optional[str] = None
    size: Optional[int] = None
    dimensions: Optional[Tuple[int, int]] = None
    alt_text: Optional[str] = None
    is_background: bool = False
    usage_context: List[str] = None
    
    def __post_init__(self):
        if self.usage_context is None:
            self.usage_context = []


@dataclass
class PageStructure:
    """Represents the overall page structure and metadata."""
    title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None
    lang: Optional[str] = None
    charset: Optional[str] = None
    viewport: Optional[str] = None
    favicon_url: Optional[str] = None
    canonical_url: Optional[str] = None
    open_graph: Dict[str, str] = None
    schema_org: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.open_graph is None:
            self.open_graph = {}
        if self.schema_org is None:
            self.schema_org = []


@dataclass
class DOMExtractionResult:
    """Complete DOM extraction result."""
    url: str
    session_id: str
    timestamp: float
    extraction_time: float
    
    # Core structure
    page_structure: PageStructure
    elements: List[ExtractedElement]
    stylesheets: List[ExtractedStylesheet]
    assets: List[ExtractedAsset]
    
    # Analysis data
    layout_analysis: Dict[str, Any]
    color_palette: List[str]
    font_families: List[str]
    responsive_breakpoints: List[int]
    
    # Technical metrics
    dom_depth: int = 0
    total_elements: int = 0
    total_stylesheets: int = 0
    total_assets: int = 0
    success: bool = True
    error_message: Optional[str] = None


class DOMExtractionService:
    """
    Service for extracting DOM structure, styles, and assets from web pages.
    
    Provides comprehensive analysis of page structure, computed styles,
    layout information, and asset discovery for website cloning.
    """
    
    def __init__(self, browser_manager: Optional[BrowserManager] = None):
        self.browser_manager = browser_manager
        self._javascript_extractors = self._load_extraction_scripts()
    
    def _load_extraction_scripts(self) -> Dict[str, str]:
        """Load JavaScript extraction scripts."""
        return {
            "dom_extractor": self._get_dom_extractor_script(),
            "style_extractor": self._get_style_extractor_script(),
            "asset_extractor": self._get_asset_extractor_script(),
            "layout_analyzer": self._get_layout_analyzer_script()
        }

    def _get_dom_extractor_script(self) -> str:
        """Clean DOM extraction script for production use."""
        return """
        (() => {
            function extractAllElements() {
                const elements = [];
                const allNodes = document.querySelectorAll('*');

                for (let i = 0; i < allNodes.length; i++) {
                    const element = allNodes[i];
                    
                    try {
                        const tagName = element.tagName.toLowerCase();
                        
                        // Skip only script and style tags
                        if (tagName === 'script' || tagName === 'style') {
                            continue;
                        }
                        
                        // Extract attributes safely
                        const attributes = {};
                        if (element.attributes) {
                            for (let j = 0; j < element.attributes.length; j++) {
                                const attr = element.attributes[j];
                                if (attr && attr.name && attr.value !== undefined) {
                                    attributes[attr.name] = attr.value;
                                }
                            }
                        }
                        
                        // Extract text content (direct text only, not nested)
                        let textContent = '';
                        if (element.childNodes) {
                            for (let k = 0; k < element.childNodes.length; k++) {
                                const node = element.childNodes[k];
                                if (node && node.nodeType === 3 && node.textContent) {
                                    textContent += node.textContent;
                                }
                            }
                        }
                        textContent = textContent.trim();
                        
                        // Extract classes
                        const classNames = [];
                        if (element.className && typeof element.className === 'string') {
                            const classes = element.className.trim();
                            if (classes) {
                                classNames.push(...classes.split(/\\s+/).filter(cls => cls.length > 0));
                            }
                        }
                        
                        // Get computed styles
                        const computedStyles = {
                            'display': 'block',
                            'box-shadow': 'none',
                            'border': 'none',
                            'padding': '0px'
                        };
                        
                        try {
                            const style = window.getComputedStyle(element);
                            if (style) {
                                computedStyles['display'] = style.display || 'block';
                                computedStyles['box-shadow'] = style.boxShadow || 'none';
                                computedStyles['border'] = style.border || 'none';
                                computedStyles['padding'] = style.padding || '0px';
                            }
                        } catch (e) {
                            // Use defaults if getComputedStyle fails
                        }

                        // Create element data
                        const elementData = {
                            tag_name: tagName,
                            element_id: element.id || null,
                            class_names: classNames,
                            computed_styles: computedStyles,
                            attributes: attributes,
                            text_content: textContent || null,
                            children_count: element.children ? element.children.length : 0,
                            xpath: null,
                            bounding_box: null,
                            is_visible: true,
                            z_index: 0
                        };
                        
                        elements.push(elementData);
                        
                    } catch (e) {
                        // Skip elements that can't be processed
                        continue;
                    }
                }
                
                return {
                    elements: elements,
                    total_elements: elements.length,
                    dom_depth: 0
                };
            }
            
            return extractAllElements();
        })()
        """        
    
    def _get_asset_extractor_script(self) -> str:
        """JavaScript for asset discovery - FIXED version."""
        return """
        (() => {
            function extractAssets() {
                const assets = [];
                const processedUrls = new Set();
                
                function addAsset(url, type, element = null, context = []) {
                    if (!url || processedUrls.has(url)) return;
                    processedUrls.add(url);
                    
                    const asset = {
                        url: url,
                        asset_type: type,  // FIXED: was assetType, now asset_type
                        usage_context: context,
                        is_background: false
                    };
                    
                    if (element) {
                        if (element.alt) asset.alt_text = element.alt;  // FIXED: was altText
                        if (element.naturalWidth && element.naturalHeight) {
                            asset.dimensions = [element.naturalWidth, element.naturalHeight];
                        }
                    }
                    
                    assets.push(asset);
                }
                
                // Extract images
                const images = document.querySelectorAll('img[src]');
                for (let img of images) {
                    addAsset(img.src, 'image', img, ['img-tag']);
                }
                
                // Extract background images from computed styles
                const allElements = document.querySelectorAll('*');
                for (let element of allElements) {
                    try {
                        const style = window.getComputedStyle(element);
                        const bgImage = style.backgroundImage;
                        
                        if (bgImage && bgImage !== 'none') {
                            const urlMatch = bgImage.match(/url\\(["']?([^"')]+)["']?\\)/);
                            if (urlMatch) {
                                const asset = {
                                    url: urlMatch[1],
                                    asset_type: 'image',  // FIXED: was assetType
                                    usage_context: ['background-image'],
                                    is_background: true
                                };
                                
                                if (!processedUrls.has(asset.url)) {
                                    processedUrls.add(asset.url);
                                    assets.push(asset);
                                }
                            }
                        }
                    } catch (e) {
                        // Skip elements that can't be accessed
                    }
                }
                
                // Extract fonts
                try {
                    for (let stylesheet of document.styleSheets) {
                        try {
                            for (let rule of stylesheet.cssRules) {
                                if (rule.type === CSSRule.FONT_FACE_RULE) {
                                    const src = rule.style.src;
                                    if (src) {
                                        const urlMatches = src.match(/url\\(["']?([^"')]+)["']?\\)/g);
                                        if (urlMatches) {
                                            urlMatches.forEach(match => {
                                                const url = match.match(/url\\(["']?([^"')]+)["']?\\)/)[1];
                                                addAsset(url, 'font', null, ['font-face']);
                                            });
                                        }
                                    }
                                }
                            }
                        } catch (e) {
                            // Can't access cross-origin stylesheets
                        }
                    }
                } catch (e) {
                    // StyleSheets access failed
                }
                
                // Extract videos and audio
                try {
                    const videos = document.querySelectorAll('video[src], video source[src]');
                    for (let video of videos) {
                        if (video.src) {
                            addAsset(video.src, 'video', null, ['video-tag']);
                        }
                    }
                    
                    const audios = document.querySelectorAll('audio[src], audio source[src]');
                    for (let audio of audios) {
                        if (audio.src) {
                            addAsset(audio.src, 'audio', null, ['audio-tag']);
                        }
                    }
                } catch (e) {
                    // Media element access failed
                }
                
                // Extract favicons and icons
                try {
                    const icons = document.querySelectorAll('link[rel*="icon"]');
                    for (let icon of icons) {
                        if (icon.href) {
                            addAsset(icon.href, 'icon', null, ['favicon']);
                        }
                    }
                } catch (e) {
                    // Icon extraction failed
                }
                
                return {
                    assets: assets,
                    total_assets: assets.length
                };
            }
            
            return extractAssets();
        })()
        """

    def _get_style_extractor_script(self) -> str:
        """JavaScript for stylesheet extraction."""
        return """
        (() => {
            function extractStylesheets() {
                const stylesheets = [];
                
                // Extract external stylesheets
                const linkElements = document.querySelectorAll('link[rel="stylesheet"]');
                for (let link of linkElements) {
                    try {
                        const stylesheet = {
                            href: link.href,
                            media: link.media || 'all',
                            inline: false,
                            rules: []
                        };
                        
                        // Try to access rules if same-origin
                        try {
                            if (link.sheet && link.sheet.cssRules) {
                                for (let rule of link.sheet.cssRules) {
                                    if (rule.type === CSSRule.STYLE_RULE) {
                                        stylesheet.rules.push({
                                            selector: rule.selectorText,
                                            styles: rule.style.cssText,
                                            specificity: calculateSpecificity(rule.selectorText)
                                        });
                                    }
                                }
                            }
                        } catch (e) {
                            // Cross-origin stylesheet, can't access rules
                            console.warn('Cannot access stylesheet rules (CORS):', link.href);
                        }
                        
                        stylesheets.push(stylesheet);
                    } catch (e) {
                        console.warn('Error processing stylesheet:', e);
                    }
                }
                
                // Extract inline styles
                const styleElements = document.querySelectorAll('style');
                for (let style of styleElements) {
                    try {
                        const stylesheet = {
                            href: null,
                            media: style.media || 'all',
                            inline: true,
                            content: style.textContent,
                            rules: []
                        };
                        
                        if (style.sheet && style.sheet.cssRules) {
                            for (let rule of style.sheet.cssRules) {
                                if (rule.type === CSSRule.STYLE_RULE) {
                                    stylesheet.rules.push({
                                        selector: rule.selectorText,
                                        styles: rule.style.cssText,
                                        specificity: calculateSpecificity(rule.selectorText)
                                    });
                                }
                            }
                        }
                        
                        stylesheets.push(stylesheet);
                    } catch (e) {
                        console.warn('Error processing inline stylesheet:', e);
                    }
                }
                
                function calculateSpecificity(selector) {
                    if (!selector) return 0;
                    
                    let specificity = 0;
                    
                    // Count IDs
                    const ids = (selector.match(/#[a-zA-Z0-9_-]+/g) || []).length;
                    specificity += ids * 100;
                    
                    // Count classes, attributes, and pseudo-classes
                    const classes = (selector.match(/\\.[a-zA-Z0-9_-]+/g) || []).length;
                    const attributes = (selector.match(/\\[[^\\]]+\\]/g) || []).length;
                    const pseudoClasses = (selector.match(/:[a-zA-Z0-9_-]+/g) || []).length;
                    specificity += (classes + attributes + pseudoClasses) * 10;
                    
                    // Count elements and pseudo-elements
                    const elements = (selector.match(/^[a-zA-Z0-9]+|\\s[a-zA-Z0-9]+/g) || []).length;
                    const pseudoElements = (selector.match(/::[a-zA-Z0-9_-]+/g) || []).length;
                    specificity += elements + pseudoElements;
                    
                    return specificity;
                }
                
                return {
                    stylesheets: stylesheets,
                    total_stylesheets: stylesheets.length
                };
            }
            
            return extractStylesheets();
        })()
        """
    
    def _get_layout_analyzer_script(self) -> str:
        """JavaScript for layout analysis."""
        return """
        (() => {
            function analyzeLayout() {
                const analysis = {
                    colorPalette: [],
                    fontFamilies: [],
                    responsiveBreakpoints: [],
                    layoutType: 'unknown'
                };
                
                // Extract color palette
                const colors = new Set();
                const elements = document.querySelectorAll('*');
                
                for (let element of elements) {
                    try {
                        const style = window.getComputedStyle(element);
                        
                        // Extract colors
                        const color = style.color;
                        const bgColor = style.backgroundColor;
                        const borderColor = style.borderColor;
                        
                        [color, bgColor, borderColor].forEach(c => {
                            if (c && c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent' && c !== 'initial') {
                                colors.add(c);
                            }
                        });
                        
                        // Extract font families
                        const fontFamily = style.fontFamily;
                        if (fontFamily && fontFamily !== 'initial') {
                            analysis.fontFamilies.push(fontFamily.split(',')[0].replace(/['"]/g, '').trim());
                        }
                    } catch (e) {
                        // Skip elements that can't be accessed
                    }
                }
                
                analysis.color_palette = Array.from(colors).slice(0, 20); // Limit to top 20 colors
                analysis.font_families = [...new Set(analysis.fontFamilies)]; // Remove duplicates
                
                // Detect layout type
                const bodyStyle = window.getComputedStyle(document.body);
                if (bodyStyle.display === 'flex' || bodyStyle.display === 'grid') {
                    analysis.layout_type = bodyStyle.display;
                } else {
                    // Check for common layout patterns
                    const flexElements = document.querySelectorAll('[style*="display: flex"], [style*="display:flex"]');
                    const gridElements = document.querySelectorAll('[style*="display: grid"], [style*="display:grid"]');
                    
                    if (gridElements.length > 0) {
                        analysis.layout_type = 'grid';
                    } else if (flexElements.length > 0) {
                        analysis.layout_type = 'flex';
                    } else {
                        analysis.layout_type = 'traditional';
                    }
                }
                
                // Detect responsive breakpoints from media queries
                const breakpoints = new Set();
                for (let stylesheet of document.styleSheets) {
                    try {
                        for (let rule of stylesheet.cssRules) {
                            if (rule.type === CSSRule.MEDIA_RULE) {
                                const mediaText = rule.media.mediaText;
                                const widthMatches = mediaText.match(/\\((?:max-|min-)?width:\\s*(\\d+)px\\)/g);
                                if (widthMatches) {
                                    widthMatches.forEach(match => {
                                        const width = parseInt(match.match(/\\d+/)[0]);
                                        if (width > 0) {
                                            breakpoints.add(width);
                                        }
                                    });
                                }
                            }
                        }
                    } catch (e) {
                        // Can't access cross-origin stylesheets
                    }
                }
                
                analysis.responsive_breakpoints = Array.from(breakpoints).sort((a, b) => a - b);
                
                return analysis;
            }
            
            return analyzeLayout();
        })()
        """
    
    async def extract_dom_structure(
        self,
        url: str,
        session_id: str,
        wait_for_load: bool = True,
        include_computed_styles: bool = True,
        max_depth: int = 10
    ) -> DOMExtractionResult:
        """
        Extract complete DOM structure, styles, and assets from a web page.
        
        Args:
            url: URL to extract from
            session_id: Session identifier
            wait_for_load: Whether to wait for page load completion
            include_computed_styles: Whether to include computed styles
            max_depth: Maximum DOM depth to extract
            
        Returns:
            Complete DOM extraction result
        """
        start_time = time.time()
        
        logger.info(f"Starting DOM extraction for {url}")
        
        if not self.browser_manager:
            raise BrowserError("Browser manager not available")
        
        try:
            async with self.browser_manager.page_context() as page:
                # Navigate to URL
                await self.browser_manager.navigate_to_url(page, url, wait_for="networkidle")
                
                if wait_for_load:
                    await self.browser_manager.wait_for_page_load(page)
                    # Additional wait for dynamic content
                    await page.wait_for_timeout(3000)
                
                # Extract page structure metadata
                page_structure = await self._extract_page_structure(page, url)
                
                # Extract DOM elements
                logger.info("Extracting DOM elements...")
                dom_data = await page.evaluate(self._javascript_extractors["dom_extractor"])
                elements = [ExtractedElement(**elem) for elem in dom_data["elements"]]
                
                # Extract stylesheets
                logger.info("Extracting stylesheets...")
                style_data = await page.evaluate(self._javascript_extractors["style_extractor"])
                stylesheets = [ExtractedStylesheet(**sheet) for sheet in style_data["stylesheets"]]
                
                # Extract assets
                logger.info("Extracting assets...")
                asset_data = await page.evaluate(self._javascript_extractors["asset_extractor"])
                raw_assets = asset_data["assets"]

                # Convert and resolve asset URLs - FIXED VERSION
                assets = []
                for asset_info in raw_assets:
                    try:
                        asset = ExtractedAsset(
                            url=urljoin(url, asset_info["url"]),
                            asset_type=asset_info["asset_type"],  # FIXED: was assetType
                            is_background=asset_info.get("is_background", False),
                            usage_context=asset_info.get("usage_context", []),
                            alt_text=asset_info.get("alt_text"),  # FIXED: was altText
                            dimensions=tuple(asset_info["dimensions"]) if asset_info.get("dimensions") else None
                        )
                        assets.append(asset)
                    except Exception as e:
                        logger.warning(f"Failed to process asset {asset_info.get('url', 'unknown')}: {str(e)}")
                        continue
                
                # Analyze layout
                logger.info("Analyzing layout...")
                layout_data = await page.evaluate(self._javascript_extractors["layout_analyzer"])
                
                extraction_time = time.time() - start_time
                
                result = DOMExtractionResult(
                    url=url,
                    session_id=session_id,
                    timestamp=time.time(),
                    extraction_time=extraction_time,
                    page_structure=page_structure,
                    elements=elements,
                    stylesheets=stylesheets,
                    assets=assets,
                    layout_analysis=layout_data,
                    color_palette=layout_data.get("colorPalette", []),
                    font_families=layout_data.get("fontFamilies", []),
                    responsive_breakpoints=layout_data.get("responsiveBreakpoints", []),
                    dom_depth=dom_data.get("domDepth", 0),
                    total_elements=len(elements),
                    total_stylesheets=len(stylesheets),
                    total_assets=len(assets),
                    success=True
                )
                
                logger.info(
                    f"DOM extraction completed: {len(elements)} elements, "
                    f"{len(stylesheets)} stylesheets, {len(assets)} assets "
                    f"in {extraction_time:.2f}s"
                )
                
                return result
                
        except Exception as e:
            extraction_time = time.time() - start_time
            error_msg = f"DOM extraction failed: {str(e)}"
            logger.error(error_msg)
            
            return DOMExtractionResult(
                url=url,
                session_id=session_id,
                timestamp=time.time(),
                extraction_time=extraction_time,
                page_structure=PageStructure(),
                elements=[],
                stylesheets=[],
                assets=[],
                layout_analysis={},
                color_palette=[],
                font_families=[],
                responsive_breakpoints=[],
                success=False,
                error_message=error_msg
            )
    
    async def _extract_page_structure(self, page, url: str) -> PageStructure:
        """Extract page metadata and structure information."""
        try:
            # Extract basic page metadata
            structure_script = """
            (() => {
                function extractPageStructure() {
                    const structure = {
                        title: document.title || null,
                        lang: document.documentElement.lang || null,
                        charset: document.characterSet || null,
                        openGraph: {},
                        schemaOrg: []
                    };
                    
                    // Extract meta tags
                    const metaTags = document.querySelectorAll('meta');
                    for (let meta of metaTags) {
                        const name = meta.getAttribute('name') || meta.getAttribute('property');
                        const content = meta.getAttribute('content');
                        
                        if (name && content) {
                            if (name === 'description') {
                                structure.metaDescription = content;
                            } else if (name === 'keywords') {
                                structure.metaKeywords = content;
                            } else if (name === 'viewport') {
                                structure.viewport = content;
                            } else if (name.startsWith('og:')) {
                                structure.openGraph[name] = content;
                            }
                        }
                    }
                    
                    // Extract favicon
                    const favicon = document.querySelector('link[rel*="icon"]');
                    if (favicon && favicon.href) {
                        structure.faviconUrl = favicon.href;
                    }
                    
                    // Extract canonical URL
                    const canonical = document.querySelector('link[rel="canonical"]');
                    if (canonical && canonical.href) {
                        structure.canonicalUrl = canonical.href;
                    }
                    
                    // Extract JSON-LD structured data
                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    for (let script of scripts) {
                        try {
                            const data = JSON.parse(script.textContent);
                            structure.schemaOrg.push(data);
                        } catch (e) {
                            // Invalid JSON, skip
                        }
                    }
                    
                    return structure;
                }
                
                return extractPageStructure();
            })()
            """
            
            structure_data = await page.evaluate(structure_script)
            
            return PageStructure(
                title=structure_data.get("title"),
                meta_description=structure_data.get("metaDescription"),
                meta_keywords=structure_data.get("metaKeywords"),
                lang=structure_data.get("lang"),
                charset=structure_data.get("charset"),
                viewport=structure_data.get("viewport"),
                favicon_url=structure_data.get("faviconUrl"),
                canonical_url=structure_data.get("canonicalUrl"),
                open_graph=structure_data.get("openGraph", {}),
                schema_org=structure_data.get("schemaOrg", [])
            )
            
        except Exception as e:
            logger.warning(f"Error extracting page structure: {str(e)}")
            return PageStructure()
    
    async def save_extraction_result(
        self,
        result: DOMExtractionResult,
        output_format: str = "json"
    ) -> str:
        """
        Save extraction result to file.
        
        Args:
            result: DOM extraction result
            output_format: Output format ('json', 'html')
            
        Returns:
            Path to saved file
        """
        output_dir = Path(settings.temp_storage_path) / "extractions"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = int(result.timestamp)
        filename = f"{result.session_id}_extraction_{timestamp}.{output_format}"
        file_path = output_dir / filename
        
        try:
            if output_format == "json":
                # Convert to JSON-serializable format
                data = asdict(result)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False, default=str)
                    
            elif output_format == "html":
                # Generate HTML report
                html_content = self._generate_html_report(result)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
            else:
                raise ValueError(f"Unsupported output format: {output_format}")
            
            logger.info(f"Extraction result saved to {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Error saving extraction result: {str(e)}")
            raise ProcessingError(f"Failed to save extraction result: {str(e)}")
    
    def _generate_html_report(self, result: DOMExtractionResult) -> str:
        """Generate HTML report from extraction result."""
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>DOM Extraction Report - {result.url}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .header {{ background: #f4f4f4; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .element {{ background: #f9f9f9; margin: 10px 0; padding: 10px; border-left: 3px solid #007cba; }}
                .styles {{ font-family: monospace; background: #f0f0f0; padding: 5px; margin: 5px 0; }}
                .color-palette {{ display: flex; flex-wrap: wrap; gap: 10px; }}
                .color-sample {{ width: 50px; height: 50px; border: 1px solid #ccc; border-radius: 3px; }}
                .asset {{ background: #fff3cd; padding: 8px; margin: 5px 0; border-radius: 3px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .success {{ color: #155724; background-color: #d4edda; padding: 5px; border-radius: 3px; }}
                .error {{ color: #721c24; background-color: #f8d7da; padding: 5px; border-radius: 3px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>DOM Extraction Report</h1>
                <p><strong>URL:</strong> {result.url}</p>
                <p><strong>Session ID:</strong> {result.session_id}</p>
                <p><strong>Extraction Time:</strong> {result.extraction_time:.2f} seconds</p>
                <p><strong>Status:</strong> 
                    <span class="{'success' if result.success else 'error'}">
                        {'Success' if result.success else 'Failed'}
                    </span>
                </p>
                {f'<p><strong>Error:</strong> {result.error_message}</p>' if result.error_message else ''}
            </div>

            <div class="section">
                <h2>Page Structure</h2>
                <table>
                    <tr><th>Property</th><th>Value</th></tr>
                    <tr><td>Title</td><td>{result.page_structure.title or 'N/A'}</td></tr>
                    <tr><td>Description</td><td>{result.page_structure.meta_description or 'N/A'}</td></tr>
                    <tr><td>Language</td><td>{result.page_structure.lang or 'N/A'}</td></tr>
                    <tr><td>Charset</td><td>{result.page_structure.charset or 'N/A'}</td></tr>
                    <tr><td>Viewport</td><td>{result.page_structure.viewport or 'N/A'}</td></tr>
                </table>
            </div>

            <div class="section">
                <h2>Extraction Summary</h2>
                <table>
                    <tr><th>Metric</th><th>Count</th></tr>
                    <tr><td>Total Elements</td><td>{result.total_elements}</td></tr>
                    <tr><td>Total Stylesheets</td><td>{result.total_stylesheets}</td></tr>
                    <tr><td>Total Assets</td><td>{result.total_assets}</td></tr>
                    <tr><td>DOM Depth</td><td>{result.dom_depth}</td></tr>
                </table>
            </div>

            <div class="section">
                <h2>Color Palette</h2>
                <div class="color-palette">
                    {self._generate_color_samples(result.color_palette)}
                </div>
            </div>

            <div class="section">
                <h2>Font Families</h2>
                <ul>
                    {chr(10).join(f'<li>{font}</li>' for font in result.font_families[:20])}
                </ul>
            </div>

            <div class="section">
                <h2>Responsive Breakpoints</h2>
                <p>{', '.join(map(str, result.responsive_breakpoints))} px</p>
            </div>

            <div class="section">
                <h2>Top Elements ({min(len(result.elements), 50)} of {len(result.elements)})</h2>
                {self._generate_elements_html(result.elements[:50])}
            </div>

            <div class="section">
                <h2>Assets ({len(result.assets)})</h2>
                {self._generate_assets_html(result.assets[:100])}
            </div>

        </body>
        </html>
        """
        return html
    
    def _generate_color_samples(self, colors: List[str]) -> str:
        """Generate HTML for color palette samples."""
        samples = []
        for color in colors[:20]:  # Limit to 20 colors
            # Handle different color formats
            color_value = color
            if color.startswith('rgb'):
                color_value = color
            elif not color.startswith('#'):
                color_value = f'#{color}' if len(color) == 6 else color
            
            samples.append(
                f'<div class="color-sample" style="background-color: {color_value};" '
                f'title="{color}"></div>'
            )
        return ''.join(samples)
    
    def _generate_elements_html(self, elements: List[ExtractedElement]) -> str:
        """Generate HTML for elements display."""
        elements_html = []
        for element in elements:
            styles_text = '; '.join(f'{k}: {v}' for k, v in list(element.computed_styles.items())[:10])
            
            element_html = f"""
            <div class="element">
                <strong>{element.tag_name}</strong>
                {f'#{element.element_id}' if element.element_id else ''}
                {f'.{" .".join(element.class_names[:3])}' if element.class_names else ''}
                <br>
                <small>Children: {element.children_count} | Visible: {element.is_visible}</small>
                {f'<div class="styles">{styles_text}...</div>' if styles_text else ''}
            </div>
            """
            elements_html.append(element_html)
        
        return ''.join(elements_html)
    
    def _generate_assets_html(self, assets: List[ExtractedAsset]) -> str:
        """Generate HTML for assets display."""
        assets_html = []
        for asset in assets:
            asset_html = f"""
            <div class="asset">
                <strong>{asset.asset_type.upper()}</strong>: 
                <a href="{asset.url}" target="_blank">{asset.url[:100]}...</a>
                {f'<br><small>Alt: {asset.alt_text}</small>' if asset.alt_text else ''}
                {f'<br><small>Dimensions: {asset.dimensions[0]}x{asset.dimensions[1]}</small>' if asset.dimensions else ''}
                <br><small>Context: {', '.join(asset.usage_context)}</small>
            </div>
            """
            assets_html.append(asset_html)
        
        return ''.join(assets_html)
    
    async def analyze_page_complexity(self, result: DOMExtractionResult) -> Dict[str, Any]:
        """
        Analyze page complexity based on extraction results.
        
        Args:
            result: DOM extraction result
            
        Returns:
            Complexity analysis metrics
        """
        if not result.success:
            return {"error": "Cannot analyze failed extraction"}
        
        complexity = {
            "overall_score": 0,
            "dom_complexity": 0,
            "style_complexity": 0,
            "asset_complexity": 0,
            "layout_complexity": 0,
            "recommendations": []
        }
        
        # DOM complexity (0-100)
        dom_score = min(100, (result.total_elements / 10) + (result.dom_depth * 5))
        complexity["dom_complexity"] = dom_score
        
        # Style complexity (0-100)
        total_rules = sum(len(sheet.rules) for sheet in result.stylesheets)
        style_score = min(100, (total_rules / 5) + (len(result.stylesheets) * 10))
        complexity["style_complexity"] = style_score
        
        # Asset complexity (0-100)
        asset_score = min(100, result.total_assets * 2)
        complexity["asset_complexity"] = asset_score
        
        # Layout complexity (0-100)
        layout_score = 0
        if result.layout_analysis.get("layoutType") == "grid":
            layout_score += 30
        elif result.layout_analysis.get("layoutType") == "flex":
            layout_score += 20
        
        layout_score += min(50, len(result.responsive_breakpoints) * 10)
        layout_score += min(20, len(result.color_palette))
        complexity["layout_complexity"] = layout_score
        
        # Overall complexity
        complexity["overall_score"] = (dom_score + style_score + asset_score + layout_score) / 4
        
        # Generate recommendations
        if dom_score > 80:
            complexity["recommendations"].append("High DOM complexity - consider element reduction")
        if style_score > 80:
            complexity["recommendations"].append("High style complexity - consider CSS optimization")
        if asset_score > 80:
            complexity["recommendations"].append("High asset count - consider asset optimization")
        if len(result.color_palette) > 15:
            complexity["recommendations"].append("Large color palette - consider color consolidation")
        
        return complexity
    
    async def get_extraction_info(self, session_id: str) -> Dict[str, Any]:
        """
        Get information about extractions for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with extraction information
        """
        extractions_dir = Path(settings.temp_storage_path) / "extractions"
        
        if not extractions_dir.exists():
            return {"session_id": session_id, "extractions": []}
        
        extraction_files = list(extractions_dir.glob(f"{session_id}_extraction_*.json"))
        
        extractions_info = []
        total_size = 0
        
        for file_path in extraction_files:
            try:
                stat = file_path.stat()
                info = {
                    "filename": file_path.name,
                    "size": stat.st_size,
                    "created": stat.st_mtime,
                    "path": str(file_path)
                }
                
                extractions_info.append(info)
                total_size += stat.st_size
                
            except Exception as e:
                logger.warning(f"Error getting info for {file_path.name}: {str(e)}")
        
        return {
            "session_id": session_id,
            "extraction_count": len(extractions_info),
            "total_size": total_size,
            "extractions": extractions_info
        }
    
    async def cleanup_extractions(
        self,
        session_id: Optional[str] = None,
        older_than_hours: Optional[int] = None
    ) -> int:
        """
        Clean up extraction files.
        
        Args:
            session_id: Clean up specific session (if None, cleans all)
            older_than_hours: Only clean files older than this many hours
            
        Returns:
            Number of files cleaned up
        """
        extractions_dir = Path(settings.temp_storage_path) / "extractions"
        
        if not extractions_dir.exists():
            return 0
        
        cleaned_count = 0
        current_time = time.time()
        
        pattern = f"{session_id}_extraction_*.json" if session_id else "*.json"
        
        for file_path in extractions_dir.glob(pattern):
            # Check age filter
            if older_than_hours:
                file_age_hours = (current_time - file_path.stat().st_mtime) / 3600
                if file_age_hours < older_than_hours:
                    continue
            
            try:
                file_path.unlink()
                cleaned_count += 1
                logger.debug(f"Cleaned up extraction: {file_path.name}")
            except Exception as e:
                logger.warning(f"Failed to clean up {file_path.name}: {str(e)}")
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} extraction files")
        
        return cleaned_count


# Global DOM extraction service instance
dom_extraction_service = DOMExtractionService()