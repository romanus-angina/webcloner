from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from typing import List, Optional
from datetime import datetime, UTC
from pathlib import Path
import time

from ...dependencies import (
    get_app_state,
    get_browser_manager,
    get_logger,
    get_request_id,
    validate_session_id,
    check_rate_limit,
    ApplicationState
)
from ...config import settings
from ...services.screenshot_service import ScreenshotService, ViewportType
from ...services.browser_manager import BrowserManager
from ...models.screenshot import (
    ScreenshotRequest,
    ScreenshotResponse,
    ScreenshotStatusResponse,
    ScreenshotCleanupResponse,
    ViewportPresetsResponse,
    ViewportPresetResponse,
    ViewportModel,
    ScreenshotBatchModel,
    ScreenshotResultModel,
    ScreenshotSessionInfo,
    ScreenshotInfoModel
)
from ...core.exceptions import ValidationError, ProcessingError
import logging

router = APIRouter()


@router.get("/viewports/presets", response_model=ViewportPresetsResponse)
async def get_viewport_presets():
    """
    Get available viewport presets for screenshot capture.
    
    Returns:
        Available viewport configurations for different device types
    """
    screenshot_service = ScreenshotService()
    
    presets = []
    for viewport_type in ViewportType:
        if viewport_type == ViewportType.CUSTOM:
            continue
            
        try:
            viewport = screenshot_service.get_viewport_by_type(viewport_type)
            preset = ViewportPresetResponse(
                viewport_type=viewport_type,
                viewport=ViewportModel(
                    name=viewport.name,
                    width=viewport.width,
                    height=viewport.height,
                    device_scale_factor=viewport.device_scale_factor,
                    is_mobile=viewport.is_mobile,
                    user_agent=viewport.user_agent
                )
            )
            presets.append(preset)
        except KeyError:
            continue
    
    return ViewportPresetsResponse(
        presets=presets,
        custom_supported=True,
        max_custom_viewports=10
    )


@router.post("/capture", response_model=ScreenshotResponse)
async def capture_screenshots(
    request: ScreenshotRequest,
    background_tasks: BackgroundTasks,
    browser_manager: BrowserManager = Depends(get_browser_manager),
    app_state: ApplicationState = Depends(get_app_state),
    logger: logging.Logger = Depends(get_logger),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
):
    """
    Capture screenshots at multiple viewports for a given URL.
    
    Args:
        request: Screenshot capture request parameters
        background_tasks: FastAPI background tasks
        
    Returns:
        Screenshot capture results
    """
    logger.info(f"Starting screenshot capture for URL: {request.url}")
    
    try:
        # Initialize screenshot service with browser manager
        screenshot_service = ScreenshotService(browser_manager)
        
        # Determine viewports to use
        viewports = []
        
        if request.viewports:
            # Convert ViewportModel to Viewport dataclass
            for vm in request.viewports:
                viewport = screenshot_service.create_custom_viewport(
                    name=vm.name,
                    width=vm.width,
                    height=vm.height,
                    device_scale_factor=vm.device_scale_factor,
                    is_mobile=vm.is_mobile,
                    user_agent=vm.user_agent
                )
                viewports.append(viewport)
        
        elif request.viewport_types:
            # Use specified viewport types
            for vt in request.viewport_types:
                if vt != ViewportType.CUSTOM:
                    try:
                        viewport = screenshot_service.get_viewport_by_type(vt)
                        viewports.append(viewport)
                    except KeyError:
                        logger.warning(f"Unknown viewport type: {vt}")
                        continue
        
        else:
            # Use default viewports
            viewports = screenshot_service.get_default_viewports()
        
        if not viewports:
            raise ValidationError("No valid viewports specified")
        
        # Capture screenshots
        screenshot_batch = await screenshot_service.capture_multi_viewport_screenshots(
            url=request.url,
            session_id=request.session_id,
            viewports=viewports,
            concurrent=request.concurrent,
            max_concurrent=request.max_concurrent,
            wait_for_load=request.wait_for_load,
            full_page=request.full_page,
            quality=request.quality
        )
        
        # Convert to response model
        screenshot_results = []
        for result in screenshot_batch.screenshots:
            screenshot_result = ScreenshotResultModel(
                viewport_name=result.viewport.name,
                viewport_width=result.viewport.width,
                viewport_height=result.viewport.height,
                file_path=result.file_path,
                file_size=result.file_size,
                capture_time=result.capture_time,
                page_title=result.page_title,
                page_dimensions={
                    "width": result.page_dimensions[0],
                    "height": result.page_dimensions[1]
                } if result.page_dimensions else None,
                success=result.success,
                error=result.error,
                timestamp=datetime.fromtimestamp(result.timestamp, UTC)
            )
            screenshot_results.append(screenshot_result)
        
        batch_model = ScreenshotBatchModel(
            url=screenshot_batch.url,
            session_id=screenshot_batch.session_id,
            screenshots=screenshot_results,
            total_capture_time=screenshot_batch.total_capture_time,
            created_at=datetime.fromtimestamp(screenshot_batch.created_at, UTC),
            success_count=len(screenshot_batch.successful_screenshots),
            failure_count=len(screenshot_batch.failed_screenshots),
            success_rate=screenshot_batch.success_rate
        )
        
        # Update session state with screenshot info
        app_state.update_session(request.session_id, {
            "screenshots_captured": True,
            "screenshot_count": len(screenshot_results),
            "screenshot_success_rate": screenshot_batch.success_rate,
            "last_screenshot_batch": batch_model.model_dump()
        })
        
        success_count = len(screenshot_batch.successful_screenshots)
        total_count = len(screenshot_batch.screenshots)
        
        logger.info(
            f"Screenshot capture completed: {success_count}/{total_count} successful "
            f"for session {request.session_id}"
        )
        
        return ScreenshotResponse(
            success=True,
            message=f"Captured {success_count}/{total_count} screenshots successfully",
            data=batch_model,
            session_id=request.session_id,
            timestamp=datetime.now(UTC)
        )
        
    except Exception as e:
        logger.error(f"Screenshot capture failed for session {request.session_id}: {str(e)}")
        
        return ScreenshotResponse(
            success=False,
            message=f"Screenshot capture failed: {str(e)}",
            data=None,
            session_id=request.session_id,
            timestamp=datetime.now(UTC)
        )


@router.get("/session/{session_id}/screenshots", response_model=ScreenshotStatusResponse)
async def get_session_screenshots(
    session_id: str = Depends(validate_session_id),
    browser_manager: BrowserManager = Depends(get_browser_manager)
):
    """
    Get screenshot information for a specific session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Screenshot status and file information
    """
    screenshot_service = ScreenshotService(browser_manager)
    
    screenshots_info = await screenshot_service.get_screenshot_info(session_id)
    
    # Convert to response models
    screenshot_models = []
    for info in screenshots_info["screenshots"]:
        screenshot_model = ScreenshotInfoModel(
            filename=info["filename"],
            size=info["size"],
            created=datetime.fromtimestamp(info["created"], UTC),
            viewport_name=info.get("viewport_name"),
            dimensions=info.get("dimensions"),
            path=info["path"]
        )
        screenshot_models.append(screenshot_model)
    
    session_info = ScreenshotSessionInfo(
        session_id=screenshots_info["session_id"],
        screenshot_count=screenshots_info["screenshot_count"],
        total_size=screenshots_info["total_size"],
        screenshots=screenshot_models
    )
    
    return ScreenshotStatusResponse(
        session_id=session_id,
        status="available" if screenshots_info["screenshot_count"] > 0 else "no_screenshots",
        screenshots_info=session_info,
        timestamp=datetime.now(UTC)
    )


@router.delete("/session/{session_id}/screenshots", response_model=ScreenshotCleanupResponse)
async def cleanup_session_screenshots(
    session_id: str = Depends(validate_session_id),
    browser_manager: BrowserManager = Depends(get_browser_manager),
    logger: logging.Logger = Depends(get_logger)
):
    """
    Clean up screenshots for a specific session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Cleanup results
    """
    screenshot_service = ScreenshotService(browser_manager)
    
    # Get current info for calculating freed space
    before_info = await screenshot_service.get_screenshot_info(session_id)
    total_size_before = before_info["total_size"]
    
    # Perform cleanup
    cleaned_count = await screenshot_service.cleanup_screenshots(session_id=session_id)
    
    logger.info(f"Cleaned up {cleaned_count} screenshots for session {session_id}")
    
    return ScreenshotCleanupResponse(
        cleaned_count=cleaned_count,
        total_freed_bytes=total_size_before,
        session_id=session_id,
        timestamp=datetime.now(UTC)
    )


@router.delete("/cleanup", response_model=ScreenshotCleanupResponse)
async def cleanup_old_screenshots(
    older_than_hours: int = Query(default=24, ge=1),
    browser_manager: BrowserManager = Depends(get_browser_manager),
    logger: logging.Logger = Depends(get_logger)
):
    """
    Clean up old screenshot files.
    
    Args:
        older_than_hours: Clean files older than this many hours
        
    Returns:
        Cleanup results
    """
    screenshot_service = ScreenshotService(browser_manager)
    
    # Get total size before cleanup for calculating freed space
    screenshots_dir = Path(settings.temp_storage_path) / "screenshots"
    total_size_before = 0
    
    if screenshots_dir.exists():
        for file_path in screenshots_dir.glob("*.jpg"):
            try:
                total_size_before += file_path.stat().st_size
            except:
                pass
    
    # Perform cleanup
    cleaned_count = await screenshot_service.cleanup_screenshots(
        older_than_hours=older_than_hours
    )
    
    # Calculate freed space
    total_size_after = 0
    if screenshots_dir.exists():
        for file_path in screenshots_dir.glob("*.jpg"):
            try:
                total_size_after += file_path.stat().st_size
            except:
                pass
    
    freed_bytes = total_size_before - total_size_after
    
    logger.info(f"Cleaned up {cleaned_count} old screenshots, freed {freed_bytes} bytes")
    
    return ScreenshotCleanupResponse(
        cleaned_count=cleaned_count,
        total_freed_bytes=freed_bytes,
        session_id=None,
        timestamp=datetime.now(UTC)
    )


@router.post("/session/{session_id}/screenshots/regenerate", response_model=ScreenshotResponse)
async def regenerate_session_screenshots(
    session_id: str = Depends(validate_session_id),
    viewport_types: Optional[List[ViewportType]] = Query(default=None),
    app_state: ApplicationState = Depends(get_app_state),
    browser_manager: BrowserManager = Depends(get_browser_manager),
    logger: logging.Logger = Depends(get_logger),
    _: None = Depends(check_rate_limit)
):
    """
    Regenerate screenshots for an existing session.
    
    Args:
        session_id: Session identifier
        viewport_types: Specific viewport types to regenerate (optional)
        
    Returns:
        New screenshot capture results
    """
    # Get session data to find original URL
    session_data = app_state.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    # Extract URL from session data
    original_request = session_data.get("request", {})
    url = original_request.get("url")
    
    if not url:
        raise ValidationError("No URL found in session data for regeneration")
    
    logger.info(f"Regenerating screenshots for session {session_id}, URL: {url}")
    
    # Clean up existing screenshots first
    screenshot_service = ScreenshotService(browser_manager)
    await screenshot_service.cleanup_screenshots(session_id=session_id)
    
    # Create new screenshot request
    screenshot_request = ScreenshotRequest(
        url=url,
        session_id=session_id,
        viewport_types=viewport_types or [ViewportType.MOBILE, ViewportType.DESKTOP],
        concurrent=True,
        max_concurrent=3,
        wait_for_load=True,
        full_page=True,
        quality=90
    )
    
    # Use the main capture endpoint logic (simplified version for regeneration)
    try:
        screenshot_service = ScreenshotService(browser_manager)
        
        # Get viewports
        viewports = []
        for vt in screenshot_request.viewport_types or [ViewportType.MOBILE, ViewportType.DESKTOP]:
            if vt != ViewportType.CUSTOM:
                try:
                    viewport = screenshot_service.get_viewport_by_type(vt)
                    viewports.append(viewport)
                except KeyError:
                    continue
        
        # Capture screenshots
        screenshot_batch = await screenshot_service.capture_multi_viewport_screenshots(
            url=screenshot_request.url,
            session_id=screenshot_request.session_id,
            viewports=viewports,
            concurrent=True,
            max_concurrent=3
        )
        
        return ScreenshotResponse(
            success=True,
            message=f"Regenerated {len(screenshot_batch.successful_screenshots)} screenshots",
            data=None,  # Simplified for regeneration
            session_id=session_id,
            timestamp=datetime.now(UTC)
        )
        
    except Exception as e:
        logger.error(f"Screenshot regeneration failed: {str(e)}")
        return ScreenshotResponse(
            success=False,
            message=f"Regeneration failed: {str(e)}",
            data=None,
            session_id=session_id,
            timestamp=datetime.now(UTC)
        )


@router.get("/stats")
async def get_screenshot_statistics(
    browser_manager: BrowserManager = Depends(get_browser_manager)
):
    """
    Get global screenshot statistics.
    
    Returns:
        Statistics about screenshot storage and usage
    """
    screenshots_dir = Path(settings.temp_storage_path) / "screenshots"
    
    if not screenshots_dir.exists():
        return {
            "total_files": 0,
            "total_size": 0,
            "disk_usage": "0 bytes",
            "oldest_file": None,
            "newest_file": None,
            "average_file_size": 0
        }
    
    files = list(screenshots_dir.glob("*.jpg"))
    
    if not files:
        return {
            "total_files": 0,
            "total_size": 0,
            "disk_usage": "0 bytes",
            "oldest_file": None,
            "newest_file": None,
            "average_file_size": 0
        }
    
    total_size = 0
    file_times = []
    
    for file_path in files:
        try:
            stat = file_path.stat()
            total_size += stat.st_size
            file_times.append(stat.st_mtime)
        except:
            continue
    
    def format_bytes(bytes_value):
        """Format bytes into human readable format."""
        for unit in ['bytes', 'KB', 'MB', 'GB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} TB"
    
    oldest_time = min(file_times) if file_times else None
    newest_time = max(file_times) if file_times else None
    
    return {
        "total_files": len(files),
        "total_size": total_size,
        "disk_usage": format_bytes(total_size),
        "oldest_file": datetime.fromtimestamp(oldest_time, UTC).isoformat() if oldest_time else None,
        "newest_file": datetime.fromtimestamp(newest_time, UTC).isoformat() if newest_time else None,
        "average_file_size": total_size // len(files) if files else 0,
        "average_file_size_formatted": format_bytes(total_size // len(files)) if files else "0 bytes"
    }