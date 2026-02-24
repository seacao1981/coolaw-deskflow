"""Feishu (Lark) channel API routes."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from deskflow.channels.feishu import FeishuAdapter, FeishuConfig, FeishuMessage
from deskflow.channels.gateway import get_gateway, OutboundMessage, MessageType
from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/feishu", tags=["feishu"])


class FeishuConfigRequest(BaseModel):
    """Request model for Feishu configuration."""

    app_id: str = ""
    app_secret: str = ""
    verification_token: str = ""
    encrypt_key: str = ""
    bot_name: str = ""
    webhook_url: str = ""


class FeishuConfigResponse(BaseModel):
    """Response model for Feishu configuration."""

    channel_id: str
    channel_type: str = "feishu"
    enabled: bool
    configured: bool
    app_id: str
    bot_name: str
    webhook_url: str


class FeishuMessageResponse(BaseModel):
    """Response model for Feishu message."""

    message_id: str
    sender_id: str
    content: str
    message_type: str
    chat_type: str
    timestamp: str


class FeishuSendRequest(BaseModel):
    """Request model for sending Feishu message."""

    recipient_id: str
    content: str
    message_type: str = "text"
    receive_id_type: str = "open_id"


class FeishuSendResponse(BaseModel):
    """Response model for send result."""

    success: bool
    message_id: str | None = None
    error: str | None = None


# In-memory config storage (should be persisted)
_feishu_configs: dict[str, dict[str, Any]] = {}


@router.get("/config", response_model=FeishuConfigResponse)
async def get_feishu_config(channel_id: str = "feishu") -> FeishuConfigResponse:
    """Get Feishu channel configuration."""
    gateway = get_gateway()
    adapter = gateway.get_adapter(channel_id)

    if adapter:
        config_data = adapter.to_dict()
        return FeishuConfigResponse(
            channel_id=channel_id,
            enabled=adapter.enabled,
            configured=bool(config_data.get("app_id") and config_data.get("app_secret")),
            app_id=config_data.get("app_id", ""),
            bot_name=config_data.get("bot_name", ""),
            webhook_url=config_data.get("webhook_url", ""),
        )
    else:
        # Return stored config if adapter not registered
        stored = _feishu_configs.get(channel_id, {})
        return FeishuConfigResponse(
            channel_id=channel_id,
            enabled=False,
            configured=bool(stored.get("app_id") and stored.get("app_secret")),
            app_id=stored.get("app_id", ""),
            bot_name=stored.get("bot_name", ""),
            webhook_url=stored.get("webhook_url", ""),
        )


@router.post("/config")
async def save_feishu_config(config: FeishuConfigRequest, channel_id: str = "feishu") -> dict[str, Any]:
    """Save Feishu channel configuration."""
    # Store configuration
    _feishu_configs[channel_id] = {
        "app_id": config.app_id,
        "app_secret": config.app_secret,
        "verification_token": config.verification_token,
        "encrypt_key": config.encrypt_key,
        "bot_name": config.bot_name,
        "webhook_url": config.webhook_url,
        "channel_id": channel_id,
    }

    # Try to register/update adapter
    gateway = get_gateway()
    feishu_config = FeishuConfig(
        app_id=config.app_id,
        app_secret=config.app_secret,
        verification_token=config.verification_token,
        encrypt_key=config.encrypt_key,
        bot_name=config.bot_name,
        webhook_url=config.webhook_url,
    )

    adapter = FeishuAdapter(config=feishu_config, channel_id=channel_id)

    # Unregister existing adapter if present
    existing = gateway.get_adapter(channel_id)
    if existing:
        gateway.unregister_adapter(channel_id)

    # Register new adapter
    gateway.register_adapter(adapter)

    logger.info("feishu_config_saved", channel_id=channel_id)

    return {
        "success": True,
        "message": "Feishu configuration saved",
        "channel_id": channel_id,
    }


@router.delete("/config")
async def delete_feishu_config(channel_id: str = "feishu") -> dict[str, Any]:
    """Delete Feishu channel configuration."""
    # Remove from storage
    if channel_id in _feishu_configs:
        del _feishu_configs[channel_id]

    # Unregister adapter
    gateway = get_gateway()
    existing = gateway.get_adapter(channel_id)
    if existing:
        gateway.unregister_adapter(channel_id)

    logger.info("feishu_config_deleted", channel_id=channel_id)

    return {
        "success": True,
        "message": "Feishu configuration deleted",
        "channel_id": channel_id,
    }


@router.post("/toggle")
async def toggle_feishu_channel(enable: bool, channel_id: str = "feishu") -> dict[str, Any]:
    """Enable or disable Feishu channel."""
    gateway = get_gateway()
    adapter = gateway.get_adapter(channel_id)

    if not adapter:
        # Try to create adapter from stored config
        stored = _feishu_configs.get(channel_id)
        if not stored:
            raise HTTPException(status_code=404, detail="Feishu channel not configured")

        feishu_config = FeishuConfig(**stored)
        adapter = FeishuAdapter(config=feishu_config, channel_id=channel_id)
        gateway.register_adapter(adapter)

    if enable:
        adapter.enable()
        logger.info("feishu_channel_enabled", channel_id=channel_id)
    else:
        adapter.disable()
        logger.info("feishu_channel_disabled", channel_id=channel_id)

    return {
        "success": True,
        "enabled": enable,
        "channel_id": channel_id,
    }


@router.post("/test")
async def test_feishu_connection(channel_id: str = "feishu") -> dict[str, Any]:
    """Test Feishu channel connection."""
    gateway = get_gateway()
    adapter = gateway.get_adapter(channel_id)

    if not adapter:
        # Try to create adapter from stored config
        stored = _feishu_configs.get(channel_id)
        if not stored:
            raise HTTPException(status_code=404, detail="Feishu channel not configured")

        feishu_config = FeishuConfig(**stored)
        adapter = FeishuAdapter(config=feishu_config, channel_id=channel_id)

    # Perform health check
    healthy = await adapter.health_check()

    return {
        "success": healthy,
        "healthy": healthy,
        "channel_id": channel_id,
        "channel_type": "feishu",
    }


@router.post("/webhook")
async def feishu_webhook(request: Request, channel_id: str = "feishu") -> dict[str, Any]:
    """Receive Feishu webhook messages.

    Feishu sends a challenge request first for URL verification,
    then sends actual messages.
    """
    body = await request.body()
    data = await request.json()

    logger.info("feishu_webhook_received", channel_id=channel_id, event_type=data.get("header", {}).get("event_type"))

    # Get adapter
    gateway = get_gateway()
    adapter = gateway.get_adapter(channel_id)

    if not adapter:
        # Try to create adapter from stored config
        stored = _feishu_configs.get(channel_id)
        if stored:
            feishu_config = FeishuConfig(**stored)
            adapter = FeishuAdapter(config=feishu_config, channel_id=channel_id)
        else:
            adapter = FeishuAdapter(channel_id=channel_id)

    # Parse message
    try:
        message = await adapter.parse_message(data)
    except Exception as e:
        logger.error("feishu_message_parse_error", error=str(e))
        raise HTTPException(status_code=400, detail=f"Failed to parse message: {e}")

    # Handle URL verification challenge
    if message.content and "challenge" in (data or {}):
        logger.info("feishu_challenge_response", challenge=message.content)
        return {"challenge": message.content}

    # Route message to gateway for processing
    if message.content and not message.metadata.get("challenge"):
        gateway.route_message(message)
        logger.info("feishu_message_routed", message_id=message.message_id)

    return {"status": "ok", "message_id": message.message_id}


@router.post("/send", response_model=FeishuSendResponse)
async def send_feishu_message(request: FeishuSendRequest, channel_id: str = "feishu") -> FeishuSendResponse:
    """Send a message to Feishu."""
    gateway = get_gateway()
    adapter = gateway.get_adapter(channel_id)

    if not adapter:
        # Try to create adapter from stored config
        stored = _feishu_configs.get(channel_id)
        if not stored:
            return FeishuSendResponse(
                success=False,
                error="Feishu channel not configured",
            )

        feishu_config = FeishuConfig(**stored)
        adapter = FeishuAdapter(config=feishu_config, channel_id=channel_id)

    # Build outbound message
    outbound = OutboundMessage(
        channel_id=channel_id,
        content=request.content,
        recipient_id=request.recipient_id,
        message_type=MessageType(request.message_type),
        metadata={"receive_id_type": request.receive_id_type},
    )

    # Send message
    success = await adapter.send(outbound)

    if success:
        return FeishuSendResponse(
            success=True,
            message_id=outbound.recipient_id,
        )
    else:
        return FeishuSendResponse(
            success=False,
            error="Failed to send message",
        )


@router.get("/adapters")
async def list_feishu_adapters() -> dict[str, Any]:
    """List all registered Feishu adapters."""
    gateway = get_gateway()
    adapters = gateway.list_adapters()

    feishu_adapters = [a for a in adapters if a["channel_type"] == "feishu"]

    return {
        "adapters": feishu_adapters,
        "count": len(feishu_adapters),
    }
