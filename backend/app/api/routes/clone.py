from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from typing import List, Optional
from datetime import datetime, UTC
import logging
import asyncio 

from ...dependencies import (
    get_app_state, 
    ApplicationState,
    get_browser_manager,
    validate_session_id  
)
from ...models.requests import CloneWebsiteRequest, RefinementRequest
from ...models.responses import (
    CloneResponse, 
    CloneStatus, 
    ProgressStep,
    RefinementResponse,
    SessionListResponse,
    CloneResult
)
from ...core.exceptions import ProcessingError, SessionError, ValidationError
from ...config import Settings
from ...services.dom_extraction_service import dom_extraction_service
from ...services.component_detector import ComponentDetector
from ...services.llm_service import llm_service
from ...services.screenshot_service import screenshot_service, ViewportType
from ...utils.logger import get_logger
from ...services.asset_downloader_service import AssetDownloaderService
from ...services.html_rewriter_service import HTMLRewriterService

router = APIRouter()
logger = get_logger(__name__)

@router.post("/clone", response_model=CloneResponse)
async def clone_website(
    request: CloneWebsiteRequest,
    background_tasks: BackgroundTasks,
    app_state: ApplicationState = Depends(get_app_state),
):
    """Initiates the website cloning process."""
    session_id = app_state.create_session()
    
    initial_progress = ProgressStep(
        step_name="Initialization",
        status=CloneStatus.PENDING,
        started_at=datetime.now(UTC),
        message="Request received, preparing to clone."
    )
    
    response = CloneResponse(
        session_id=session_id,
        status=CloneStatus.PENDING,
        progress=[initial_progress],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    
    app_state.update_session(session_id, response.model_dump())
    
    background_tasks.add_task(
        process_clone_request,
        session_id=session_id,
        request=request,
        app_state=app_state
    )
    
    return response

@router.get("/clone/{session_id}", response_model=CloneResponse)
async def get_clone_status(
    session_id: str = Depends(validate_session_id),
    app_state: ApplicationState = Depends(get_app_state)
):
    session_data = app_state.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return CloneResponse(**session_data)

@router.post("/clone/{session_id}/refine", response_model=RefinementResponse)
async def refine_clone(
    refinement_request: RefinementRequest,
    background_tasks: BackgroundTasks,
    session_id: str = Depends(validate_session_id),
    app_state: ApplicationState = Depends(get_app_state)
):
    session_data = app_state.get_session(session_id)
    if not session_data:
        raise SessionError(f"Session {session_id} not found", session_id)
    if session_data.get("status") != CloneStatus.COMPLETED.value:
        raise ValidationError("Can only refine completed clones")
    
    logger.info(f"Starting refinement for session {session_id}")
    
    response = RefinementResponse(
        session_id=session_id,
        status=CloneStatus.REFINING,
        iterations=session_data.get("refinement_iterations", 0) + 1,
        improvements_made=[],
        feedback_processed=refinement_request.feedback
    )
    
    app_state.update_session(session_id, {"status": CloneStatus.REFINING.value})
    
    # This part would need a background task for refinement
    # For now, just returning a mock response
    return response



@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    page: int = 1,
    page_size: int = 10,
    status: str = None,
    app_state: ApplicationState = Depends(get_app_state)
):
    """
    List all cloning sessions.
    
    Args:
        page: Page number (1-based)
        page_size: Number of items per page
        status: Filter by status (optional)
        
    Returns:
        Paginated list of sessions
    """
    # Validate parameters
    if page < 1:
        raise ValidationError("Page must be >= 1", "page")
    if page_size < 1 or page_size > 100:
        raise ValidationError("Page size must be between 1 and 100", "page_size")
    
    sessions = app_state.active_sessions
    
    # Filter by status if provided
    if status:
        sessions = {
            sid: data for sid, data in sessions.items()
            if data.get("status") == status
        }
    
    # Convert to response objects
    session_responses = []
    for session_id, session_data in sessions.items():
        response = CloneResponse(
            session_id=session_id,
            status=CloneStatus(session_data.get("status", "pending")),
            progress=session_data.get("progress", []),
            result=session_data.get("result"),
            created_at=session_data.get("created_at"),
            updated_at=session_data.get("updated_at", datetime.now(UTC)),
            estimated_completion=session_data.get("estimated_completion"),
            error_message=session_data.get("error_message")
        )
        session_responses.append(response)
    
    # Sort by creation time (newest first)
    session_responses.sort(key=lambda x: x.created_at, reverse=True)
    
    # Paginate
    total_count = len(session_responses)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_sessions = session_responses[start_idx:end_idx]
    
    return SessionListResponse(
        sessions=paginated_sessions,
        total_count=total_count,
        page=page,
        page_size=page_size
    )


@router.delete("/clone/{session_id}")
async def delete_session(
    session_id: str = Depends(validate_session_id),
    app_state: ApplicationState = Depends(get_app_state),
    logger: logging.Logger = Depends(get_logger)
):
    """
    Delete a cloning session and its associated data.
    
    Args:
        session_id: Session ID to delete
        
    Returns:
        Confirmation message
    """
    session_data = app_state.active_sessions.pop(session_id, None)
    
    if not session_data:
        raise SessionError(f"Session {session_id} not found", session_id)
    
    logger.info(f"Deleted session {session_id}")
    
    # TODO: In the future, also clean up associated files
    
    return {
        "message": f"Session {session_id} deleted successfully",
        "deleted_at": datetime.now(UTC).isoformat()
    }


async def update_progress(session_id: str, app_state: ApplicationState, step_name: str, message: str, status: CloneStatus, percentage: int):
    """Helper to update and log progress."""
    logger.info(f"Session {session_id}: {step_name} - {message}")
    
    # Ensure progress is always a list
    session_data = app_state.get_session(session_id)
    current_progress = session_data.get("progress", [])
    if not isinstance(current_progress, list):
        current_progress = []

    progress_step = ProgressStep(
        step_name=step_name,
        status=status,
        started_at=datetime.now(UTC),
        progress_percentage=float(percentage),
        message=message
    )
    
    # Append new progress step
    current_progress.append(progress_step.model_dump())
    
    app_state.update_session(session_id, {
        "status": status.value,
        "progress": current_progress,
        "updated_at": datetime.now(UTC)
    })

# Enhanced process_clone_request function for backend/app/api/routes/clone.py

async def process_clone_request(
    session_id: str,
    request: CloneWebsiteRequest,
    app_state: ApplicationState,
):
    """
    Enhanced cloning pipeline with better asset handling and modern web support.
    """
    try:
        browser_manager = get_browser_manager()
        if not browser_manager._is_initialized:
            await browser_manager.initialize()
        
        dom_extraction_service.browser_manager = browser_manager
        screenshot_service.browser_manager = browser_manager
        
        # 1. Enhanced Blueprint Extraction with Asset Detection
        await update_progress(session_id, app_state, "Blueprint Extraction", 
                            "Analyzing page structure, detecting modern web patterns...", 
                            CloneStatus.ANALYZING, 10)
        
        dom_result = await dom_extraction_service.extract_dom_structure(
            url=str(request.url), 
            session_id=session_id,
            wait_for_load=True,
            include_computed_styles=True,
            max_depth=6
        )
        
        if not dom_result.success:
            raise ProcessingError(f"Blueprint extraction failed: {dom_result.error_message}")

        blueprint = dom_result.blueprint
        if not blueprint:
            raise ProcessingError("Extraction returned an empty blueprint.")

        logger.info(f"Extracted {len(dom_result.assets)} assets for processing")
        logger.info(f"Asset types: {getattr(dom_result, 'asset_types', [])}")
        
        # Log asset breakdown
        asset_breakdown = {}
        for asset in dom_result.assets:
            asset_type = getattr(asset, 'asset_type', 'unknown')
            asset_breakdown[asset_type] = asset_breakdown.get(asset_type, 0) + 1
        logger.info(f"Asset breakdown: {asset_breakdown}")

        # 2. Enhanced Asset Downloading with Better Error Handling
        await update_progress(session_id, app_state, "Asset Processing", 
                            f"Processing {len(dom_result.assets)} assets (images, SVGs, icons)...", 
                            CloneStatus.SCRAPING, 25)
        
        
        asset_downloader = AssetDownloaderService(session_id)
        download_results = await asset_downloader.download_assets(dom_result.assets)
        await asset_downloader.close()
        
        # Get download statistics
        download_stats = asset_downloader.get_stats()
        logger.info(f"Asset download stats: {download_stats}")
        
        # Create comprehensive asset map
        asset_map = {}
        successful_assets = []
        failed_assets = []
        
        for item in download_results:
            if item.get('success'):
                successful_assets.append(item)
                original_url = item.get('original_url')
                local_path = item.get('local_path')
                
                if original_url and local_path:
                    asset_map[original_url] = local_path
                
                # Handle inline assets with special keys
                if item.get('is_inline') and item.get('content'):
                    inline_key = f"inline-{item.get('asset_type', 'asset')}"
                    asset_map[inline_key] = local_path
                
                # Handle data URLs
                if item.get('is_data_url'):
                    asset_map[original_url] = local_path
                    
            else:
                failed_assets.append(item)

        logger.info(f"Asset processing results: {len(successful_assets)} successful, {len(failed_assets)} failed")
        logger.info(f"Asset map keys: {list(asset_map.keys())[:10]}...")  # Log first 10 keys

        # 3. Enhanced HTML Generation with Asset Context
        await update_progress(session_id, app_state, "HTML Assembly", 
                            "AI is generating HTML with enhanced asset integration...", 
                            CloneStatus.GENERATING, 40)
        
        # Provide additional context to LLM about assets
        asset_context = {
            'total_assets': len(dom_result.assets),
            'successful_downloads': len(successful_assets),
            'asset_types': list(asset_breakdown.keys()),
            'has_logos': any('logo' in str(asset.get('alt_text', '')).lower() 
                           for asset in successful_assets),
            'has_icons': any(asset.get('asset_type') == 'svg' 
                           for asset in successful_assets),
            'has_backgrounds': any('background' in asset.get('asset_type', '') 
                                 for asset in successful_assets)
        }
        
        initial_generation = await llm_service.generate_html_from_components(
            component_result=blueprint,
            dom_result=dom_result,
            original_url=str(request.url),
            quality_level=request.quality,
            asset_context=asset_context  # Pass asset context
        )
        initial_html = initial_generation["html_content"]

        # 4. Enhanced Asset Integration with Modern Patterns
        await update_progress(session_id, app_state, "Asset Integration", 
                            "Integrating assets with modern web patterns...", 
                            CloneStatus.GENERATING, 55)
        
        # Use enhanced HTML rewriter
        from ..services.enhanced_html_rewriter_service import EnhancedHTMLRewriterService
        rewriter = EnhancedHTMLRewriterService()
        
        # Multi-pass asset integration
        logger.info("Starting multi-pass asset integration...")
        
        # Pass 1: Basic asset path rewriting
        html_with_assets = rewriter.rewrite_asset_paths(initial_html, asset_map)
        
        # Pass 2: Enhanced asset integration
        html_with_enhanced_assets = rewriter.enhance_asset_integration(html_with_assets, successful_assets)
        
        # Pass 3: Inject missing critical assets
        if failed_assets:
            logger.info(f"Injecting fallbacks for {len(failed_assets)} failed assets")
            html_with_enhanced_assets = rewriter.inject_missing_assets(
                html_with_enhanced_assets, 
                successful_assets
            )
        
        # Get rewrite statistics
        rewrite_stats = rewriter.get_rewrite_stats()
        logger.info(f"Asset rewrite stats: {rewrite_stats}")

        # 5. Visual QA - Enhanced Screenshot Comparison
        await update_progress(session_id, app_state, "Visual Comparison", 
                            "Capturing high-quality screenshots for AI analysis...", 
                            CloneStatus.REFINING, 60)
        
        viewport = screenshot_service.get_viewport_by_type(ViewportType.DESKTOP)
        
        # Capture screenshots with better timing
        original_shot_task = screenshot_service.capture_screenshot(
            url=str(request.url), 
            viewport=viewport, 
            session_id=session_id, 
            full_page=True,
            wait_for_load=True
        )
        
        generated_shot_task = screenshot_service.capture_html_content_screenshot(
            html_content=html_with_enhanced_assets, 
            viewport=viewport, 
            session_id=session_id, 
            full_page=True,
            wait_for_load=True
        )
        
        original_shot, generated_shot = await asyncio.gather(original_shot_task, generated_shot_task)

        if not original_shot.success or not generated_shot.success:
            raise ProcessingError(f"Failed to capture screenshots for VQA. Original: {original_shot.error}, Generated: {generated_shot.error}")

        # 6. Enhanced Visual QA with Asset-Specific Feedback
        await update_progress(session_id, app_state, "AI Quality Analysis", 
                            "AI analyzing visual differences and asset placement...", 
                            CloneStatus.REFINING, 75)
        
        feedback = await llm_service.analyze_visual_differences(
            original_shot.file_path, 
            generated_shot.file_path,
            asset_context=asset_context  # Provide asset context for better analysis
        )

        # 7. Asset-Aware Refinement
        await update_progress(session_id, app_state, "Final Refinement", 
                            "Applying visual feedback with focus on asset integration...", 
                            CloneStatus.REFINING, 90)
        
        refined_html = await llm_service.refine_html_with_feedback(
            html_with_enhanced_assets, 
            feedback,
            asset_map=asset_map,  # Provide asset map for better refinement
            asset_context=asset_context
        )

        # 8. Final Asset Path Verification and Optimization
        await update_progress(session_id, app_state, "Finalizing Assets", 
                            "Final verification and optimization of asset integration...", 
                            CloneStatus.COMPLETED, 95)
        
        # Final pass to ensure all assets are properly integrated
        final_html_with_verified_assets = rewriter.rewrite_asset_paths(refined_html, asset_map)
        
        # Add final optimizations
        final_html_with_verified_assets = rewriter.enhance_asset_integration(
            final_html_with_verified_assets, 
            successful_assets
        )

        # 9. Enhanced Completion with Detailed Asset Report
        final_similarity = llm_service._calculate_similarity_score(
            blueprint, 
            dom_result, 
            final_html_with_verified_assets
        )
        
        # Create comprehensive asset summary
        asset_summary = {
            "extraction": {
                "total_found": len(dom_result.assets),
                "types_found": list(asset_breakdown.keys()),
                "extraction_metadata": {
                    "has_react": getattr(dom_result, 'has_react', False),
                    "has_vue": getattr(dom_result, 'has_vue', False),
                    "has_angular": getattr(dom_result, 'has_angular', False),
                    "extraction_limited": getattr(dom_result, 'extraction_limited', False)
                }
            },
            "download": download_stats,
            "integration": rewrite_stats,
            "final_status": {
                "successfully_integrated": len(successful_assets),
                "failed_downloads": len(failed_assets),
                "integration_rate": len(successful_assets) / max(len(dom_result.assets), 1) * 100,
                "asset_map_size": len(asset_map)
            }
        }
        
        # Enhanced completion metrics
        completion_metrics = {
            "assets_processed": len(dom_result.assets),
            "assets_integrated": len(successful_assets),
            "asset_types": list(asset_breakdown.keys()),
            "integration_techniques": [
                "enhanced_extraction",
                "multi_pass_rewriting", 
                "modern_web_patterns",
                "responsive_optimization"
            ]
        }
        
        final_result = CloneResult(
            html_content=final_html_with_verified_assets,
            similarity_score=final_similarity,
            generation_time=time.time() - start_time,
            tokens_used=initial_generation.get("tokens_used", 0),
            assets=list(asset_map.keys()),
            # Add enhanced metadata
            asset_summary=asset_summary,
            completion_metrics=completion_metrics
        )
        
        completion_message = (f"Clone completed! Similarity: {final_similarity:.1f}%, "
                            f"Assets: {len(successful_assets)}/{len(dom_result.assets)} integrated "
                            f"({asset_summary['final_status']['integration_rate']:.1f}%)")
        
        await update_progress(session_id, app_state, "Completed", completion_message, CloneStatus.COMPLETED, 100)
        
        # Update session with comprehensive asset information
        session_update = {
            "result": final_result.model_dump(),
            "asset_summary": asset_summary,
            "extraction_metadata": {
                "modern_web_features": {
                    "react_detected": getattr(dom_result, 'has_react', False),
                    "vue_detected": getattr(dom_result, 'has_vue', False),
                    "angular_detected": getattr(dom_result, 'has_angular', False)
                },
                "asset_extraction": {
                    "total_extracted": len(dom_result.assets),
                    "types_detected": getattr(dom_result, 'asset_types', []),
                    "extraction_limited": getattr(dom_result, 'extraction_limited', False)
                }
            }
        }
        app_state.update_session(session_id, session_update)

        logger.info(f"Enhanced clone completed successfully!")
        logger.info(f"Final stats: {completion_metrics}")
        logger.info(f"Asset integration: {asset_summary['final_status']}")

    except Exception as e:
        error_message = f"Enhanced clone processing failed: {str(e)}"
        logger.error(error_message, exc_info=True)
        
        # Provide detailed error context
        error_context = {
            "stage": "unknown",
            "assets_found": 0,
            "assets_processed": 0,
            "error_type": type(e).__name__
        }
        
        # Try to determine what stage failed
        if "blueprint extraction" in str(e).lower():
            error_context["stage"] = "blueprint_extraction"
        elif "asset" in str(e).lower():
            error_context["stage"] = "asset_processing"
        elif "html" in str(e).lower():
            error_context["stage"] = "html_generation"
        elif "screenshot" in str(e).lower():
            error_context["stage"] = "visual_analysis"
        
        app_state.update_session(session_id, {
            "status": CloneStatus.FAILED.value,
            "error_message": error_message,
            "error_context": error_context,
            "updated_at": datetime.now(UTC)
        })


async def process_refinement_request(
    session_id: str,
    refinement_request: RefinementRequest,
    app_state: ApplicationState,
    logger: logging.Logger
):
    """
    Background task to process refinement requests.
    This is a placeholder implementation.
    """
    logger.info(f"Processing refinement for session {session_id}")
    
    try:
        # Simulate refinement processing
        import asyncio
        await asyncio.sleep(1)
        
        # Update session with refinement results
        app_state.update_session(session_id, {
            "status": CloneStatus.COMPLETED.value,
            "updated_at": datetime.now(UTC),
            "refinement_in_progress": False,
            "refinement_iterations": app_state.active_sessions[session_id].get("refinement_iterations", 0) + 1
        })
        
        logger.info(f"Refinement completed for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error processing refinement {session_id}: {str(e)}")
        app_state.update_session(session_id, {
            "status": CloneStatus.FAILED.value,
            "updated_at": datetime.now(UTC),
            "error_message": str(e),
            "refinement_in_progress": False
        })