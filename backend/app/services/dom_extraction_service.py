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
    
    async def _wait_for_dynamic_content(self, page, timeout: int = 5000):
        """Waits for a period to allow dynamic content to load."""
        await asyncio.sleep(timeout / 1000)

    async def _extract_page_structure(self, page, url: str) -> PageStructure:
        """Extracts basic page metadata like title."""
        title = await page.title()
        return PageStructure(url=url, title=title)


    async def extract_dom_structure(
        self,
        url: str,
        session_id: str
    ) -> DOMExtractionResult:
        """
        Extracts a complete hierarchical blueprint from the page using the
        injected JavaScript extractor.
        """
        start_time = time.time()
        logger.info(f"Starting blueprint extraction for {url}")

        if not self.browser_manager:
            raise BrowserError("Browser manager not available for DOM extraction")

        try:
            async with self.browser_manager.page_context() as page:
                await self.browser_manager.navigate_to_url(page, url, wait_for="networkidle")
                await self._wait_for_dynamic_content(page)
                
                page_structure = await self._extract_page_structure(page, url)

                logger.info("Executing blueprint extraction script...")
                extraction_data = await page.evaluate(self._javascript_extractors["dom_extractor"])
                
                if not extraction_data or "blueprint" not in extraction_data:
                    raise ProcessingError("Blueprint extraction script returned invalid data.")

                blueprint_dict = extraction_data["blueprint"]
                blueprint_model = DetectedComponent(**blueprint_dict) if blueprint_dict else None

                assets = []
                def collect_assets(component: DetectedComponent):
                    if component.asset_url:
                        assets.append(ExtractedAsset(url=component.asset_url, asset_type=str(component.component_type)))
                    for child in component.children:
                        collect_assets(child)
                
                if blueprint_model:
                    collect_assets(blueprint_model)

                extraction_time = time.time() - start_time
                
                result = DOMExtractionResult(
                    url=url,
                    session_id=session_id,
                    timestamp=time.time(),
                    extraction_time=extraction_time,
                    page_structure=page_structure,
                    blueprint=blueprint_model,
                    assets=assets,
                    success=True
                )
                
                logger.info(f"Blueprint extraction completed in {extraction_time:.2f}s")
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
