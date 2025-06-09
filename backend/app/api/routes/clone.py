from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List
from datetime import datetime, UTC
import uuid
import time

from ...dependencies import (
    get_app_state, 
    get_settings, 
    get_logger, 
    get_request_id,
    validate_session_id,
    check_rate_limit,
    ApplicationState
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
from ...core.exceptions import ValidationError, SessionError
from ...config import Settings
import logging
from ...services.llm_service import llm_service
from ...services.component_detector import ComponentDetector

router = APIRouter()


@router.post("/clone", response_model=CloneResponse)
async def clone_website(
    request: CloneWebsiteRequest,
    background_tasks: BackgroundTasks,
    app_state: ApplicationState = Depends(get_app_state),
    settings: Settings = Depends(get_settings),
    logger: logging.Logger = Depends(get_logger),
    request_id: str = Depends(get_request_id),
    _: None = Depends(check_rate_limit)
):
    """
    Start cloning a website.
    
    This endpoint initiates the website cloning process and returns immediately
    with a session ID. The actual cloning happens in the background.
    
    Args:
        request: Website cloning request parameters
        background_tasks: FastAPI background tasks
        
    Returns:
        Initial clone response with session ID and status
    """
    logger.info(f"Starting clone request for URL: {request.url}")
    
    # Create new session
    session_id = app_state.create_session()
    
    # Create initial response
    response = CloneResponse(
        session_id=session_id,
        status=CloneStatus.PENDING,
        progress=[
            ProgressStep(
                step_name="Initialization",
                status=CloneStatus.PENDING,
                started_at=datetime.now(UTC),
                progress_percentage=0.0,
                message="Request received, preparing to clone website"
            )
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    
    # Update session with initial data
    app_state.update_session(session_id, {
        "status": CloneStatus.PENDING.value,
        "request": request.model_dump(),
        "request_id": request_id,
        "progress": response.progress
    })
    
    # Add background task to process the cloning
    background_tasks.add_task(
        process_clone_request,
        session_id=session_id,
        request=request,
        app_state=app_state,
        settings=settings,
        logger=logger
    )
    
    logger.info(f"Clone request initiated with session ID: {session_id}")
    
    return response


@router.get("/clone/{session_id}", response_model=CloneResponse)
async def get_clone_status(
    session_id: str = Depends(validate_session_id),
    app_state: ApplicationState = Depends(get_app_state)
):
    """
    Get the status of a cloning operation.
    
    Args:
        session_id: Session ID from the original clone request
        
    Returns:
        Current status and progress of the cloning operation
    """
    session_data = app_state.get_session(session_id)
    
    if not session_data:
        raise SessionError(f"Session {session_id} not found", session_id)
    
    # Convert session data to response model
    response = CloneResponse(
        session_id=session_id,
        status=CloneStatus(session_data.get("status", "pending")),
        progress=session_data.get("progress", []),
        result=session_data.get("result"),
        created_at=session_data.get("created_at"),
        updated_at=session_data.get("updated_at", datetime.now(UTC)),
        estimated_completion=session_data.get("estimated_completion"),
        error_message=session_data.get("error_message"),
        component_analysis=session_data.get("component_analysis")
    )
    
    return response


@router.post("/clone/{session_id}/refine", response_model=RefinementResponse)
async def refine_clone(
    refinement_request: RefinementRequest,
    background_tasks: BackgroundTasks,
    session_id: str = Depends(validate_session_id),
    app_state: ApplicationState = Depends(get_app_state),
    logger: logging.Logger = Depends(get_logger),
    _: None = Depends(check_rate_limit)
):
    """
    Refine a completed clone based on user feedback.
    
    Args:
        refinement_request: Refinement parameters and feedback
        session_id: Session ID from the original clone request
        
    Returns:
        Refinement operation status
    """
    session_data = app_state.get_session(session_id)
    
    if not session_data:
        raise SessionError(f"Session {session_id} not found", session_id)
    
    # Check if the clone is completed
    if session_data.get("status") != CloneStatus.COMPLETED.value:
        raise ValidationError("Can only refine completed clones")
    
    logger.info(f"Starting refinement for session {session_id}")
    
    # Create refinement response
    response = RefinementResponse(
        session_id=session_id,
        status=CloneStatus.PENDING,
        iterations=session_data.get("refinement_iterations", 0) + 1,
        improvements_made=[],
        feedback_processed=refinement_request.feedback
    )
    
    # Update session status
    app_state.update_session(session_id, {
        "status": CloneStatus.REFINING.value,
        "refinement_in_progress": True,
        "latest_feedback": refinement_request.feedback
    })
    
    # Add background task for refinement
    background_tasks.add_task(
        process_refinement_request,
        session_id=session_id,
        refinement_request=refinement_request,
        app_state=app_state,
        logger=logger
    )
    
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


async def process_clone_request(
    session_id: str,
    request: CloneWebsiteRequest,
    app_state: ApplicationState,
    settings: Settings,
    logger: logging.Logger
):
    """
    Background task to process the actual cloning request.
    Enhanced with component detection and LLM generation.
    """
    logger.info(f"Processing clone request for session {session_id}")
    
    try:
        # Update status to analyzing
        app_state.update_session(session_id, {
            "status": CloneStatus.ANALYZING.value,
            "updated_at": datetime.now(UTC)
        })
        
        # Step 1: DOM Extraction
        from ...dependencies import get_browser_manager, get_dom_extraction_service
        browser_manager = get_browser_manager()
        dom_service = get_dom_extraction_service()
        
        if not browser_manager._is_initialized:
            await browser_manager.initialize()
        
        dom_service.browser_manager = browser_manager
        
        logger.info(f"Extracting DOM structure for {request.url}")
        dom_result = await dom_service.extract_dom_structure(
            url=str(request.url),
            session_id=session_id,
            wait_for_load=True,
            include_computed_styles=request.include_styling,
            max_depth=10
        )
        
        if not dom_result.success:
            raise ProcessingError(f"DOM extraction failed: {dom_result.error_message}")
        
        # Step 2: Component Detection
        app_state.update_session(session_id, {
            "status": CloneStatus.ANALYZING.value,
            "updated_at": datetime.now(UTC),
            "progress": [
                ProgressStep(
                    step_name="Component Analysis",
                    status=CloneStatus.ANALYZING,
                    started_at=datetime.now(UTC),
                    progress_percentage=30.0,
                    message="Detecting UI components..."
                )
            ]
        })
        
        logger.info(f"Detecting components for session {session_id}")
        component_detector = ComponentDetector(dom_result)
        component_result = component_detector.detect_components()
        
        logger.info(f"Detected {component_result.total_components} components in {component_result.detection_time_seconds:.2f}s")
        
        # Step 3: LLM HTML Generation
        app_state.update_session(session_id, {
            "status": CloneStatus.GENERATING.value,
            "updated_at": datetime.now(UTC),
            "progress": [
                ProgressStep(
                    step_name="HTML Generation",
                    status=CloneStatus.GENERATING,
                    started_at=datetime.now(UTC),
                    progress_percentage=60.0,
                    message=f"Generating HTML from {component_result.total_components} detected components..."
                )
            ]
        })
        
        logger.info(f"Generating HTML for session {session_id}")
        generation_start = time.time()
        
        llm_result = await llm_service.generate_html_from_components(
            component_result=component_result,
            dom_result=dom_result,
            original_url=str(request.url),
            quality_level=request.quality
        )
        
        generation_time = time.time() - generation_start
        llm_result["generation_time"] = generation_time
        
        # Step 4: Complete
        app_state.update_session(session_id, {
            "status": CloneStatus.COMPLETED.value,
            "updated_at": datetime.now(UTC),
            "result": CloneResult(
                html_content=llm_result["html_content"],
                css_content=llm_result.get("css_content"),
                assets=[],  # TODO: Implement asset handling
                similarity_score=llm_result["similarity_score"],
                generation_time=llm_result["generation_time"],
                tokens_used=llm_result["tokens_used"]
            ).__dict__,
            "component_analysis": {
                "total_components": component_result.total_components,
                "detection_time": component_result.detection_time_seconds,
                "components_replicated": llm_result["components_replicated"],
                "components_detected": [
                    {
                        "type": comp.component_type.value,
                        "label": comp.label,
                        "metadata": comp.metadata
                    } for comp in component_result.components
                ]
            },
            "progress": [
                ProgressStep(
                    step_name="Completed",
                    status=CloneStatus.COMPLETED,
                    started_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                    progress_percentage=100.0,
                    message=f"Website cloned successfully! Similarity: {llm_result['similarity_score']:.1f}%"
                )
            ]
        })
        
        logger.info(f"Clone request completed for session {session_id}: {llm_result['similarity_score']:.1f}% similarity")
        
    except Exception as e:
        logger.error(f"Error processing clone request {session_id}: {str(e)}")
        app_state.update_session(session_id, {
            "status": CloneStatus.FAILED.value,
            "updated_at": datetime.now(UTC),
            "error_message": str(e)
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