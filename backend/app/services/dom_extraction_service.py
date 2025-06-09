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
from .extraction import extractors, analyzer, storage
from ..models.dom_extraction import (
    ExtractedElementModel as ExtractedElement,
    ExtractedStylesheetModel as ExtractedStylesheet,
    ExtractedAssetModel as ExtractedAsset,
    PageStructureModel as PageStructure,
    DOMExtractionResultModel as DOMExtractionResult,
)


logger = get_logger(__name__)


class DOMExtractionService:
    """
    Service for extracting DOM structure, styles, and assets from web pages.
    
    Provides comprehensive analysis of page structure, computed styles,
    layout information, and asset discovery for website cloning.
    """
    
    def __init__(self, browser_manager: Optional[BrowserManager] = None):
        self.browser_manager = browser_manager
        self._javascript_extractors = {
            "dom_extractor": extractors.get_dom_extractor_script(),
            "style_extractor": extractors.get_style_extractor_script(),
            "asset_extractor": extractors.get_asset_extractor_script(),
            "layout_analyzer": extractors.get_layout_analyzer_script()
        }
    
    async def _wait_for_dynamic_content(self, page) -> None:
        """Enhanced waiting strategy for dynamic content."""
        try:
            # Wait for network idle
            await page.wait_for_load_state("networkidle", timeout=30000)
            
            # Wait for common dynamic content indicators
            await page.evaluate("""
                async () => {
                    // Wait for common framework indicators
                    const frameworks = ['React', 'Vue', 'Angular', '$', 'jQuery'];
                    let frameworkLoaded = false;
                    
                    for (const fw of frameworks) {
                        if (window[fw]) {
                            frameworkLoaded = true;
                            break;
                        }
                    }
                    
                    if (frameworkLoaded) {
                        // Additional wait for framework initialization
                        await new Promise(resolve => setTimeout(resolve, 3000));
                    }
                    
                    // Wait for any remaining animations to complete
                    await new Promise(resolve => setTimeout(resolve, 2000));
                    
                    return true;
                }
            """)
            
            # Check for lazy-loaded content
            await page.evaluate("""
                () => {
                    // Scroll to trigger lazy loading
                    window.scrollTo(0, document.body.scrollHeight);
                    window.scrollTo(0, 0);
                }
            """)
            
            # Final wait for lazy content to load
            await page.wait_for_timeout(2000)
        
        except Exception as e:
            logger.warning(f"Enhanced waiting failed, proceeding with extraction: {str(e)}")

    async def extract_dom_structure(
        self,
        url: str,
        session_id: str,
        wait_for_load: bool = True,
        include_computed_styles: bool = True,
        max_depth: int = 10
    ) -> DOMExtractionResult:
        """Enhanced DOM extraction with proper dynamic content waiting."""
        start_time = time.time()
        
        logger.info(f"Starting enhanced DOM extraction for {url}")
        
        if not self.browser_manager:
            raise BrowserError("Browser manager not available")
        
        try:
            async with self.browser_manager.page_context() as page:
                # Navigate to URL
                await self.browser_manager.navigate_to_url(page, url, wait_for="networkidle")
                
                if wait_for_load:
                    # Enhanced waiting strategy for dynamic content
                    await self._wait_for_dynamic_content(page)
                
                # Extract page structure metadata
                page_structure = await self._extract_page_structure(page, url)
                
                # Extract DOM elements with dynamic content support
                logger.info("Extracting DOM elements with dynamic content...")
                dom_data = await page.evaluate(self._javascript_extractors["dom_extractor"])
                
                if not dom_data.get("page_fully_loaded"):
                    logger.warning("Page may not be fully loaded - extraction might be incomplete")
                
                elements = [ExtractedElement(**elem) for elem in dom_data["elements"]]
                
                # Extract stylesheets with enhanced CSS rule extraction
                logger.info("Extracting enhanced stylesheets...")
                style_data = await page.evaluate(self._javascript_extractors["style_extractor"])
                stylesheets = [ExtractedStylesheet(**sheet) for sheet in style_data["stylesheets"]]
                
                # Extract assets with better URL resolution
                logger.info("Extracting assets with enhanced resolution...")
                asset_data = await page.evaluate(self._javascript_extractors["asset_extractor"])
                assets = []
                for asset_info in asset_data["assets"]:
                    try:
                        asset = ExtractedAsset(
                            url=urljoin(url, asset_info["url"]),
                            asset_type=asset_info["asset_type"],
                            is_background=asset_info.get("is_background", False),
                            usage_context=asset_info.get("usage_context", []),
                            alt_text=asset_info.get("alt_text"),
                            dimensions=tuple(asset_info["dimensions"]) if asset_info.get("dimensions") else None
                        )
                        assets.append(asset)
                    except Exception as e:
                        logger.warning(f"Failed to process asset {asset_info.get('url', 'unknown')}: {str(e)}")
                        continue
                
                # Enhanced layout analysis
                logger.info("Performing enhanced layout analysis...")
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
                    color_palette=layout_data.get("color_palette", []),
                    font_families=layout_data.get("font_families", []),
                    responsive_breakpoints=layout_data.get("responsive_breakpoints", []),
                    dom_depth=dom_data.get("dom_depth", 0),
                    total_elements=len(elements),
                    total_stylesheets=len(stylesheets),
                    total_assets=len(assets),
                    success=True
                )
                
                logger.info(
                    f"Enhanced DOM extraction completed: {len(elements)} elements, "
                    f"{len(stylesheets)} stylesheets, {len(assets)} assets "
                    f"in {extraction_time:.2f}s"
                )
                
                return result
                
        except Exception as e:
            # Error handling remains the same
            extraction_time = time.time() - start_time
            error_msg = f"Enhanced DOM extraction failed: {str(e)}"
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

    async def save_extraction_result(self, result: DOMExtractionResult, output_format: str = "json") -> str:
        return await storage.save_extraction_result(result, output_format)

    async def get_extraction_info(self, session_id: str) -> Dict[str, Any]:
        return await storage.get_extraction_info(session_id)

    async def cleanup_extractions(self, session_id: Optional[str] = None, older_than_hours: Optional[int] = None) -> int:
        return await storage.cleanup_extractions(session_id, older_than_hours)

    async def analyze_page_complexity(self, result: DOMExtractionResult) -> Dict[str, Any]:
        return await analyzer.analyze_page_complexity(result)


# Global DOM extraction service instance
dom_extraction_service = DOMExtractionService()