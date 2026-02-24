"""Memory management API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory"])


def _get_state() -> Any:
    """Get app state at runtime."""
    from deskflow.app import get_app_state
    return get_app_state()


@router.get("/stats")
async def get_memory_stats():
    """Get memory system statistics."""
    state = _get_state()

    if not state.memory:
        raise HTTPException(status_code=503, detail="Memory system not initialized")

    stats = state.memory.get_stats()

    # Get count
    count = await state.memory.count()
    stats["total_memories"] = count

    return stats


@router.post("/cleanup")
async def trigger_memory_cleanup():
    """Trigger manual memory cleanup (TTL + LRU eviction).

    This endpoint triggers the memory lifecycle manager to:
    - Delete expired memories based on TTL
    - Evict least recently used memories if over capacity

    Returns:
        Cleanup result with deleted memory counts.
    """
    state = _get_state()

    if not state.memory:
        raise HTTPException(status_code=503, detail="Memory system not initialized")

    try:
        result = await state.memory.cleanup_memories()

        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])

        return {
            "success": True,
            "cleanup_result": result,
        }

    except Exception as e:
        logger.error("memory_cleanup_trigger_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_memory_config():
    """Get memory lifecycle configuration."""
    state = _get_state()

    if not state.memory:
        raise HTTPException(status_code=503, detail="Memory system not initialized")

    stats = state.memory.get_stats()
    lifecycle = stats.get("lifecycle", {})

    return {
        "lifecycle_enabled": "config" in lifecycle,
        "config": lifecycle.get("config", {}),
    }


@router.get("/recent")
async def get_recent_memories(limit: int = 20):
    """Get recent memories.

    Args:
        limit: Maximum number of memories to return.

    Returns:
        List of recent memory entries.
    """
    state = _get_state()

    if not state.memory:
        raise HTTPException(status_code=503, detail="Memory system not initialized")

    try:
        memories = await state.memory.get_recent(limit)

        return {
            "memories": [
                {
                    "id": m.id,
                    "content": m.content,
                    "memory_type": m.memory_type,
                    "importance": m.importance,
                    "tags": m.tags,
                    "created_at": m.created_at,
                    "last_accessed": m.last_accessed,
                    "access_count": m.access_count,
                }
                for m in memories
            ],
            "total": len(memories),
        }

    except Exception as e:
        logger.error("get_recent_memories_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a specific memory.

    Args:
        memory_id: ID of the memory to delete.

    Returns:
        Deletion result.
    """
    state = _get_state()

    if not state.memory:
        raise HTTPException(status_code=503, detail="Memory system not initialized")

    try:
        deleted = await state.memory.delete(memory_id)

        if not deleted:
            raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found")

        return {
            "success": True,
            "message": f"Memory '{memory_id}' deleted",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_memory_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
