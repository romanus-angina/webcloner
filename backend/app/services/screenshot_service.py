from typing import Dict, List, Optional, Tuple, Any
import asyncio
import time
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import hashlib
import logging

from ..config import settings
from ..core.exceptions import (
    BrowserError,
    BrowserTimeoutError,
    ProcessingError,
    StorageError
)
from ..utils.logger import get_logger
from .browser_manager import BrowserManager

logger = get_logger(__name__)


class ViewportType(str, Enum):
    MOBILE = "mobile"
    TABLET = "tablet"
    DESKTOP = "desktop"
    LARGE_DESKTOP = "large_desktop"
    CUSTOM = "custom"


@dataclass
class Viewport:
    name: str
    width: int
    height: int
    device_scale_factor: float = 1.0
    is_mobile: bool = False
    user_agent: Optional[str] = None
    
    def __post_init__(self):
        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"Invalid viewport dimensions: {self.width}x{self.height}")
        if self.device_scale_factor <= 0:
            raise ValueError(f"Invalid device scale factor: {self.device_scale_factor}")


@dataclass
class ScreenshotResult:
    viewport: Viewport
    file_path: str
    file_size: int
    capture_time: float
    url: Optional[str] = None
    timestamp: float = time.time()
    page_title: Optional[str] = None
    page_dimensions: Optional[Tuple[int, int]] = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class ScreenshotBatch:
    url: str
    session_id: str
    screenshots: List[ScreenshotResult]
    total_capture_time: float
    created_at: float
    
    @property
    def successful_screenshots(self) -> List[ScreenshotResult]:
        return [s for s in self.screenshots if s.success]
    
    @property
    def failed_screenshots(self) -> List[ScreenshotResult]:
        return [s for s in self.screenshots if not s.success]
    
    @property
    def success_rate(self) -> float:
        if not self.screenshots: return 0.0
        return (len(self.successful_screenshots) / len(self.screenshots)) * 100


class ScreenshotService:
    def __init__(self, browser_manager: Optional[BrowserManager] = None):
        self.browser_manager = browser_manager
        self._default_viewports = self._create_default_viewports()
        
    def _create_default_viewports(self) -> Dict[ViewportType, Viewport]:
        return {
            ViewportType.DESKTOP: Viewport(name="Desktop", width=1920, height=1080)
        }
    
    def get_default_viewports(self) -> List[Viewport]:
        return list(self._default_viewports.values())
    
    def get_viewport_by_type(self, viewport_type: ViewportType) -> Viewport:
        return self._default_viewports[viewport_type]

    def create_custom_viewport(self, name: str, width: int, height: int, **kwargs) -> Viewport:
        return Viewport(name=name, width=width, height=height, **kwargs)

    async def capture_screenshot(self, url: str, viewport: Viewport, session_id: str, **kwargs) -> ScreenshotResult:
        return await self._capture(url=url, viewport=viewport, session_id=session_id, **kwargs)

    async def capture_html_content_screenshot(self, html_content: str, viewport: Viewport, session_id: str, **kwargs) -> ScreenshotResult:
        return await self._capture(html_content=html_content, viewport=viewport, session_id=session_id, **kwargs)

    async def _capture(
        self,
        viewport: Viewport,
        session_id: str,
        url: Optional[str] = None,
        html_content: Optional[str] = None,
        wait_for_load: bool = True,
        full_page: bool = False,
        quality: int = 90
    ) -> ScreenshotResult:
        capture_source = url or "html_content"
        logger.info(f"Capturing screenshot for {capture_source} at {viewport.name}")
        
        try:
            if not self.browser_manager:
                raise BrowserError("Browser manager not available")

            filename = self._generate_filename(url, html_content, viewport, session_id)
            file_path = Path(settings.temp_storage_path) / "screenshots" / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            context_options = {"viewport": {"width": viewport.width, "height": viewport.height}}
            
            async with self.browser_manager.page_context(**context_options) as page:
                if url:
                    await self.browser_manager.navigate_to_url(page, url, wait_for="networkidle")
                elif html_content:
                    # FIX: Navigate to about:blank first to establish a stable context, then set content.
                    await page.goto("about:blank")
                    await page.set_content(html_content, wait_until="networkidle")
                
                if wait_for_load:
                    await page.wait_for_timeout(2000)
                
                await page.screenshot(path=str(file_path), full_page=full_page, type="jpeg", quality=quality)
                
                return ScreenshotResult(
                    viewport=viewport,
                    file_path=str(file_path),
                    file_size=file_path.stat().st_size,
                    capture_time=time.time() - float(file_path.stat().st_ctime),
                    url=url
                )
        except Exception as e:
            error_msg = f"Screenshot capture failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return ScreenshotResult(
                viewport=viewport, file_path="", file_size=0, capture_time=0, url=url, success=False, error=error_msg
            )
            
    def _generate_filename(self, url: Optional[str], html_content: Optional[str], viewport: Viewport, session_id: str) -> str:
        source_hash = hashlib.md5((url or html_content or "").encode()).hexdigest()[:8]
        timestamp = int(time.time())
        suffix = "original" if url else "generated"
        return f"{session_id}_{suffix}_{viewport.name.lower()}_{timestamp}.jpg"

# Global instance
screenshot_service = ScreenshotService()
