"""Memory insight extraction API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/memory/insights", tags=["memory-insights"])


def _get_state() -> Any:
    """Get app state at runtime."""
    from deskflow.app import get_app_state
    return get_app_state()


def _get_extractor() -> Any:
    """Get insight extractor."""
    from deskflow.memory.extractor import get_extractor
    return get_extractor()


@router.post("/extract")
async def extract_insights(request: dict):
    """Extract insights from text.

    Request body:
    - text: Text to analyze
    - context: Optional context

    Returns:
    - Entities, sentiments, insights, topics, and summary
    """
    try:
        text = request.get("text", "")
        context = request.get("context", "")

        if not text:
            raise HTTPException(status_code=400, detail="text is required")

        extractor = _get_extractor()
        result = extractor.extract(text, context)

        return {
            "success": True,
            "result": result.to_dict(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("extract_insights_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract/batch")
async def extract_insights_batch(request: dict):
    """Extract insights from multiple texts.

    Request body:
    - texts: List of texts to analyze

    Returns:
    - Aggregated insights result
    """
    try:
        texts = request.get("texts", [])

        if not texts:
            raise HTTPException(status_code=400, detail="texts array is required")

        extractor = _get_extractor()
        result = extractor.extract_batch(texts)

        return {
            "success": True,
            "result": result.to_dict(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("extract_insights_batch_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entities")
async def get_extracted_entities():
    """Get recently extracted entities from conversations.

    Note: This is a placeholder - will be implemented with persistence.
    """
    # TODO: Implement entity persistence and retrieval
    return {
        "success": True,
        "entities": [],
        "total": 0,
    }


@router.get("/preferences")
async def get_user_preferences():
    """Get extracted user preferences.

    Note: This integrates with user profile system.
    """
    try:
        from deskflow.core.user_profile import get_profile_manager

        manager = get_profile_manager()
        profile = await manager.load_profile()

        # Convert traits to preferences format
        preferences = []
        for trait_name, trait in profile.traits.items():
            if "prefers" in trait_name:
                preferences.append({
                    "type": "preference",
                    "target": trait_name.replace("prefers_", ""),
                    "confidence": trait.confidence,
                })

        return {
            "success": True,
            "preferences": preferences,
            "total": len(preferences),
        }

    except Exception as e:
        logger.error("get_user_preferences_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
