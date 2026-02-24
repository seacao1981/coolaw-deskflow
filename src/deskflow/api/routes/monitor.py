"""System monitoring API routes."""

from __future__ import annotations

import asyncio
import platform
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from deskflow.config import AppConfig, load_config
from deskflow.observability.activity_logger import get_activity_logger, ActivityType, ActivityStatus
from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/monitor", tags=["monitor"])

# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections for activity push notifications."""

    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and store a new WebSocket connection."""
        await websocket.accept()
        self._connections.append(websocket)
        logger.info("websocket_connected", total=len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info("websocket_disconnected", total=len(self._connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast a message to all connected clients."""
        disconnected = []
        for connection in self._connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

# Global connection manager instance
_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    """Get or create global connection manager."""
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager


# Start time for uptime calculation
_start_time = time.time()


def _get_state() -> object:
    """Get app state at runtime."""
    from deskflow.app import get_app_state
    return get_app_state()


@router.get("/status")
async def get_system_status():
    """Get real-time system status."""
    # CPU usage
    cpu_percent = psutil.cpu_percent(interval=0.5)

    # Memory usage
    memory = psutil.virtual_memory()

    # Disk usage
    disk = psutil.disk_usage("/")

    # Get project data directory
    try:
        state = _get_state()
        config: AppConfig = state.config
        data_dir = config.get_data_dir()
        data_path = str(data_dir)
    except Exception:
        data_path = "data"

    try:
        data_disk = psutil.disk_usage(data_path)
    except Exception:
        data_disk = disk

    # Uptime
    uptime_seconds = time.time() - _start_time

    return {
        "cpu": {
            "percent": cpu_percent,
            "cores": psutil.cpu_count(logical=True),
        },
        "memory": {
            "used_mb": round(memory.used / 1024 / 1024, 2),
            "total_mb": round(memory.total / 1024 / 1024, 2),
            "percent": memory.percent,
        },
        "disk": {
            "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
            "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
            "percent": disk.percent,
        },
        "data_disk": {
            "used_gb": round(data_disk.used / 1024 / 1024 / 1024, 2),
            "total_gb": round(data_disk.total / 1024 / 1024 / 1024, 2),
            "percent": data_disk.percent,
        },
        "uptime_seconds": round(uptime_seconds, 2),
        "platform": platform.system(),
    }


@router.get("/llm-stats")
async def get_llm_stats():
    """Get LLM usage statistics."""
    state = _get_state()

    # Get token usage from LLM client
    llm_provider = "none"
    llm_model = "none"
    total_tokens = 0
    today_tokens = 0
    total_cost_usd = 0.0
    today_cost_usd = 0.0
    request_count = 0
    today_request_count = 0

    if state.llm_client:
        llm_provider = state.llm_client.provider_name
        llm_model = state.llm_client.model_name
        total_tokens = state.llm_client.total_tokens
        today_tokens = state.llm_client.today_tokens
        request_count = state.llm_client.request_count

    # Get detailed stats from token tracker
    try:
        from deskflow.core.token_tracking import get_token_stats
        token_stats = get_token_stats()
        total_tokens = token_stats.get("total_tokens", total_tokens)
        today_tokens = token_stats.get("today_tokens", today_tokens)
        total_cost_usd = token_stats.get("total_cost_usd", 0.0)
        today_cost_usd = token_stats.get("today_cost_usd", 0.0)
        request_count = token_stats.get("request_count", request_count)
        today_request_count = token_stats.get("today_request_count", 0)
    except Exception as e:
        logger.warning("token_stats_load_failed", error=str(e))

    # Try to get memory/usage stats
    memory_count = 0
    if state.memory:
        try:
            memory_count = await state.memory.count()
        except Exception:
            pass

    # Tool stats
    active_tools = state.tools.count if state.tools else 0

    return {
        "provider": llm_provider,
        "model": llm_model,
        "memory_count": memory_count,
        "active_tools": active_tools,
        "total_tokens": total_tokens,
        "today_tokens": today_tokens,
        "total_cost_usd": round(total_cost_usd, 4),
        "today_cost_usd": round(today_cost_usd, 4),
        "request_count": request_count,
        "today_request_count": today_request_count,
    }


@router.get("/activity")
async def get_recent_activity(
    limit: int = 20,
    type: str | None = None,
    status: str | None = None,
):
    """Get recent system activity log.

    Args:
        limit: Maximum number of activities to return.
        type: Filter by activity type (llm_call, tool_execution, memory_operation, system_event, user_action).
        status: Filter by status (success, failed, pending).

    Returns:
        List of recent activities with total count.
    """
    activity_logger = get_activity_logger()

    # Convert string filters to enum if provided
    activity_type: ActivityType | None = None
    activity_status: ActivityStatus | None = None

    if type:
        try:
            activity_type = ActivityType(type)
        except ValueError:
            pass

    if status:
        try:
            activity_status = ActivityStatus(status)
        except ValueError:
            pass

    activities = activity_logger.get_recent_activities(
        limit=limit,
        activity_type=activity_type,
        status=activity_status,
    )

    return {
        "activities": [a.to_dict() for a in activities],
        "total": len(activities),
        "statistics": activity_logger.get_statistics(),
    }


@router.get("/token-stats")
async def get_token_statistics(days: int = 7):
    """Get detailed token usage statistics.

    Args:
        days: Number of days of history to return (default 7).

    Returns:
        Token statistics including total, today, and daily breakdown.
    """
    try:
        from deskflow.core.token_tracking import get_tracker

        tracker = get_tracker()
        stats = tracker.get_stats()
        daily_stats = tracker.get_daily_stats(days)

        return {
            "success": True,
            "stats": stats,
            "daily_stats": daily_stats,
        }

    except Exception as e:
        logger.error("get_token_statistics_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/activity")
async def websocket_activity(websocket: WebSocket):
    """WebSocket endpoint for real-time activity push notifications.

    Clients connect to receive activity updates as they happen.
    """
    manager = get_connection_manager()
    await manager.connect(websocket)

    # Send initial activity count
    activity_logger = get_activity_logger()
    await websocket.send_json({
        "type": "init",
        "count": activity_logger.get_today_count(),
    })

    try:
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client (ping/pong or close)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # Handle client messages if needed
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send periodic ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping", "timestamp": datetime.now().isoformat()})
                except Exception:
                    break
            except WebSocketDisconnect:
                break
            except Exception:
                break
    finally:
        manager.disconnect(websocket)


def notify_activity_created(record: Any) -> None:
    """Notify WebSocket clients when a new activity is created.

    This function is called by the activity logger when a new record is added.
    """
    import asyncio

    manager = get_connection_manager()
    if not manager._connections:
        return

    # Create broadcast task
    async def broadcast():
        await manager.broadcast({
            "type": "new_activity",
            "activity": record.to_dict() if hasattr(record, 'to_dict') else record,
            "timestamp": datetime.now().isoformat(),
        })

    # Schedule broadcast (don't block)
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(broadcast())
    except RuntimeError:
        # No event loop running, ignore
        pass
