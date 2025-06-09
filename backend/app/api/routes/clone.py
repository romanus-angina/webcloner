from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from typing import List, Optional
from datetime import datetime, UTC
import logging
import asyncio # <-- FIX: Added the missing import

from ...dependencies import (
    get_app_state, 
    ApplicationState,
    get_browser_manager,
    validate_session_id  # <-- FIX: Added the missing import
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
    
    progress_step = ProgressStep(
        step_name=step_name,
        status=status,
        started_at=datetime.now(UTC),
        progress_percentage=float(percentage),
        message=message
    )
    
    app_state.update_session(session_id, {
        "status": status.value,
        "progress": [progress_step.model_dump()],
        "updated_at": datetime.now(UTC)
    })

async def process_clone_request(
    session_id: str,
    request: CloneWebsiteRequest,
    app_state: ApplicationState,
):
    """Full cloning pipeline with VQA feedback loop."""
    try:
        browser_manager = get_browser_manager()
        if not browser_manager._is_initialized:
            await browser_manager.initialize()
        
        dom_extraction_service.browser_manager = browser_manager
        screenshot_service.browser_manager = browser_manager
        
        await update_progress(session_id, app_state, "DOM Analysis", "Extracting page structure and styles...", CloneStatus.ANALYZING, 10)
        dom_result = await dom_extraction_service.extract_dom_structure(url=str(request.url), session_id=session_id)
        if not dom_result.success:
            raise ProcessingError(f"DOM extraction failed: {dom_result.error_message}")

        await update_progress(session_id, app_state, "Component Detection", "Identifying UI components...", CloneStatus.ANALYZING, 30)
        component_result = ComponentDetector(dom_result).detect_components()

        await update_progress(session_id, app_state, "Initial Generation", "Creating first version of the website...", CloneStatus.GENERATING, 50)
        initial_generation = await llm_service.generate_html_from_components(
            component_result=component_result,
            dom_result=dom_result,
            original_url=str(request.url),
            quality_level=request.quality
        )
        initial_html = initial_generation["html_content"]

        await update_progress(session_id, app_state, "Visual Comparison", "Taking screenshots for visual analysis...", CloneStatus.REFINING, 70)
        
        viewport = screenshot_service.get_viewport_by_type(ViewportType.DESKTOP)
        original_shot_task = screenshot_service.capture_screenshot(url=str(request.url), viewport=viewport, session_id=session_id, full_page=False)
        generated_shot_task = screenshot_service.capture_html_content_screenshot(html_content=initial_html, viewport=viewport, session_id=session_id, full_page=False)
        
        original_shot, generated_shot = await asyncio.gather(original_shot_task, generated_shot_task)

        if not original_shot.success or not generated_shot.success:
            raise ProcessingError(f"Failed to capture screenshots for VQA. Original: {original_shot.error}, Generated: {generated_shot.error}")

        await update_progress(session_id, app_state, "QA Analysis", "AI is visually comparing the websites...", CloneStatus.REFINING, 80)
        feedback = await llm_service.analyze_visual_differences(original_shot.file_path, generated_shot.file_path)

        await update_progress(session_id, app_state, "Final Refinement", "Applying visual feedback to the code...", CloneStatus.REFINING, 90)
        refined_html = await llm_service.refine_html_with_feedback(initial_html, feedback)

        final_similarity = llm_service._calculate_similarity_score(component_result, dom_result, refined_html)
        final_result = CloneResult(
            html_content=refined_html,
            similarity_score=final_similarity,
            generation_time=0.0,
            tokens_used=initial_generation.get("tokens_used", 0)
        )
        
        await update_progress(session_id, app_state, "Completed", f"Clone refined successfully! Similarity: {final_similarity:.1f}%", CloneStatus.COMPLETED, 100)
        app_state.update_session(session_id, {"result": final_result.model_dump()})

    except Exception as e:
        error_message = f"Clone processing failed: {str(e)}"
        logger.error(error_message, exc_info=True)
        app_state.update_session(session_id, {
            "status": CloneStatus.FAILED.value,
            "error_message": error_message,
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