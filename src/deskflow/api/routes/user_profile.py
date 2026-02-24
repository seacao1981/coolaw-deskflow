"""User profile management API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/user", tags=["user"])


def _get_state() -> Any:
    """Get app state at runtime."""
    from deskflow.app import get_app_state
    return get_app_state()


def _get_profile_manager() -> Any:
    """Get profile manager from app state or create new one."""
    from deskflow.core.user_profile import get_profile_manager
    return get_profile_manager()


@router.get("/profile")
async def get_user_profile():
    """Get complete user profile."""
    try:
        manager = _get_profile_manager()
        profile = await manager.load_profile()

        return {
            "success": True,
            "profile": profile.to_dict(),
        }

    except Exception as e:
        logger.error("get_user_profile_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profile/stats")
async def get_user_profile_stats():
    """Get user profile statistics."""
    try:
        manager = _get_profile_manager()
        # Load profile first
        await manager.load_profile()

        return {
            "success": True,
            "stats": manager.get_stats(),
        }

    except Exception as e:
        logger.error("get_user_profile_stats_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profile/basic")
async def update_user_basic_info(request: dict):
    """Update basic user information.

    Request body:
    - name: Optional user name
    - email: Optional user email
    - timezone: Optional timezone
    - language: Optional language code
    """
    try:
        manager = _get_profile_manager()

        name = request.get("name")
        email = request.get("email")
        timezone = request.get("timezone")
        language = request.get("language")

        profile = await manager.update_basic_info(
            name=name,
            email=email,
            timezone=timezone,
            language=language,
        )

        return {
            "success": True,
            "message": "User info updated",
            "profile": profile.to_dict(),
        }

    except Exception as e:
        logger.error("update_user_basic_info_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profile/preferences")
async def update_user_preferences(request: dict):
    """Update user preferences.

    Request body:
    - response_style: "concise" | "detailed" | "technical" | "casual"
    - code_language: Preferred programming language
    - explanation_depth: "beginner" | "intermediate" | "expert"
    """
    try:
        manager = _get_profile_manager()

        response_style = request.get("response_style")
        code_language = request.get("code_language")
        explanation_depth = request.get("explanation_depth")

        profile = await manager.update_preferences(
            response_style=response_style,
            code_language=code_language,
            explanation_depth=explanation_depth,
        )

        return {
            "success": True,
            "message": "Preferences updated",
            "profile": profile.to_dict(),
        }

    except Exception as e:
        logger.error("update_user_preferences_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profile/learn")
async def learn_from_conversation(request: dict):
    """Learn user traits from a conversation.

    Request body:
    - messages: List of {role, content} message dicts

    Returns:
    - Detected traits and learning statistics
    """
    try:
        manager = _get_profile_manager()

        messages = request.get("messages", [])
        if not messages:
            raise HTTPException(status_code=400, detail="messages array is required")

        result = await manager.learn_from_conversation(messages)

        return {
            "success": True,
            "learning_result": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("learn_from_conversation_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profile/personalization")
async def get_personalization_context():
    """Get personalization context for response generation.

    Returns context that can be used to customize AI responses.
    """
    try:
        manager = _get_profile_manager()
        context = await manager.get_personalization_context()

        return {
            "success": True,
            "context": context,
        }

    except Exception as e:
        logger.error("get_personalization_context_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profile/traits")
async def get_user_traits():
    """Get all detected user traits."""
    try:
        manager = _get_profile_manager()
        profile = await manager.load_profile()

        # Group traits by category
        traits_by_category: dict[str, list[dict]] = {}
        for trait_name, trait in profile.traits.items():
            category = trait.category
            if category not in traits_by_category:
                traits_by_category[category] = []
            traits_by_category[category].append(trait.to_dict())

        return {
            "success": True,
            "traits": traits_by_category,
            "total_traits": len(profile.traits),
        }

    except Exception as e:
        logger.error("get_user_traits_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/profile/trait/{trait_name}")
async def delete_trait(trait_name: str):
    """Delete a specific user trait.

    Args:
        trait_name: Name of the trait to delete.
    """
    try:
        manager = _get_profile_manager()
        profile = await manager.load_profile()

        if trait_name not in profile.traits:
            raise HTTPException(status_code=404, detail=f"Trait '{trait_name}' not found")

        del profile.traits[trait_name]
        await manager.save_profile()

        return {
            "success": True,
            "message": f"Trait '{trait_name}' deleted",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_trait_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
