"""Identity management API routes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/identity", tags=["identity"])


def _get_state() -> Any:
    """Get app state at runtime."""
    from deskflow.app import get_app_state
    return get_app_state()


def _get_identity_dir() -> Path:
    """Get the identity directory."""
    state = _get_state()
    from deskflow.config import AppConfig
    config: AppConfig = state.config
    return config.get_project_root() / "identity"


# Pre-built personas
PERSONAS = {
    "default": {
        "name": "Default",
        "description": "Standard assistant persona",
        "soul": "You are DeskFlow Agent, an intelligent AI assistant.",
        "agent": "Be helpful, accurate, and concise.",
        "user": "",
    },
    "butler": {
        "name": "Butler",
        "description": "Professional butler-style assistant",
        "soul": "You are a professional butler, dedicated to serving the user with elegance.",
        "agent": "Speak formally, anticipate needs, and provide refined service.",
        "user": "The user prefers formal address and detailed explanations.",
    },
    "tech_expert": {
        "name": "Tech Expert",
        "description": "Technical expert persona",
        "soul": "You are a technical expert with deep knowledge of software and systems.",
        "agent": "Provide precise technical answers with code examples when relevant.",
        "user": "The user is a developer and prefers technical depth.",
    },
    "business": {
        "name": "Business",
        "description": "Business professional persona",
        "soul": "You are a business professional focused on efficiency and results.",
        "agent": "Provide concise, action-oriented responses.",
        "user": "The user values brevity and actionable insights.",
    },
}


@router.get("")
async def list_personas():
    """List all available personas."""
    identity_dir = _get_identity_dir()

    # Get pre-built personas
    personas = []
    for key, data in PERSONAS.items():
        personas.append({
            "key": key,
            "name": data["name"],
            "description": data["description"],
            "is_custom": False,
        })

    # Scan for custom personas
    personas_dir = identity_dir / "personas"
    if personas_dir.exists():
        for item in personas_dir.iterdir():
            if item.is_dir() and not item.name.startswith("_"):
                meta_file = item / "meta.json"
                if meta_file.exists():
                    import json
                    try:
                        with open(meta_file) as f:
                            meta = json.load(f)
                        personas.append({
                            "key": item.name,
                            "name": meta.get("name", item.name),
                            "description": meta.get("description", "Custom persona"),
                            "is_custom": True,
                        })
                    except Exception:
                        pass

    return {"personas": personas, "total": len(personas)}


@router.get("/{persona_key}")
async def get_persona(persona_key: str):
    """Get details of a specific persona."""
    identity_dir = _get_identity_dir()

    # Check pre-built personas
    if persona_key in PERSONAS:
        data = PERSONAS[persona_key]
        return {
            "key": persona_key,
            "name": data["name"],
            "description": data["description"],
            "soul": data["soul"],
            "agent": data["agent"],
            "user": data["user"],
            "is_custom": False,
        }

    # Check custom personas
    personas_dir = identity_dir / "personas"
    persona_path = personas_dir / persona_key

    if not persona_path.exists():
        raise HTTPException(status_code=404, detail=f"Persona '{persona_key}' not found")

    # Load persona files
    soul_file = persona_path / "SOUL.md"
    agent_file = persona_path / "AGENT.md"
    user_file = persona_path / "USER.md"
    meta_file = persona_path / "meta.json"

    import json
    meta = {}
    if meta_file.exists():
        with open(meta_file) as f:
            meta = json.load(f)

    return {
        "key": persona_key,
        "name": meta.get("name", persona_key),
        "description": meta.get("description", "Custom persona"),
        "soul": soul_file.read_text() if soul_file.exists() else "",
        "agent": agent_file.read_text() if agent_file.exists() else "",
        "user": user_file.read_text() if user_file.exists() else "",
        "is_custom": True,
    }


@router.post("/{persona_key}/activate")
async def activate_persona(persona_key: str):
    """Activate a persona."""
    identity_dir = _get_identity_dir()

    # Check if persona exists
    if persona_key not in PERSONAS:
        personas_dir = identity_dir / "personas"
        if not (personas_dir / persona_key).exists():
            raise HTTPException(status_code=404, detail=f"Persona '{persona_key}' not found")

    # Save current persona
    current_persona_file = identity_dir / "current_persona.txt"
    with open(current_persona_file, "w") as f:
        f.write(persona_key)

    logger.info("persona_activated", persona=persona_key)

    return {
        "success": True,
        "message": f"Persona '{persona_key}' activated",
        "persona": persona_key,
    }


@router.post("/custom")
async def create_custom_persona(request: dict):
    """Create a custom persona."""
    identity_dir = _get_identity_dir()

    persona_key = request.get("key")
    if not persona_key:
        raise HTTPException(status_code=400, detail="Persona key is required")

    # Validate key format
    if not persona_key.replace("_", "").isalnum():
        raise HTTPException(
            status_code=400,
            detail="Persona key must contain only letters, numbers, and underscores",
        )

    # Create persona directory
    personas_dir = identity_dir / "personas"
    personas_dir.mkdir(parents=True, exist_ok=True)

    persona_path = personas_dir / persona_key

    if persona_path.exists():
        raise HTTPException(status_code=400, detail=f"Persona '{persona_key}' already exists")

    persona_path.mkdir(parents=True, exist_ok=True)

    # Save persona files
    soul = request.get("soul", "")
    agent = request.get("agent", "")
    user = request.get("user", "")
    name = request.get("name", persona_key)
    description = request.get("description", "Custom persona")

    if soul:
        with open(persona_path / "SOUL.md", "w", encoding="utf-8") as f:
            f.write(soul)

    if agent:
        with open(persona_path / "AGENT.md", "w", encoding="utf-8") as f:
            f.write(agent)

    if user:
        with open(persona_path / "USER.md", "w", encoding="utf-8") as f:
            f.write(user)

    # Save metadata
    import json
    meta = {
        "name": name,
        "description": description,
        "created_at": __import__("datetime").datetime.now().isoformat(),
    }

    with open(persona_path / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    logger.info("custom_persona_created", persona=persona_key)

    return {
        "success": True,
        "message": f"Custom persona '{persona_key}' created",
        "persona": persona_key,
    }


@router.delete("/custom/{persona_key}")
async def delete_custom_persona(persona_key: str):
    """Delete a custom persona."""
    import shutil

    identity_dir = _get_identity_dir()
    personas_dir = identity_dir / "personas"
    persona_path = personas_dir / persona_key

    if not persona_path.exists():
        raise HTTPException(status_code=404, detail=f"Persona '{persona_key}' not found")

    # Don't allow deleting pre-built personas
    if persona_key in PERSONAS:
        raise HTTPException(status_code=400, detail="Cannot delete pre-built persona")

    # Delete persona directory
    shutil.rmtree(persona_path)

    logger.info("custom_persona_deleted", persona=persona_key)

    return {
        "success": True,
        "message": f"Custom persona '{persona_key}' deleted",
    }


@router.get("/current")
async def get_current_persona():
    """Get the currently active persona."""
    identity_dir = _get_identity_dir()
    current_persona_file = identity_dir / "current_persona.txt"

    current = "default"
    if current_persona_file.exists():
        current = current_persona_file.read_text().strip()

    # Get persona details
    if current in PERSONAS:
        data = PERSONAS[current]
        return {
            "key": current,
            "name": data["name"],
            "description": data["description"],
            "is_custom": False,
        }

    # Check if custom persona
    personas_dir = identity_dir / "personas"
    persona_path = personas_dir / current

    if persona_path.exists():
        import json
        meta_file = persona_path / "meta.json"
        meta = {}
        if meta_file.exists():
            with open(meta_file) as f:
                meta = json.load(f)

        return {
            "key": current,
            "name": meta.get("name", current),
            "description": meta.get("description", "Custom persona"),
            "is_custom": True,
        }

    return {"key": "default", "name": "Default", "description": "Default persona", "is_custom": False}
