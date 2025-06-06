from fastapi import APIRouter, Depends, Query
from typing import Dict, Any
import psutil
import os
from datetime import datetime, UTC

from ...dependencies import get_app_state, get_settings, ApplicationState
from ...models.responses import HealthResponse
from ...config import Settings

router = APIRouter()


@router.get("/health/detailed", response_model=HealthResponse)
async def detailed_health_check(
    app_state: ApplicationState = Depends(get_app_state),
    settings: Settings = Depends(get_settings)
):
    """
    Detailed health check with system information.
    
    Returns comprehensive health information including:
    - System metrics (CPU, memory, disk)
    - Application statistics
    - Service status
    """
    uptime = app_state.get_uptime()
    
    # Get system metrics
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        system_info = {
            "cpu_percent": cpu_percent,
            "memory_total": memory.total,
            "memory_available": memory.available,
            "memory_percent": memory.percent,
            "disk_total": disk.total,
            "disk_free": disk.free,
            "disk_percent": (disk.used / disk.total) * 100
        }
    except Exception:
        system_info = {"error": "Unable to fetch system metrics"}
    
    details = {
        "system": system_info,
        "application": {
            "uptime_seconds": uptime,
            "active_sessions": len(app_state.active_sessions),
            "total_requests": app_state.request_count,
            "environment": settings.environment,
            "debug_mode": settings.debug
        },
        "services": {
            "anthropic_configured": bool(settings.anthropic_api_key),
            "redis_configured": bool(settings.redis_url),
            "temp_storage_available": os.path.exists(settings.temp_storage_path)
        }
    }
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(UTC),
        version=settings.app_version,
        uptime=uptime,
        details=details
    )


@router.get("/health/quick")
async def quick_health_check():
    """Quick health check for load balancers."""
    return {"status": "ok", "timestamp": datetime.now(UTC).isoformat()}


@router.get("/health/sessions")
async def sessions_health(
    app_state: ApplicationState = Depends(get_app_state)
):
    """Get information about active sessions."""
    sessions = app_state.active_sessions
    
    session_stats = {
        "total_active": len(sessions),
        "by_status": {},
        "oldest_session": None,
        "newest_session": None
    }
    
    if sessions:
        # Count by status
        for session_data in sessions.values():
            status = session_data.get("status", "unknown")
            session_stats["by_status"][status] = session_stats["by_status"].get(status, 0) + 1
        
        # Find oldest and newest
        sorted_sessions = sorted(
            sessions.items(), 
            key=lambda session_tuple: session_tuple[1].get("created_at", datetime.min)
        )
        
        if sorted_sessions:
            session_stats["oldest_session"] = {
                "id": sorted_sessions[0][0],
                "created_at": sorted_sessions[0][1]["created_at"].isoformat(),
                "status": sorted_sessions[0][1].get("status")
            }
            session_stats["newest_session"] = {
                "id": sorted_sessions[-1][0], 
                "created_at": sorted_sessions[-1][1]["created_at"].isoformat(),
                "status": sorted_sessions[-1][1].get("status")
            }
    
    return session_stats


@router.get("/health/storage")
async def storage_health(
    settings: Settings = Depends(get_settings)
):
    """Check storage system health."""
    storage_info = {
        "temp_path": settings.temp_storage_path,
        "max_file_size": settings.max_file_size,
        "directories": {}
    }
    
    # Check required directories
    required_dirs = ["screenshots", "generated", "assets"]
    
    for dir_name in required_dirs:
        dir_path = os.path.join(settings.temp_storage_path, dir_name)
        storage_info["directories"][dir_name] = {
            "exists": os.path.exists(dir_path),
            "writable": os.access(dir_path, os.W_OK) if os.path.exists(dir_path) else False,
            "path": dir_path
        }
        
        # Count files if directory exists
        if os.path.exists(dir_path):
            try:
                file_count = len([f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))])
                storage_info["directories"][dir_name]["file_count"] = file_count
            except Exception:
                storage_info["directories"][dir_name]["file_count"] = "error"
    
    return storage_info


@router.get("/health/config")
async def config_health(
    settings: Settings = Depends(get_settings)
):
    """Get configuration status (sanitized for security)."""
    config_status = {
        "environment": settings.environment,
        "debug": settings.debug,
        "services_configured": {
            "anthropic": bool(settings.anthropic_api_key),
            "redis": bool(settings.redis_url)
        },
        "rate_limiting": {
            "enabled": True,
            "requests_per_window": settings.rate_limit_requests,
            "window_seconds": settings.rate_limit_window
        },
        "timeouts": {
            "request_timeout": settings.request_timeout,
            "max_retries": settings.max_retries
        }
    }
    
    return config_status