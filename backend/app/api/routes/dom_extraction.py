from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from typing import List, Optional, Dict, Any
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
from ...services.dom_extraction_service import DOMExtractionService, DOMExtractionResult
from ...services.browser_manager import BrowserManager
from ...models.dom_extraction import (
    DOMExtractionRequest,
    DOMExtractionResponse,
    DOMExtractionStatusResponse,
    DOMExtractionCleanupResponse,
    DOMComplexityResponse,
    DOMExtractionInfoResponse,
    DOMExtractionSessionInfo,
    DOMExtractionFileInfo
)
from ...core.exceptions import ValidationError, ProcessingError
import logging

router = APIRouter()


@router.post("/extract", response_model=DOMExtractionResponse)
async def extract_dom_structure(
    request: DOMExtractionRequest,
    background_tasks: BackgroundTasks,
    browser_manager: BrowserManager = Depends(get_browser_manager),
    app_state: ApplicationState = Depends(get_app_state),
    logger: logging.Logger = Depends(get_logger),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
):
    """
    Extract DOM structure, styles, and assets from a web page.
    
    Args:
        request: DOM extraction request parameters
        background_tasks: FastAPI background tasks
        
    Returns:
        DOM extraction results
    """
    logger.info(f"Starting DOM extraction for URL: {request.url}")
    
    try:
        # Initialize DOM extraction service with browser manager
        extraction_service = DOMExtractionService(browser_manager)
        
        # Perform extraction
        result = await extraction_service.extract_dom_structure(
            url=request.url,
            session_id=request.session_id,
            wait_for_load=request.wait_for_load,
            include_computed_styles=request.include_computed_styles,
            max_depth=request.max_depth
        )
        
        # Save result if requested
        saved_file_path = None
        if request.save_result:
            saved_file_path = await extraction_service.save_extraction_result(
                result, 
                output_format=request.output_format
            )
        
        # Update session state with extraction info
        app_state.update_session(request.session_id, {
            "dom_extracted": True,
            "extraction_success": result.success,
            "extraction_time": result.extraction_time,
            "total_elements": result.total_elements,
            "total_stylesheets": result.total_stylesheets,
            "total_assets": result.total_assets,
            "last_extraction_result": result.__dict__ if result.success else None
        })
        
        logger.info(
            f"DOM extraction completed: {result.total_elements} elements, "
            f"{result.total_stylesheets} stylesheets, {result.total_assets} assets "
            f"for session {request.session_id}"
        )
        
        return DOMExtractionResponse(
            success=result.success,
            message=f"Extracted {result.total_elements} elements successfully" if result.success 
                   else f"Extraction failed: {result.error_message}",
            extraction_result=result,
            saved_file_path=saved_file_path,
            session_id=request.session_id,
            timestamp=datetime.now(UTC)
        )
        
    except Exception as e:
        logger.error(f"DOM extraction failed for session {request.session_id}: {str(e)}")
        
        return DOMExtractionResponse(
            success=False,
            message=f"DOM extraction failed: {str(e)}",
            extraction_result=None,
            saved_file_path=None,
            session_id=request.session_id,
            timestamp=datetime.now(UTC)
        )


@router.get("/session/{session_id}/status", response_model=DOMExtractionStatusResponse)
async def get_extraction_status(
    session_id: str = Depends(validate_session_id),
    browser_manager: BrowserManager = Depends(get_browser_manager)
):
    """
    Get DOM extraction status and information for a specific session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        DOM extraction status and file information
    """
    extraction_service = DOMExtractionService(browser_manager)
    
    extraction_info = await extraction_service.get_extraction_info(session_id)
    
    # Convert to response models
    extraction_models = []
    for info in extraction_info["extractions"]:
        extraction_model = DOMExtractionFileInfo(
            filename=info["filename"],
            size=info["size"],
            created=datetime.fromtimestamp(info["created"], UTC),
            path=info["path"]
        )
        extraction_models.append(extraction_model)
    
    session_info = DOMExtractionSessionInfo(
        session_id=extraction_info["session_id"],
        extraction_count=extraction_info["extraction_count"],
        total_size=extraction_info["total_size"],
        extractions=extraction_models
    )
    
    return DOMExtractionStatusResponse(
        session_id=session_id,
        status="available" if extraction_info["extraction_count"] > 0 else "no_extractions",
        extraction_info=session_info,
        timestamp=datetime.now(UTC)
    )


@router.post("/analyze-complexity", response_model=DOMComplexityResponse)
async def analyze_page_complexity(
    request: DOMExtractionRequest,
    browser_manager: BrowserManager = Depends(get_browser_manager),
    logger: logging.Logger = Depends(get_logger),
    _: None = Depends(check_rate_limit)
):
    """
    Analyze page complexity without full extraction.
    
    Args:
        request: DOM extraction request parameters
        
    Returns:
        Page complexity analysis
    """
    logger.info(f"Analyzing page complexity for URL: {request.url}")
    
    try:
        extraction_service = DOMExtractionService(browser_manager)
        
        # Perform lightweight extraction for complexity analysis
        result = await extraction_service.extract_dom_structure(
            url=request.url,
            session_id=request.session_id,
            wait_for_load=request.wait_for_load,
            include_computed_styles=False,  # Skip detailed styles for faster analysis
            max_depth=5  # Limit depth for performance
        )
        
        if not result.success:
            raise ProcessingError(f"Failed to extract page for analysis: {result.error_message}")
        
        # Analyze complexity
        complexity_analysis = await extraction_service.analyze_page_complexity(result)
        
        logger.info(f"Complexity analysis completed for {request.url}: score {complexity_analysis['overall_score']:.1f}")
        
        return DOMComplexityResponse(
            success=True,
            message="Complexity analysis completed successfully",
            complexity_analysis=complexity_analysis,
            extraction_metrics={
                "total_elements": result.total_elements,
                "total_stylesheets": result.total_stylesheets,
                "total_assets": result.total_assets,
                "dom_depth": result.dom_depth,
                "extraction_time": result.extraction_time
            },
            session_id=request.session_id,
            timestamp=datetime.now(UTC)
        )
        
    except Exception as e:
        logger.error(f"Complexity analysis failed for {request.url}: {str(e)}")
        
        return DOMComplexityResponse(
            success=False,
            message=f"Complexity analysis failed: {str(e)}",
            complexity_analysis={},
            extraction_metrics={},
            session_id=request.session_id,
            timestamp=datetime.now(UTC)
        )


@router.delete("/session/{session_id}/extractions", response_model=DOMExtractionCleanupResponse)
async def cleanup_session_extractions(
    session_id: str = Depends(validate_session_id),
    browser_manager: BrowserManager = Depends(get_browser_manager),
    logger: logging.Logger = Depends(get_logger)
):
    """
    Clean up DOM extraction files for a specific session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Cleanup results
    """
    extraction_service = DOMExtractionService(browser_manager)
    
    # Get current info for calculating freed space
    before_info = await extraction_service.get_extraction_info(session_id)
    total_size_before = before_info["total_size"]
    
    # Perform cleanup
    cleaned_count = await extraction_service.cleanup_extractions(session_id=session_id)
    
    logger.info(f"Cleaned up {cleaned_count} extraction files for session {session_id}")
    
    return DOMExtractionCleanupResponse(
        cleaned_count=cleaned_count,
        total_freed_bytes=total_size_before,
        session_id=session_id,
        timestamp=datetime.now(UTC)
    )


@router.delete("/cleanup", response_model=DOMExtractionCleanupResponse)
async def cleanup_old_extractions(
    older_than_hours: int = Query(default=24, ge=1),
    browser_manager: BrowserManager = Depends(get_browser_manager),
    logger: logging.Logger = Depends(get_logger)
):
    """
    Clean up old DOM extraction files.
    
    Args:
        older_than_hours: Clean files older than this many hours
        
    Returns:
        Cleanup results
    """
    extraction_service = DOMExtractionService(browser_manager)
    
    # Get total size before cleanup for calculating freed space
    extractions_dir = Path(settings.temp_storage_path) / "extractions"
    total_size_before = 0
    
    if extractions_dir.exists():
        for file_path in extractions_dir.glob("*.json"):
            try:
                total_size_before += file_path.stat().st_size
            except:
                pass
    
    # Perform cleanup
    cleaned_count = await extraction_service.cleanup_extractions(
        older_than_hours=older_than_hours
    )
    
    # Calculate freed space
    total_size_after = 0
    if extractions_dir.exists():
        for file_path in extractions_dir.glob("*.json"):
            try:
                total_size_after += file_path.stat().st_size
            except:
                pass
    
    freed_bytes = total_size_before - total_size_after
    
    logger.info(f"Cleaned up {cleaned_count} old extraction files, freed {freed_bytes} bytes")
    
    return DOMExtractionCleanupResponse(
        cleaned_count=cleaned_count,
        total_freed_bytes=freed_bytes,
        session_id=None,
        timestamp=datetime.now(UTC)
    )


@router.post("/session/{session_id}/regenerate", response_model=DOMExtractionResponse)
async def regenerate_extraction(
    extraction_request: DOMExtractionRequest,
    session_id: str = Depends(validate_session_id),
    app_state: ApplicationState = Depends(get_app_state),
    browser_manager: BrowserManager = Depends(get_browser_manager),
    logger: logging.Logger = Depends(get_logger),
    _: None = Depends(check_rate_limit)
):
    """
    Regenerate DOM extraction for an existing session.
    
    Args:
        extraction_request: DOM extraction parameters
        session_id: Session identifier
        
    Returns:
        New DOM extraction results
    """
    # Get session data to find original URL if not provided
    session_data = app_state.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    # Use URL from request or fall back to session data
    url = extraction_request.url
    if not url:
        original_request = session_data.get("request", {})
        url = original_request.get("url")
        
        if not url:
            raise ValidationError("No URL found in session data for regeneration")
    
    logger.info(f"Regenerating DOM extraction for session {session_id}, URL: {url}")
    
    # Clean up existing extractions first
    extraction_service = DOMExtractionService(browser_manager)
    await extraction_service.cleanup_extractions(session_id=session_id)
    
    # Create new extraction request with session ID
    new_request = DOMExtractionRequest(
        url=url,
        session_id=session_id,
        wait_for_load=extraction_request.wait_for_load,
        include_computed_styles=extraction_request.include_computed_styles,
        max_depth=extraction_request.max_depth,
        save_result=extraction_request.save_result,
        output_format=extraction_request.output_format
    )
    
    # Use the main extract endpoint logic
    try:
        result = await extraction_service.extract_dom_structure(
            url=new_request.url,
            session_id=new_request.session_id,
            wait_for_load=new_request.wait_for_load,
            include_computed_styles=new_request.include_computed_styles,
            max_depth=new_request.max_depth
        )
        
        # Save result if requested
        saved_file_path = None
        if new_request.save_result:
            saved_file_path = await extraction_service.save_extraction_result(
                result, 
                output_format=new_request.output_format
            )
        
        return DOMExtractionResponse(
            success=result.success,
            message=f"Regenerated extraction with {result.total_elements} elements" if result.success
                   else f"Regeneration failed: {result.error_message}",
            extraction_result=result,
            saved_file_path=saved_file_path,
            session_id=session_id,
            timestamp=datetime.now(UTC)
        )
        
    except Exception as e:
        logger.error(f"DOM extraction regeneration failed: {str(e)}")
        return DOMExtractionResponse(
            success=False,
            message=f"Regeneration failed: {str(e)}",
            extraction_result=None,
            saved_file_path=None,
            session_id=session_id,
            timestamp=datetime.now(UTC)
        )


@router.get("/stats")
async def get_extraction_statistics(
    browser_manager: BrowserManager = Depends(get_browser_manager)
):
    """
    Get global DOM extraction statistics.
    
    Returns:
        Statistics about extraction storage and usage
    """
    extractions_dir = Path(settings.temp_storage_path) / "extractions"
    
    if not extractions_dir.exists():
        return {
            "total_files": 0,
            "total_size": 0,
            "disk_usage": "0 bytes",
            "oldest_file": None,
            "newest_file": None,
            "average_file_size": 0
        }
    
    files = list(extractions_dir.glob("*.json"))
    
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