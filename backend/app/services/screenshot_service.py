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
    """Standard viewport types for responsive design."""
    MOBILE = "mobile"
    TABLET = "tablet"
    DESKTOP = "desktop"
    LARGE_DESKTOP = "large_desktop"
    CUSTOM = "custom"


@dataclass
class Viewport:
    """Viewport configuration for screenshots."""
    name: str
    width: int
    height: int
    device_scale_factor: float = 1.0
    is_mobile: bool = False
    user_agent: Optional[str] = None
    
    def __post_init__(self):
        """Validate viewport configuration."""
        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"Invalid viewport dimensions: {self.width}x{self.height}")
        if self.device_scale_factor <= 0:
            raise ValueError(f"Invalid device scale factor: {self.device_scale_factor}")


@dataclass
class ScreenshotResult:
    """Result of a screenshot capture operation."""
    viewport: Viewport
    file_path: str
    file_size: int
    capture_time: float
    url: str
    timestamp: float
    page_title: Optional[str] = None
    page_dimensions: Optional[Tuple[int, int]] = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class ScreenshotBatch:
    """Collection of screenshot results for a URL."""
    url: str
    session_id: str
    screenshots: List[ScreenshotResult]
    total_capture_time: float
    created_at: float
    
    @property
    def successful_screenshots(self) -> List[ScreenshotResult]:
        """Get only successful screenshots."""
        return [s for s in self.screenshots if s.success]
    
    @property
    def failed_screenshots(self) -> List[ScreenshotResult]:
        """Get only failed screenshots."""
        return [s for s in self.screenshots if not s.success]
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if not self.screenshots:
            return 0.0
        return (len(self.successful_screenshots) / len(self.screenshots)) * 100


class ScreenshotService:
    """
    Service for capturing screenshots at multiple viewports.
    
    Provides high-level interface for capturing website screenshots
    across different device types and screen sizes for responsive
    design analysis.
    """
    
    def __init__(self, browser_manager: Optional[BrowserManager] = None):
        self.browser_manager = browser_manager
        self._default_viewports = self._create_default_viewports()
        
    def _create_default_viewports(self) -> Dict[ViewportType, Viewport]:
        """Create default viewport configurations for common devices."""
        return {
            ViewportType.MOBILE: Viewport(
                name="Mobile",
                width=375,
                height=667,
                device_scale_factor=2.0,
                is_mobile=True,
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"
            ),
            ViewportType.TABLET: Viewport(
                name="Tablet",
                width=768,
                height=1024,
                device_scale_factor=2.0,
                is_mobile=False,
                user_agent="Mozilla/5.0 (iPad; CPU OS 14_0 like Mac OS X) AppleWebKit/605.1.15"
            ),
            ViewportType.DESKTOP: Viewport(
                name="Desktop",
                width=1920,
                height=1080,
                device_scale_factor=1.0,
                is_mobile=False
            ),
            ViewportType.LARGE_DESKTOP: Viewport(
                name="Large Desktop",
                width=2560,
                height=1440,
                device_scale_factor=1.0,
                is_mobile=False
            )
        }
    
    def get_default_viewports(self) -> List[Viewport]:
        """Get list of default viewports."""
        return list(self._default_viewports.values())
    
    def get_viewport_by_type(self, viewport_type: ViewportType) -> Viewport:
        """Get viewport configuration by type."""
        return self._default_viewports[viewport_type]
    
    def create_custom_viewport(
        self,
        name: str,
        width: int,
        height: int,
        device_scale_factor: float = 1.0,
        is_mobile: bool = False,
        user_agent: Optional[str] = None
    ) -> Viewport:
        """Create a custom viewport configuration."""
        return Viewport(
            name=name,
            width=width,
            height=height,
            device_scale_factor=device_scale_factor,
            is_mobile=is_mobile,
            user_agent=user_agent
        )
    
    async def capture_screenshot(
        self,
        url: str,
        viewport: Viewport,
        session_id: str,
        wait_for_load: bool = True,
        full_page: bool = True,
        quality: int = 90
    ) -> ScreenshotResult:
        """
        Capture a single screenshot at the specified viewport.
        
        Args:
            url: URL to capture
            viewport: Viewport configuration
            session_id: Session identifier for file organization
            wait_for_load: Whether to wait for page load completion
            full_page: Whether to capture full page or just viewport
            quality: JPEG quality (1-100)
            
        Returns:
            ScreenshotResult with capture details
        """
        start_time = time.time()
        
        logger.info(f"Capturing screenshot for {url} at {viewport.name} ({viewport.width}x{viewport.height})")
        
        try:
            # Generate filename
            filename = self._generate_filename(url, viewport, session_id)
            file_path = Path(settings.temp_storage_path) / "screenshots" / filename
            
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            if not self.browser_manager:
                raise BrowserError("Browser manager not available")
            
            # Configure context for this viewport
            context_options = {
                "viewport": {
                    "width": viewport.width,
                    "height": viewport.height
                },
                "device_scale_factor": viewport.device_scale_factor,
                "is_mobile": viewport.is_mobile
            }
            
            if viewport.user_agent:
                context_options["user_agent"] = viewport.user_agent
            
            # Capture screenshot using browser manager
            async with self.browser_manager.page_context(**context_options) as page:
                # Navigate to URL
                await self.browser_manager.navigate_to_url(page, url, wait_for="networkidle")
                
                if wait_for_load:
                    await self.browser_manager.wait_for_page_load(page)
                    # Additional wait for dynamic content
                    await page.wait_for_timeout(2000)
                
                # Get page info
                page_title = await page.title()
                
                # Get page dimensions if capturing full page
                page_dimensions = None
                if full_page:
                    # Get actual page dimensions
                    dimensions = await page.evaluate("""
                        () => {
                            return {
                                width: Math.max(
                                    document.body.scrollWidth,
                                    document.body.offsetWidth,
                                    document.documentElement.clientWidth,
                                    document.documentElement.scrollWidth,
                                    document.documentElement.offsetWidth
                                ),
                                height: Math.max(
                                    document.body.scrollHeight,
                                    document.body.offsetHeight,
                                    document.documentElement.clientHeight,
                                    document.documentElement.scrollHeight,
                                    document.documentElement.offsetHeight
                                )
                            };
                        }
                    """)
                    page_dimensions = (dimensions['width'], dimensions['height'])
                
                # Configure screenshot options
                screenshot_options = {
                    "path": str(file_path),
                    "full_page": full_page,
                    "type": "jpeg",
                    "quality": quality
                }
                
                # Take screenshot
                await page.screenshot(**screenshot_options)
                
                # Get file size
                file_size = file_path.stat().st_size
                capture_time = time.time() - start_time
                
                logger.info(
                    f"Screenshot captured successfully: {filename} "
                    f"({file_size} bytes, {capture_time:.2f}s)"
                )
                
                return ScreenshotResult(
                    viewport=viewport,
                    file_path=str(file_path),
                    file_size=file_size,
                    capture_time=capture_time,
                    url=url,
                    timestamp=time.time(),
                    page_title=page_title,
                    page_dimensions=page_dimensions,
                    success=True
                )
                
        except Exception as e:
            capture_time = time.time() - start_time
            error_msg = f"Screenshot capture failed for {viewport.name}: {str(e)}"
            logger.error(error_msg)
            
            return ScreenshotResult(
                viewport=viewport,
                file_path="",
                file_size=0,
                capture_time=capture_time,
                url=url,
                timestamp=time.time(),
                success=False,
                error=error_msg
            )
    
    async def capture_multi_viewport_screenshots(
        self,
        url: str,
        session_id: str,
        viewports: Optional[List[Viewport]] = None,
        concurrent: bool = True,
        max_concurrent: int = 3,
        **screenshot_options
    ) -> ScreenshotBatch:
        """
        Capture screenshots at multiple viewports.
        
        Args:
            url: URL to capture
            session_id: Session identifier
            viewports: List of viewports to capture (uses defaults if None)
            concurrent: Whether to capture screenshots concurrently
            max_concurrent: Maximum concurrent captures
            **screenshot_options: Additional options for screenshot capture
            
        Returns:
            ScreenshotBatch with all results
        """
        start_time = time.time()
        
        if viewports is None:
            viewports = self.get_default_viewports()
        
        logger.info(f"Capturing {len(viewports)} screenshots for {url}")
        
        if concurrent:
            screenshots = await self._capture_concurrent(
                url, session_id, viewports, max_concurrent, **screenshot_options
            )
        else:
            screenshots = await self._capture_sequential(
                url, session_id, viewports, **screenshot_options
            )
        
        total_time = time.time() - start_time
        
        batch = ScreenshotBatch(
            url=url,
            session_id=session_id,
            screenshots=screenshots,
            total_capture_time=total_time,
            created_at=time.time()
        )
        
        success_count = len(batch.successful_screenshots)
        total_count = len(batch.screenshots)
        
        logger.info(
            f"Screenshot batch completed: {success_count}/{total_count} successful "
            f"({batch.success_rate:.1f}%) in {total_time:.2f}s"
        )
        
        return batch
    
    async def _capture_concurrent(
        self,
        url: str,
        session_id: str,
        viewports: List[Viewport],
        max_concurrent: int,
        **screenshot_options
    ) -> List[ScreenshotResult]:
        """Capture screenshots concurrently with concurrency limit."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def capture_with_semaphore(viewport: Viewport):
            async with semaphore:
                return await self.capture_screenshot(
                    url, viewport, session_id, **screenshot_options
                )
        
        tasks = [capture_with_semaphore(viewport) for viewport in viewports]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        screenshots = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Screenshot task failed for {viewports[i].name}: {str(result)}")
                screenshots.append(ScreenshotResult(
                    viewport=viewports[i],
                    file_path="",
                    file_size=0,
                    capture_time=0.0,
                    url=url,
                    timestamp=time.time(),
                    success=False,
                    error=str(result)
                ))
            else:
                screenshots.append(result)
        
        return screenshots
    
    async def _capture_sequential(
        self,
        url: str,
        session_id: str,
        viewports: List[Viewport],
        **screenshot_options
    ) -> List[ScreenshotResult]:
        """Capture screenshots sequentially."""
        screenshots = []
        
        for viewport in viewports:
            try:
                result = await self.capture_screenshot(
                    url, viewport, session_id, **screenshot_options
                )
                screenshots.append(result)
            except Exception as e:
                logger.error(f"Sequential screenshot failed for {viewport.name}: {str(e)}")
                screenshots.append(ScreenshotResult(
                    viewport=viewport,
                    file_path="",
                    file_size=0,
                    capture_time=0.0,
                    url=url,
                    timestamp=time.time(),
                    success=False,
                    error=str(e)
                ))
        
        return screenshots
    
    def _generate_filename(self, url: str, viewport: Viewport, session_id: str) -> str:
        """Generate unique filename for screenshot."""
        # Create URL hash for uniqueness
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        
        # Clean viewport name for filename
        viewport_name = viewport.name.lower().replace(" ", "_")
        
        # Include dimensions for clarity
        dimensions = f"{viewport.width}x{viewport.height}"
        
        # Create timestamp
        timestamp = int(time.time())
        
        return f"{session_id}_{url_hash}_{viewport_name}_{dimensions}_{timestamp}.jpg"
    
    async def cleanup_screenshots(
        self,
        session_id: Optional[str] = None,
        older_than_hours: Optional[int] = None
    ) -> int:
        """
        Clean up screenshot files.
        
        Args:
            session_id: Clean up specific session (if None, cleans all)
            older_than_hours: Only clean files older than this many hours
            
        Returns:
            Number of files cleaned up
        """
        screenshots_dir = Path(settings.temp_storage_path) / "screenshots"
        
        if not screenshots_dir.exists():
            return 0
        
        cleaned_count = 0
        current_time = time.time()
        
        for file_path in screenshots_dir.glob("*.jpg"):
            # Check session filter
            if session_id and not file_path.name.startswith(f"{session_id}_"):
                continue
            
            # Check age filter
            if older_than_hours:
                file_age_hours = (current_time - file_path.stat().st_mtime) / 3600
                if file_age_hours < older_than_hours:
                    continue
            
            try:
                file_path.unlink()
                cleaned_count += 1
                logger.debug(f"Cleaned up screenshot: {file_path.name}")
            except Exception as e:
                logger.warning(f"Failed to clean up {file_path.name}: {str(e)}")
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} screenshot files")
        
        return cleaned_count
    
    async def get_screenshot_info(self, session_id: str) -> Dict[str, Any]:
        """
        Get information about screenshots for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with screenshot information
        """
        screenshots_dir = Path(settings.temp_storage_path) / "screenshots"
        
        if not screenshots_dir.exists():
            return {"session_id": session_id, "screenshots": []}
        
        screenshot_files = list(screenshots_dir.glob(f"{session_id}_*.jpg"))
        
        screenshots_info = []
        total_size = 0
        
        for file_path in screenshot_files:
            try:
                stat = file_path.stat()
                # Parse filename to extract info
                name_parts = file_path.stem.split("_")
                
                info = {
                    "filename": file_path.name,
                    "size": stat.st_size,
                    "created": stat.st_mtime,
                    "path": str(file_path)
                }
                
                # Try to extract viewport info from filename
                if len(name_parts) >= 4:
                    info["viewport_name"] = name_parts[2].replace("_", " ").title()
                    info["dimensions"] = name_parts[3]
                
                screenshots_info.append(info)
                total_size += stat.st_size
                
            except Exception as e:
                logger.warning(f"Error getting info for {file_path.name}: {str(e)}")
        
        return {
            "session_id": session_id,
            "screenshot_count": len(screenshots_info),
            "total_size": total_size,
            "screenshots": screenshots_info
        }


# Global screenshot service instance
screenshot_service = ScreenshotService()