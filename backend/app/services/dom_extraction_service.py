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
        Extracts a complete hierarchical blueprint with enhanced asset detection.
        """
        start_time = time.time()
        logger.info(f"Starting enhanced blueprint extraction for {url}")

        if not self.browser_manager:
            raise BrowserError("Browser manager not available for DOM extraction")

        try:
            async with self.browser_manager.page_context() as page:
                await self.browser_manager.navigate_to_url(page, url, wait_for="networkidle")
                await self._wait_for_dynamic_content(page)
                
                page_structure = await self._extract_page_structure(page, url)

                logger.info("Executing enhanced blueprint extraction script...")
                extraction_data = await page.evaluate(self._javascript_extractors["dom_extractor"])
                
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
                    for i, asset in enumerate(assets_data[:5]):  # Log first 5 assets
                        logger.info(f"Asset {i+1}: type={asset.get('asset_type')}, url={asset.get('url', 'N/A')[:100]}, has_content={bool(asset.get('content'))}")
                else:
                    logger.warning("No assets found in extraction")

                # Convert blueprint to model
                blueprint_model = DetectedComponent(**blueprint_dict) if blueprint_dict else None

                # Convert assets to models
                assets = []
                for asset_data in assets_data:
                    try:
                        # Handle different asset structures
                        asset_model = ExtractedAsset(
                            url=asset_data.get('url'),
                            content=asset_data.get('content'),
                            asset_type=asset_data.get('asset_type', 'unknown'),
                            alt_text=asset_data.get('alt_text'),
                            dimensions=asset_data.get('dimensions'),
                            usage_context=asset_data.get('usage_context', [])
                        )
                        assets.append(asset_model)
                    except Exception as e:
                        logger.warning(f"Failed to create asset model: {e}")
                        # Create basic asset model
                        assets.append(ExtractedAsset(
                            url=asset_data.get('url'),
                            asset_type=asset_data.get('asset_type', 'unknown')
                        ))

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
                    # Add metadata fields
                    total_elements=metadata.get('total_components', 0),
                    total_stylesheets=0,  # Will be filled if needed
                    total_assets=len(assets),
                    dom_depth=6  # Max depth from our config
                )
                
                logger.info(f"Enhanced blueprint extraction completed in {extraction_time:.2f}s")
                logger.info(f"Extracted {len(assets)} assets, {metadata.get('total_components', 0)} components")
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
