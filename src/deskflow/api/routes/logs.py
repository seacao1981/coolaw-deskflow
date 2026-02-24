"""Enhanced logging API routes."""

from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/logs", tags=["logs"])

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


def _get_state() -> Any:
    """Get app state at runtime."""
    from deskflow.app import get_app_state
    return get_app_state()


@router.get("/stats")
async def get_log_stats():
    """Get log storage statistics."""
    try:
        from deskflow.logging import get_log_cleaner

        cleaner = get_log_cleaner()
        if not cleaner:
            return {
                "success": False,
                "error": "Log cleaner not initialized",
            }

        stats = cleaner.get_stats()

        return {
            "success": True,
            "stats": stats,
        }

    except Exception as e:
        logger.error("get_log_stats_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flush")
async def flush_logs():
    """Flush buffered logs to file."""
    try:
        from deskflow.logging import flush_logs

        flush_logs()

        return {
            "success": True,
            "message": "Logs flushed successfully",
        }

    except Exception as e:
        logger.error("flush_logs_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def trigger_cleanup():
    """Trigger manual log cleanup."""
    try:
        from deskflow.logging import get_log_cleaner

        cleaner = get_log_cleaner()
        if not cleaner:
            return {
                "success": False,
                "error": "Log cleaner not initialized",
            }

        # Trigger immediate cleanup
        cleaner._cleanup_old_logs()
        cleaner._check_size_limit()

        stats = cleaner.get_stats()

        return {
            "success": True,
            "message": "Cleanup completed",
            "stats": stats,
        }

    except Exception as e:
        logger.error("trigger_cleanup_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_log_config():
    """Get current logging configuration."""
    try:
        from deskflow.logging import get_log_cleaner, get_session_buffer

        cleaner = get_log_cleaner()
        buffer = get_session_buffer()

        return {
            "success": True,
            "config": {
                "buffer": {
                    "enabled": buffer is not None,
                    "flush_interval": buffer._config.flush_interval if buffer else None,
                    "max_buffer_size": buffer._config.max_buffer_size if buffer else None,
                },
                "cleanup": {
                    "enabled": cleaner is not None,
                    "max_age_days": cleaner._config.max_age_days if cleaner else None,
                    "max_size_mb": cleaner._config.max_size_mb if cleaner else None,
                    "compression": cleaner._config.compression if cleaner else None,
                },
            },
        }

    except Exception as e:
        logger.error("get_log_config_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/start")
async def start_session(session_id: str):
    """Start a new log session.

    Args:
        session_id: Unique session identifier

    Returns:
        Session start result
    """
    try:
        from deskflow.logging import set_current_session

        set_current_session(session_id)

        logger.info("log_session_started", session_id=session_id)

        return {
            "success": True,
            "session_id": session_id,
            "message": f"Session '{session_id}' started",
        }

    except Exception as e:
        logger.error("start_session_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/end")
async def end_session(session_id: str):
    """End a log session and flush logs.

    Args:
        session_id: Session identifier to end

    Returns:
        Session end result
    """
    try:
        from deskflow.logging import flush_logs

        # Flush all pending logs
        flush_logs()

        logger.info("log_session_ended", session_id=session_id)

        return {
            "success": True,
            "session_id": session_id,
            "message": f"Session '{session_id}' ended and logs flushed",
        }

    except Exception as e:
        logger.error("end_session_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent")
async def get_recent_logs(
    lines: int = 50,
    level: str | None = None,
):
    """Get recent log entries.

    Args:
        lines: Number of lines to return
        level: Filter by log level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Recent log entries
    """
    try:
        from pathlib import Path

        log_dir = Path("data/logs")
        if not log_dir.exists():
            return {
                "success": True,
                "entries": [],
                "total": 0,
            }

        # Get most recent log file
        log_files = sorted(log_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)

        if not log_files:
            return {
                "success": True,
                "entries": [],
                "total": 0,
            }

        entries = []
        with open(log_files[0], encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)  # Use json.loads instead of eval
                    if level is None or entry.get("level") == level:
                        entries.append(entry)
                        if len(entries) >= lines:
                            break
                except (json.JSONDecodeError, Exception):
                    continue

        return {
            "success": True,
            "entries": entries,
            "total": len(entries),
            "source_file": log_files[0].name,
        }

    except Exception as e:
        logger.error("get_recent_logs_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stream")
async def stream_logs(
    level: str | None = None,
    lines: int = 10,
) -> StreamingResponse:
    """Stream logs in real-time using SSE (Server-Sent Events).

    Args:
        level: Filter by log level (DEBUG, INFO, WARNING, ERROR)
        lines: Initial number of historical lines to send

    Returns:
        SSE stream of log entries
    """
    async def generate() -> AsyncGenerator[str, None]:
        """Generate SSE events."""
        log_dir = Path("data/logs")

        # Send initial connection event
        yield f"event: connected\ndata: {json.dumps({'status': 'connected', 'timestamp': datetime.now().isoformat()})}\n\n"

        # Send historical logs
        if log_dir.exists():
            log_files = sorted(log_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
            if log_files:
                entries = []
                try:
                    with open(log_files[0], encoding="utf-8") as f:
                        for line in reversed(f.readlines()):
                            try:
                                entry = json.loads(line.strip())
                                if level is None or entry.get("level") == level:
                                    entries.append(entry)
                                    if len(entries) >= lines:
                                        break
                            except json.JSONDecodeError:
                                continue

                    # Send historical entries in reverse order (oldest first)
                    for entry in reversed(entries):
                        yield f"event: log\ndata: {json.dumps(entry)}\n\n"
                except Exception as e:
                    logger.error("stream_historical_failed", error=str(e))

        # Stream new logs (polling for new entries)
        last_size = 0
        if log_files:
            with contextlib.suppress(Exception):
                last_size = log_files[0].stat().st_size

        while True:
            try:
                await asyncio.sleep(1)  # Poll every second

                # Check if log file has grown
                if log_dir.exists():
                    current_files = sorted(log_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
                    if current_files:
                        current_file = current_files[0]
                        current_size = current_file.stat().st_size

                        if current_size > last_size:
                            # Read new lines
                            try:
                                with open(current_file, encoding="utf-8") as f:
                                    f.seek(last_size)
                                    new_lines = f.readlines()

                                for line in new_lines:
                                    try:
                                        entry = json.loads(line.strip())
                                        if level is None or entry.get("level") == level:
                                            yield f"event: log\ndata: {json.dumps(entry)}\n\n"
                                    except json.JSONDecodeError:
                                        continue

                                last_size = current_size
                            except Exception:
                                pass

                # Send heartbeat
                yield f"event: heartbeat\ndata: {json.dumps({'timestamp': datetime.now().isoformat()})}\n\n"

            except Exception:
                # Client disconnected
                break

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/activity/stream")
async def stream_activity(
    type: str | None = None,
    status: str | None = None,
) -> StreamingResponse:
    """Stream activity log in real-time using SSE.

    Args:
        type: Filter by activity type (llm_call, tool_execution, memory_operation, system_event, user_action)
        status: Filter by status (success, failed, pending)

    Returns:
        SSE stream of activity records
    """
    from deskflow.observability.activity_logger import (
        ActivityStatus,
        ActivityType,
        get_activity_logger,
    )

    async def generate() -> AsyncGenerator[str, None]:
        """Generate SSE activity events."""
        activity_logger = get_activity_logger()

        # Send initial connection event
        yield f"event: connected\ndata: {json.dumps({'status': 'connected', 'timestamp': datetime.now().isoformat()})}\n\n"

        # Send recent activities
        try:
            # Convert string filters to enum
            activity_type: ActivityType | None = None
            activity_status: ActivityStatus | None = None

            if type:
                with contextlib.suppress(ValueError):
                    activity_type = ActivityType(type)

            if status:
                with contextlib.suppress(ValueError):
                    activity_status = ActivityStatus(status)

            activities = activity_logger.get_recent_activities(limit=20, activity_type=activity_type, status=activity_status)

            for activity in activities:
                yield f"event: activity\ndata: {json.dumps(activity.to_dict())}\n\n"
        except Exception as e:
            logger.error("stream_activity_initial_failed", error=str(e))

        # Poll for new activities
        last_count = activity_logger.get_today_count()
        while True:
            try:
                await asyncio.sleep(2)  # Poll every 2 seconds

                current_count = activity_logger.get_today_count()
                if current_count > last_count:
                    # New activities available
                    new_activities = activity_logger.get_recent_activities(
                        limit=current_count - last_count,
                        activity_type=activity_type,
                        status=activity_status,
                    )

                    for activity in new_activities:
                        yield f"event: activity\ndata: {json.dumps(activity.to_dict())}\n\n"

                    last_count = current_count

                # Send heartbeat
                yield f"event: heartbeat\ndata: {json.dumps({'timestamp': datetime.now().isoformat(), 'count': last_count})}\n\n"

            except Exception:
                # Client disconnected
                break

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
