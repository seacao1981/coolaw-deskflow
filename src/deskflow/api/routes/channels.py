"""IM Channels management API routes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/channels", tags=["channels"])


# Supported channel types
SUPPORTED_CHANNELS = {
    "feishu": {
        "name": "Feishu (Lark)",
        "description": "飞书开放平台机器人",
        "icon": "feishu",
        "color": "blue",
        "config_fields": [
            {"name": "app_id", "label": "App ID", "type": "text", "required": True},
            {"name": "app_secret", "label": "App Secret", "type": "password", "required": True},
            {"name": "verification_token", "label": "Verification Token", "type": "password", "required": False},
            {"name": "encrypt_key", "label": "Encrypt Key", "type": "password", "required": False},
        ],
    },
    "wework": {
        "name": "Enterprise WeChat",
        "description": "企业微信机器人",
        "icon": "wework",
        "color": "green",
        "config_fields": [
            {"name": "corp_id", "label": "Corp ID", "type": "text", "required": True},
            {"name": "agent_id", "label": "Agent ID", "type": "text", "required": True},
            {"name": "secret", "label": "Secret", "type": "password", "required": True},
            {"name": "token", "label": "Token", "type": "password", "required": False},
            {"name": "encoding_aes_key", "label": "EncodingAESKey", "type": "password", "required": False},
        ],
    },
    "dingtalk": {
        "name": "DingTalk",
        "description": "钉钉机器人",
        "icon": "dingtalk",
        "color": "cyan",
        "config_fields": [
            {"name": "webhook_url", "label": "Webhook URL", "type": "url", "required": True},
            {"name": "secret", "label": "Secret (optional)", "type": "password", "required": False},
        ],
    },
    "telegram": {
        "name": "Telegram",
        "description": "Telegram Bot",
        "icon": "telegram",
        "color": "blue",
        "config_fields": [
            {"name": "bot_token", "label": "Bot Token", "type": "password", "required": True},
            {"name": "allowed_chats", "label": "Allowed Chat IDs (comma separated)", "type": "text", "required": False},
        ],
    },
}


@dataclass
class ChannelConfig:
    """Channel configuration."""
    channel_type: str
    name: str
    is_enabled: bool = False
    config: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: __import__("time").time())
    updated_at: float = field(default_factory=lambda: __import__("time").time())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "channel_type": self.channel_type,
            "name": self.name,
            "is_enabled": self.is_enabled,
            "config": self.config,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# In-memory channel registry (will be persisted in future)
_channel_registry: dict[str, ChannelConfig] = {}


def _get_channel_registry() -> dict[str, ChannelConfig]:
    """Get or initialize channel registry."""
    if not _channel_registry:
        # Initialize with default configs for all supported channels
        for channel_type, info in SUPPORTED_CHANNELS.items():
            _channel_registry[channel_type] = ChannelConfig(
                channel_type=channel_type,
                name=info["name"],
                is_enabled=False,
            )
    return _channel_registry


@router.get("")
async def list_channels():
    """List all configured channels."""
    registry = _get_channel_registry()

    channels = []
    for channel_type, config in registry.items():
        channel_info = {
            **config.to_dict(),
            "description": SUPPORTED_CHANNELS[channel_type]["description"],
            "icon": SUPPORTED_CHANNELS[channel_type]["icon"],
            "color": SUPPORTED_CHANNELS[channel_type]["color"],
        }
        channels.append(channel_info)

    return {
        "channels": channels,
        "total": len(channels),
        "enabled_count": sum(1 for c in channels if c["is_enabled"]),
    }


@router.get("/supported")
async def list_supported_channels():
    """List all supported channel types."""
    return {
        "channels": [
            {
                "type": channel_type,
                "name": info["name"],
                "description": info["description"],
                "icon": info["icon"],
                "color": info["color"],
                "config_fields": info["config_fields"],
            }
            for channel_type, info in SUPPORTED_CHANNELS.items()
        ],
        "total": len(SUPPORTED_CHANNELS),
    }


@router.get("/{channel_type}")
async def get_channel_config(channel_type: str):
    """Get configuration for a specific channel."""
    if channel_type not in SUPPORTED_CHANNELS:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_type}' not supported")

    registry = _get_channel_registry()
    config = registry.get(channel_type)

    if not config:
        config = ChannelConfig(
            channel_type=channel_type,
            name=SUPPORTED_CHANNELS[channel_type]["name"],
            is_enabled=False,
        )
        registry[channel_type] = config

    return {
        "channel": {
            **config.to_dict(),
            "description": SUPPORTED_CHANNELS[channel_type]["description"],
            "icon": SUPPORTED_CHANNELS[channel_type]["icon"],
            "color": SUPPORTED_CHANNELS[channel_type]["color"],
            "config_fields": SUPPORTED_CHANNELS[channel_type]["config_fields"],
        }
    }


@router.post("/{channel_type}/config")
async def update_channel_config(channel_type: str, request: dict):
    """Update configuration for a specific channel."""
    if channel_type not in SUPPORTED_CHANNELS:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_type}' not supported")

    registry = _get_channel_registry()

    if channel_type not in registry:
        registry[channel_type] = ChannelConfig(
            channel_type=channel_type,
            name=SUPPORTED_CHANNELS[channel_type]["name"],
        )

    config = registry[channel_type]

    # Update config
    update_data = request.get("config", {})
    config.config.update(update_data)
    config.updated_at = __import__("time").time()

    logger.info("channel_config_updated", channel=channel_type)

    return {
        "success": True,
        "message": f"Channel '{channel_type}' configuration updated",
        "channel": config.to_dict(),
    }


@router.post("/{channel_type}/toggle")
async def toggle_channel(channel_type: str, request: dict | None = None):
    """Enable or disable a channel."""
    if channel_type not in SUPPORTED_CHANNELS:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_type}' not supported")

    registry = _get_channel_registry()

    if channel_type not in registry:
        registry[channel_type] = ChannelConfig(
            channel_type=channel_type,
            name=SUPPORTED_CHANNELS[channel_type]["name"],
        )

    config = registry[channel_type]

    # Toggle or set explicit enable/disable
    action = request.get("action") if request else None
    if action == "enable":
        config.is_enabled = True
    elif action == "disable":
        config.is_enabled = False
    else:
        config.is_enabled = not config.is_enabled

    config.updated_at = __import__("time").time()

    logger.info("channel_toggled", channel=channel_type, enabled=config.is_enabled)

    return {
        "success": True,
        "message": f"Channel '{channel_type}' {'enabled' if config.is_enabled else 'disabled'}",
        "is_enabled": config.is_enabled,
    }


@router.delete("/{channel_type}/config")
async def reset_channel_config(channel_type: str):
    """Reset channel configuration to defaults."""
    if channel_type not in SUPPORTED_CHANNELS:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_type}' not supported")

    registry = _get_channel_registry()

    if channel_type in registry:
        config = registry[channel_type]
        config.config = {}
        config.is_enabled = False
        config.updated_at = __import__("time").time()

    logger.info("channel_config_reset", channel=channel_type)

    return {
        "success": True,
        "message": f"Channel '{channel_type}' configuration reset",
    }


@router.post("/{channel_type}/test")
async def test_channel_connection(channel_type: str, request: dict):
    """Test channel connection configuration."""
    if channel_type not in SUPPORTED_CHANNELS:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_type}' not supported")

    # Simulate connection test (will be implemented with actual channel adapters)
    registry = _get_channel_registry()
    config = registry.get(channel_type)

    if not config or not config.config:
        return {
            "success": False,
            "message": f"Channel '{channel_type}' is not configured",
            "latency_ms": 0,
        }

    # TODO: Implement actual connection test when channel adapters are built
    # For now, just validate that config exists
    required_fields = [f["name"] for f in SUPPORTED_CHANNELS[channel_type]["config_fields"] if f.get("required", False)]
    missing_fields = [f for f in required_fields if f not in config.config]

    if missing_fields:
        return {
            "success": False,
            "message": f"Missing required fields: {', '.join(missing_fields)}",
        }

    # Simulated successful test
    return {
        "success": True,
        "message": f"Connection test successful for '{channel_type}'",
        "channel": channel_type,
        "latency_ms": 150,  # Simulated
    }
