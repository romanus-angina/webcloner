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
    StyleAnalysisModel,
    ColorPaletteModel,
    TypographyAnalysisModel,
    TypographyStyleModel
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
            "asset_extractor": extractors.get_asset_extractor_script(),
            "style_analyzer": extractors.get_style_extractor_script()
        }
    
    async def _wait_for_dynamic_content(self, page) -> None:
        """Enhanced waiting strategy for dynamic content."""
        try:
            await page.wait_for_load_state("networkidle", timeout=30000)
            await page.evaluate("new Promise(resolve => setTimeout(resolve, 2000))")
        except Exception as e:
            logger.warning(f"Waiting for dynamic content failed, proceeding: {str(e)}")

    async def extract_dom_structure(
        self,
        url: str,
        session_id: str,
        wait_for_load: bool = True,
        include_computed_styles: bool = True,
        max_depth: int = 10
    ) -> DOMExtractionResult:
        """Enhanced DOM extraction with structured style analysis."""
        start_time = time.time()
        logger.info(f"Starting DOM and Style extraction for {url}")
        
        if not self.browser_manager:
            raise BrowserError("Browser manager not available")
        
        try:
            async with self.browser_manager.page_context() as page:
                await self.browser_manager.navigate_to_url(page, url, wait_for="networkidle")
                
                if wait_for_load:
                    await self._wait_for_dynamic_content(page)
                
                page_structure = await self._extract_page_structure(page, url)
                
                logger.info("Extracting DOM elements...")
                dom_data = await page.evaluate(self._javascript_extractors["dom_extractor"])
                elements = [ExtractedElement(**elem) for elem in dom_data["elements"]]
                
                logger.info("Extracting Assets...")
                asset_data = await page.evaluate(self._javascript_extractors["asset_extractor"])
                asset_list = asset_data.get("assets", [])
                assets = []
                for a in asset_list:
                    # If it's an external asset with a URL, resolve it to be absolute
                    if a.get("url"):
                        a["url"] = urljoin(url, a["url"])
                    assets.append(ExtractedAsset(**a))
                
                logger.info("Performing Style and Layout Analysis...")
                style_data = await page.evaluate(self._javascript_extractors["style_analyzer"])

                style_analysis = StyleAnalysisModel(**style_data)
                
                extraction_time = time.time() - start_time
                
                result = DOMExtractionResult(
                    url=url,
                    session_id=session_id,
                    timestamp=time.time(),
                    extraction_time=extraction_time,
                    page_structure=page_structure,
                    elements=elements,
                    stylesheets=[],
                    assets=assets,
                    style_analysis=style_analysis,
                    dom_depth=dom_data.get("dom_depth", 0),
                    total_elements=len(elements),
                    total_stylesheets=0,
                    total_assets=len(assets),
                    success=True
                )
                
                logger.info(f"DOM and Style extraction completed in {extraction_time:.2f}s")
                return result
                
        except Exception as e:
            extraction_time = time.time() - start_time
            error_msg = f"DOM and Style extraction failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Create a default StyleAnalysisModel for the failed case
            default_style_analysis = StyleAnalysisModel(
                theme=ColorPaletteModel(),
                typography=TypographyAnalysisModel(body=TypographyStyleModel()),
            )

            return DOMExtractionResult(
                url=url,
                session_id=session_id,
                timestamp=time.time(),
                extraction_time=extraction_time,
                success=False,
                error_message=error_msg,
                page_structure=PageStructure(),
                elements=[],
                stylesheets=[],
                assets=[],
                style_analysis=default_style_analysis
            )
    
    async def _extract_page_structure(self, page, url: str) -> PageStructure:
        """Extract page metadata and structure information."""
        try:
            structure_script = """
            (() => {
                const structure = { title: document.title || null, lang: document.documentElement.lang || null };
                // ... (rest of the script can be shortened for brevity)
                return structure;
            })()
            """
            structure_data = await page.evaluate(structure_script)
            return PageStructure(**structure_data)
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
