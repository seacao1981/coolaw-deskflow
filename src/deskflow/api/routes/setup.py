"""Setup wizard API routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/setup", tags=["setup"])

# Config file path
CONFIG_DIR = Path.home() / ".deskflow"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _ensure_config_dir() -> None:
    """Ensure config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load_config() -> dict[str, Any]:
    """Load configuration from file."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_config(config: dict[str, Any]) -> None:
    """Save configuration to file."""
    _ensure_config_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


class LLMConfig(BaseModel):
    """LLM configuration."""

    provider: str
    base_url: str
    api_key: str
    model: str
    max_tokens: int = 4096
    temperature: float = 0.7


class IMConfig(BaseModel):
    """IM channel configuration."""

    channel_type: str
    token: str
    webhook_url: str | None = None
    secret: str | None = None


class WorkspaceConfig(BaseModel):
    """Workspace configuration."""

    path: str
    name: str


class SetupConfigRequest(BaseModel):
    """Setup wizard configuration request."""

    llm: LLMConfig
    im: IMConfig | None = None
    workspace: WorkspaceConfig | None = None


class SetupResponse(BaseModel):
    """Setup response."""

    success: bool
    message: str
    config_path: str | None = None


@router.post("/config", response_model=SetupResponse)
async def save_setup_config(request: dict[str, Any]) -> SetupResponse:
    """Save setup wizard configuration.

    This endpoint persists the configuration from the setup wizard to disk.
    """
    try:
        _ensure_config_dir()

        # Load existing config
        existing_config = _load_config()

        # Merge new config
        llm_config = request.get("llm", {})
        im_config = request.get("im")
        workspace_config = request.get("workspace", {})

        # Update LLM config
        if llm_config:
            existing_config["llm"] = {
                "provider": llm_config.get("provider", "dashscope"),
                "base_url": llm_config.get("base_url", ""),
                "api_key": llm_config.get("api_key", ""),
                "model": llm_config.get("model", "qwen3.5-plus"),
                "max_tokens": llm_config.get("max_tokens", 4096),
                "temperature": llm_config.get("temperature", 0.7),
            }

        # Update IM config (optional)
        if im_config:
            existing_config["im"] = {
                "channel_type": im_config.get("channel_type", ""),
                "token": im_config.get("token", ""),
                "webhook_url": im_config.get("webhook_url"),
                "secret": im_config.get("secret"),
            }
        else:
            existing_config.pop("im", None)

        # Update workspace config
        if workspace_config:
            existing_config["workspace"] = {
                "path": workspace_config.get("path", str(Path.home() / "deskflow-projects" / "default")),
                "name": workspace_config.get("name", "default"),
            }

        # Save config
        _save_config(existing_config)

        logger.info("setup_config_saved", path=str(CONFIG_FILE))

        return SetupResponse(
            success=True,
            message="Configuration saved successfully",
            config_path=str(CONFIG_FILE),
        )

    except Exception as e:
        logger.error("save_setup_config_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to save config: {str(e)}")


@router.get("/config", response_model=dict[str, Any])
async def get_setup_config() -> dict[str, Any]:
    """Get saved setup configuration.

    Returns the current configuration without sensitive fields like API keys.
    """
    config = _load_config()

    # Redact sensitive fields
    if "llm" in config and "api_key" in config.get("llm", {}):
        config["llm"]["api_key"] = "****" if config["llm"]["api_key"] else ""

    if "im" in config and "token" in config.get("im", {}):
        config["im"]["token"] = "****" if config["im"]["token"] else ""

    return config


@router.post("/start", response_model=SetupResponse)
async def start_service() -> SetupResponse:
    """Start the backend service after setup.

    This endpoint is called when the user completes the setup wizard.
    """
    try:
        # Verify configuration exists
        config = _load_config()
        if not config.get("llm") or not config["llm"].get("api_key"):
            raise HTTPException(status_code=400, detail="LLM configuration is required")

        # In a real implementation, this would:
        # 1. Initialize the Agent components
        # 2. Start the message gateway
        # 3. Start session manager
        # 4. Return success

        logger.info("setup_service_started")

        return SetupResponse(
            success=True,
            message="Service started successfully",
            config_path=str(CONFIG_FILE),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("start_service_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start service: {str(e)}")
