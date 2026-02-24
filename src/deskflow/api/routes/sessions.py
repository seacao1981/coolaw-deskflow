"""Session management API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _get_state() -> Any:
    """Get app state at runtime."""
    from deskflow.app import get_app_state
    return get_app_state()


@router.post("/create")
async def create_session(request: dict):
    """Create a new session.

    Request body:
    - user_id: User identifier
    - channel_id: Channel identifier (e.g., 'feishu', 'wework')
    - ttl_seconds: Optional session TTL in seconds (default: 3600)
    - metadata: Optional session metadata

    Returns:
    - session_id: Created session ID
    """
    try:
        from deskflow.channels.session import get_session_manager

        user_id = request.get("user_id")
        channel_id = request.get("channel_id")
        ttl_seconds = request.get("ttl_seconds")
        metadata = request.get("metadata")

        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        if not channel_id:
            raise HTTPException(status_code=400, detail="channel_id is required")

        manager = get_session_manager()
        session_id = await manager.create_session(
            user_id=user_id,
            channel_id=channel_id,
            ttl_seconds=ttl_seconds,
            metadata=metadata,
        )

        return {
            "success": True,
            "session_id": session_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_session_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get session by ID.

    Args:
        session_id: Session identifier

    Returns:
    - Session data including context and metadata
    """
    try:
        from deskflow.channels.session import get_session_manager

        manager = get_session_manager()
        session = await manager.get_session(session_id)

        if session is None:
            raise HTTPException(status_code=404, detail="Session not found or expired")

        return {
            "success": True,
            "session": session.to_dict(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_session_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete a session.

    Args:
        session_id: Session identifier

    Returns:
    - Deletion result
    """
    try:
        from deskflow.channels.session import get_session_manager

        manager = get_session_manager()
        deleted = await manager.delete_session(session_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "success": True,
            "message": f"Session '{session_id}' deleted",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_session_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/context")
async def update_context(session_id: str, request: dict):
    """Add a message to session context.

    Args:
        session_id: Session identifier

    Request body:
    - message: Message content
    - role: Message role ('user' or 'assistant', default: 'user')

    Returns:
    - Update result
    """
    try:
        from deskflow.channels.session import get_session_manager

        message = request.get("message")
        role = request.get("role", "user")

        if not message:
            raise HTTPException(status_code=400, detail="message is required")

        manager = get_session_manager()
        success = await manager.update_context(session_id, message, role)

        if not success:
            raise HTTPException(status_code=404, detail="Session not found or expired")

        return {
            "success": True,
            "message": "Context updated",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_context_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/list")
async def list_user_sessions(user_id: str, channel_id: str | None = None):
    """Get all sessions for a user.

    Args:
        user_id: User identifier
        channel_id: Optional channel filter

    Returns:
    - List of user sessions
    """
    try:
        from deskflow.channels.session import get_session_manager

        manager = get_session_manager()
        sessions = await manager.get_user_sessions(user_id, channel_id)

        return {
            "success": True,
            "sessions": [s.to_dict() for s in sessions],
            "total": len(sessions),
        }

    except Exception as e:
        logger.error("list_user_sessions_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_session_stats():
    """Get session statistics."""
    try:
        from deskflow.channels.session import get_session_manager

        manager = get_session_manager()
        stats = await manager.get_stats()

        return {
            "success": True,
            "stats": stats,
        }

    except Exception as e:
        logger.error("get_session_stats_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def trigger_cleanup():
    """Trigger manual cleanup of expired sessions.

    Returns:
    - Cleanup result with deleted count
    """
    try:
        from deskflow.channels.session import get_session_manager

        manager = get_session_manager()
        deleted = await manager.cleanup_expired_sessions()

        return {
            "success": True,
            "deleted_count": deleted,
            "message": f"Cleaned up {deleted} expired sessions",
        }

    except Exception as e:
        logger.error("trigger_cleanup_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
