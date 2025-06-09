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
    StyleAnalysisModel,
    ColorPaletteModel,
    TypographyAnalysisModel,
    TypographyStyleModel
)
from ..models.components import DetectedComponent


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
            "dom_extractor": extractors.get_dom_extractor_script()
        }
    
    async def _wait_for_dynamic_content(self, page, timeout: int = 8000):
        """Enhanced waiting for dynamic content including React/Vue apps."""
        # Wait for basic content
        await asyncio.sleep(2)
        
        # Wait for React apps
        try:
            await page.wait_for_function("""
                () => {
                    // Check if React has finished rendering
                    if (window.React || document.querySelector('[data-reactroot]')) {
                        const reactElements = document.querySelectorAll('[data-reactroot] *');
                        return reactElements.length > 10; // Assume some content has loaded
                    }
                    return true; // Not a React app
                }
            """, timeout=timeout)
        except Exception as e:
            logger.debug(f"React wait timeout: {e}")
        
        # Wait for Vue apps
        try:
            await page.wait_for_function("""
                () => {
                    if (window.Vue || document.querySelector('[data-v-]')) {
                        const vueElements = document.querySelectorAll('[data-v-]');
                        return vueElements.length > 5;
                    }
                    return true; // Not a Vue app
                }
            """, timeout=timeout)
        except Exception as e:
            logger.debug(f"Vue wait timeout: {e}")
        
        # Wait for images to start loading
        try:
            await page.wait_for_function("""
                () => {
                    const images = document.querySelectorAll('img');
                    if (images.length === 0) return true;
                    
                    let loadedCount = 0;
                    images.forEach(img => {
                        if (img.complete || img.naturalWidth > 0) {
                            loadedCount++;
                        }
                    });
                    
                    // Consider it ready if at least 50% of images are loaded or started loading
                    return loadedCount >= Math.min(images.length * 0.5, 10);
                }
            """, timeout=timeout)
        except Exception as e:
            logger.debug(f"Image loading wait timeout: {e}")

    async def _extract_page_structure(self, page, url: str) -> PageStructure:
        """Enhanced page structure extraction."""
        try:
            # Extract comprehensive page metadata
            page_data = await page.evaluate("""
                () => {
                    const getMetaContent = (name) => {
                        const meta = document.querySelector(`meta[name="${name}"], meta[property="${name}"]`);
                        return meta ? meta.getAttribute('content') : null;
                    };
                    
                    return {
                        title: document.title,
                        description: getMetaContent('description'),
                        keywords: getMetaContent('keywords'),
                        lang: document.documentElement.lang,
                        charset: document.characterSet,
                        viewport: getMetaContent('viewport'),
                        favicon: document.querySelector('link[rel*="icon"]')?.href,
                        canonical: document.querySelector('link[rel="canonical"]')?.href,
                        og_title: getMetaContent('og:title'),
                        og_description: getMetaContent('og:description'),
                        og_image: getMetaContent('og:image'),
                        og_url: getMetaContent('og:url'),
                        twitter_card: getMetaContent('twitter:card'),
                        twitter_title: getMetaContent('twitter:title'),
                        twitter_description: getMetaContent('twitter:description'),
                        twitter_image: getMetaContent('twitter:image')
                    };
                }
            """)
            
            # Build Open Graph data
            open_graph = {}
            for key, value in page_data.items():
                if key.startswith('og_') and value:
                    open_graph[key[3:]] = value
                elif key.startswith('twitter_') and value:
                    open_graph[key] = value
            
            return PageStructure(
                title=page_data.get('title'),
                meta_description=page_data.get('description'),
                meta_keywords=page_data.get('keywords'),
                lang=page_data.get('lang'),
                charset=page_data.get('charset'),
                viewport=page_data.get('viewport'),
                favicon_url=page_data.get('favicon'),
                canonical_url=page_data.get('canonical'),
                open_graph=open_graph
            )
            
        except Exception as e:
            logger.warning(f"Failed to extract page structure: {e}")
            return PageStructure(title="Unknown")

    async def extract_dom_structure(
        self,
        url: str,
        session_id: str,
        wait_for_load: bool = True,
        include_computed_styles: bool = True,
        max_depth: int = 6
    ) -> DOMExtractionResult:
        """
        Enhanced DOM extraction with better asset detection and modern web support.
        """
        start_time = time.time()
        logger.info(f"Starting enhanced blueprint extraction for {url}")

        if not self.browser_manager:
            raise BrowserError("Browser manager not available for DOM extraction")

        try:
            async with self.browser_manager.page_context() as page:
                await self.browser_manager.navigate_to_url(page, url, wait_for="networkidle")
                
                # Enhanced waiting for dynamic content
                await self._wait_for_dynamic_content(page, timeout=8000)
                
                # Wait for images to load with proper error handling
                try:
                    await page.wait_for_function("""
                        () => {
                            const images = Array.from(document.images);
                            return images.every(img => img.complete || img.naturalWidth > 0);
                        }
                    """, timeout=10000)
                except Exception as e:
                    logger.warning(f"Image loading wait failed: {e}")
                    # Continue without failing the entire process
                
                page_structure = await self._extract_page_structure(page, url)

                logger.info("Executing enhanced blueprint extraction script...")
                
                # Use the enhanced extractor script
                extraction_data = await page.evaluate(self._javascript_extractors["dom_extractor"])
                
                logger.info("=== DOM EXTRACTION DEBUG ===")
                logger.info(f"Extraction data type: {type(extraction_data)}")
                logger.info(f"Extraction data keys: {list(extraction_data.keys()) if isinstance(extraction_data, dict) else 'Not a dict'}")

                if isinstance(extraction_data, dict):
                    assets_data = extraction_data.get("assets", [])
                    metadata = extraction_data.get("metadata", {})
                    
                    logger.info(f"Assets data type: {type(assets_data)}")
                    logger.info(f"Assets length: {len(assets_data) if isinstance(assets_data, list) else 'Not a list'}")
                    logger.info(f"Metadata: {metadata}")
                    
                    if isinstance(assets_data, list) and len(assets_data) > 0:
                        logger.info(f"First asset: {assets_data[0]}")
                        logger.info(f"Asset types found: {[asset.get('asset_type') for asset in assets_data[:5]]}")
                    else:
                        logger.warning("No assets found in extraction data!")
                        
                        # Check if there are actually images on the page
                        image_check = await page.evaluate("""
                            () => {
                                const images = document.querySelectorAll('img, svg, [style*="background-image"]');
                                const imageInfo = Array.from(images).slice(0, 10).map(img => ({
                                    tag: img.tagName,
                                    src: img.src || img.getAttribute('src') || 'no-src',
                                    classes: Array.from(img.classList),
                                    hasBackgroundImage: img.style.backgroundImage ? true : false
                                }));
                                
                                return {
                                    totalImages: images.length,
                                    imageInfo: imageInfo,
                                    bodyHtml: document.body.innerHTML.substring(0, 500)
                                };
                            }
                        """)
                        
                        logger.info(f"Manual image check: {image_check}")
                else:
                    logger.error(f"Extraction data is not a dict: {extraction_data}")

                logger.info("=== END DEBUG ===")

                if not extraction_data:
                    raise ProcessingError("Blueprint extraction script returned no data.")

                # Extract blueprint and assets
                blueprint_dict = extraction_data.get("blueprint")
                assets_data = extraction_data.get("assets", [])
                metadata = extraction_data.get("metadata", {})
                
                logger.info(f"Extraction metadata: {metadata}")

                # Debug asset extraction
                if assets_data:
                    logger.info(f"Assets found: {len(assets_data)}")
                    asset_types = {}
                    for asset in assets_data:
                        asset_type = asset.get('asset_type', 'unknown')
                        asset_types[asset_type] = asset_types.get(asset_type, 0) + 1
                    logger.info(f"Asset types: {asset_types}")
                    
                    # Log sample assets
                    for i, asset in enumerate(assets_data[:5]):
                        logger.info(f"Asset {i+1}: type={asset.get('asset_type')}, " +
                                f"url={asset.get('url', 'N/A')[:100]}, " +
                                f"has_content={bool(asset.get('content'))}")
                else:
                    logger.warning("No assets found in extraction")

                # Convert blueprint to model
                blueprint_model = DetectedComponent(**blueprint_dict) if blueprint_dict else None

                # Enhanced asset conversion with better error handling
                assets = []
                for asset_data in assets_data:
                    try:
                        # Create asset model with all available fields
                        asset_model = ExtractedAsset(
                            url=asset_data.get('url'),
                            content=asset_data.get('content'),
                            asset_type=asset_data.get('asset_type', 'unknown'),
                            mime_type=asset_data.get('content_type'),
                            alt_text=asset_data.get('alt_text'),
                            dimensions=asset_data.get('dimensions') or (
                                (asset_data.get('width'), asset_data.get('height')) 
                                if asset_data.get('width') and asset_data.get('height') 
                                else None
                            ),
                            usage_context=asset_data.get('usage_context', []),
                            is_background=asset_data.get('asset_type') in ['background-image', 'css-background'],
                            size=asset_data.get('file_size')
                        )
                        assets.append(asset_model)
                    except Exception as e:
                        logger.warning(f"Failed to create asset model: {e}")
                        # Create minimal asset model
                        try:
                            minimal_asset = ExtractedAsset(
                                url=asset_data.get('url'),
                                asset_type=asset_data.get('asset_type', 'unknown'),
                                alt_text=asset_data.get('alt_text', 'asset')
                            )
                            assets.append(minimal_asset)
                        except Exception as e2:
                            logger.error(f"Failed to create minimal asset model: {e2}")

                extraction_time = time.time() - start_time
                
                result = DOMExtractionResult(
                    url=url,
                    session_id=session_id,
                    timestamp=time.time(),
                    extraction_time=extraction_time,
                    page_structure=page_structure,
                    blueprint=blueprint_model,
                    assets=assets,
                    success=True,
                    # Enhanced metadata
                    total_elements=metadata.get('total_components', 0),
                    total_stylesheets=0,
                    total_assets=len(assets),
                    dom_depth=max_depth
                )
                
                logger.info(f"Enhanced blueprint extraction completed in {extraction_time:.2f}s")
                logger.info(f"Extracted {len(assets)} assets, {metadata.get('total_components', 0)} components")
                logger.info(f"Asset types found: {metadata.get('asset_types', [])}")
                
                return result
                
        except Exception as e:
            logger.error(f"Blueprint extraction failed: {str(e)}", exc_info=True)
            return DOMExtractionResult(
                url=url,
                session_id=session_id,
                timestamp=time.time(),
                extraction_time=time.time() - start_time,
                page_structure=PageStructure(url=url, title="Error"),
                blueprint=None,
                assets=[],
                success=False,
                error_message=f"Blueprint extraction failed: {str(e)}"
            )

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
