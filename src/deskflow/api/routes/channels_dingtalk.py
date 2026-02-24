"""DingTalk (钉钉) channel API routes."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from deskflow.channels.dingtalk import DingTalkAdapter, DingTalkConfig, DingTalkMessage
from deskflow.channels.gateway import get_gateway, OutboundMessage, MessageType
from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/dingtalk", tags=["dingtalk"])


class DingTalkConfigRequest(BaseModel):
    """Request model for DingTalk configuration."""

    app_key: str = ""
    app_secret: str = ""
    access_token: str = ""
    webhook_url: str = ""
    agent_id: str = ""


class DingTalkConfigResponse(BaseModel):
    """Response model for DingTalk configuration."""

    channel_id: str
    channel_type: str = "dingtalk"
    enabled: bool
    configured: bool
    app_key: str
    agent_id: str
    webhook_url: str


class DingTalkSendRequest(BaseModel):
    """Request model for sending DingTalk message."""

    recipient_id: str
    content: str
    message_type: str = "text"


class DingTalkSendResponse(BaseModel):
    """Response model for send result."""

    success: bool
    message_id: str | None = None
    error: str | None = None


# In-memory config storage
_dingtalk_configs: dict[str, dict[str, Any]] = {}


@router.get("/config", response_model=DingTalkConfigResponse)
async def get_dingtalk_config(channel_id: str = "dingtalk") -> DingTalkConfigResponse:
    """Get DingTalk channel configuration."""
    gateway = get_gateway()
    adapter = gateway.get_adapter(channel_id)

    if adapter:
        config_data = adapter.to_dict()
        return DingTalkConfigResponse(
            channel_id=channel_id,
            enabled=adapter.enabled,
            configured=bool(config_data.get("app_key") and config_data.get("app_secret")),
            app_key=config_data.get("app_key", ""),
            agent_id=config_data.get("agent_id", ""),
            webhook_url=config_data.get("webhook_url", ""),
        )
    else:
        stored = _dingtalk_configs.get(channel_id, {})
        return DingTalkConfigResponse(
            channel_id=channel_id,
            enabled=False,
            configured=bool(stored.get("app_key") and stored.get("app_secret")),
            app_key=stored.get("app_key", ""),
            agent_id=stored.get("agent_id", ""),
            webhook_url=stored.get("webhook_url", ""),
        )


@router.post("/config")
async def save_dingtalk_config(
    config: DingTalkConfigRequest, channel_id: str = "dingtalk"
) -> dict[str, Any]:
    """Save DingTalk channel configuration."""
    _dingtalk_configs[channel_id] = {
        "app_key": config.app_key,
        "app_secret": config.app_secret,
        "access_token": config.access_token,
        "webhook_url": config.webhook_url,
        "agent_id": config.agent_id,
        "channel_id": channel_id,
    }

    # Create and register adapter
    gateway = get_gateway()
    dingtalk_config = DingTalkConfig(
        app_key=config.app_key,
        app_secret=config.app_secret,
        access_token=config.access_token,
        webhook_url=config.webhook_url,
        agent_id=config.agent_id,
    )

    adapter = DingTalkAdapter(config=dingtalk_config, channel_id=channel_id)

    # Unregister existing if present
    existing = gateway.get_adapter(channel_id)
    if existing:
        gateway.unregister_adapter(channel_id)

    gateway.register_adapter(adapter)

    logger.info("dingtalk_config_saved", channel_id=channel_id)

    return {
        "success": True,
        "message": "DingTalk configuration saved",
        "channel_id": channel_id,
    }


@router.delete("/config")
async def delete_dingtalk_config(channel_id: str = "dingtalk") -> dict[str, Any]:
    """Delete DingTalk channel configuration."""
    if channel_id in _dingtalk_configs:
        del _dingtalk_configs[channel_id]

    gateway = get_gateway()
    existing = gateway.get_adapter(channel_id)
    if existing:
        gateway.unregister_adapter(channel_id)

    logger.info("dingtalk_config_deleted", channel_id=channel_id)

    return {
        "success": True,
        "message": "DingTalk configuration deleted",
        "channel_id": channel_id,
    }


@router.post("/toggle")
async def toggle_dingtalk_channel(enable: bool, channel_id: str = "dingtalk") -> dict[str, Any]:
    """Enable or disable DingTalk channel."""
    gateway = get_gateway()
    adapter = gateway.get_adapter(channel_id)

    if not adapter:
        stored = _dingtalk_configs.get(channel_id)
        if not stored:
            raise HTTPException(status_code=404, detail="DingTalk channel not configured")

        dingtalk_config = DingTalkConfig(**stored)
        adapter = DingTalkAdapter(config=dingtalk_config, channel_id=channel_id)
        gateway.register_adapter(adapter)

    if enable:
        adapter.enable()
        logger.info("dingtalk_channel_enabled", channel_id=channel_id)
    else:
        adapter.disable()
        logger.info("dingtalk_channel_disabled", channel_id=channel_id)

    return {
        "success": True,
        "enabled": enable,
        "channel_id": channel_id,
    }


@router.post("/test")
async def test_dingtalk_connection(channel_id: str = "dingtalk") -> dict[str, Any]:
    """Test DingTalk channel connection."""
    gateway = get_gateway()
    adapter = gateway.get_adapter(channel_id)

    if not adapter:
        stored = _dingtalk_configs.get(channel_id)
        if not stored:
            raise HTTPException(status_code=404, detail="DingTalk channel not configured")

        dingtalk_config = DingTalkConfig(**stored)
        adapter = DingTalkAdapter(config=dingtalk_config, channel_id=channel_id)

    healthy = await adapter.health_check()

    return {
        "success": healthy,
        "healthy": healthy,
        "channel_id": channel_id,
        "channel_type": "dingtalk",
    }


@router.post("/callback")
async def dingtalk_callback(
    request: Request,
    timestamp: str = Query(None),
    signature: str = Query(None),
    channel_id: str = "dingtalk",
) -> dict[str, Any]:
    """Handle DingTalk message callback.

    DingTalk sends POST requests to this endpoint when receiving messages.
    """
    body = await request.body()

    # Parse based on content type
    content_type = request.headers.get("content-type", "")
    if "json" in content_type.lower():
        data = await request.json() if body else {}
    else:
        # Try to parse as JSON anyway
        try:
            data = await request.json() if body else {}
        except Exception:
            data = {}

    # Add query params to data
    if timestamp:
        data["timestamp"] = timestamp
    if signature:
        data["signature"] = signature

    logger.info("dingtalk_callback_received", channel_id=channel_id, msg_type=data.get("msgtype"))

    # Get or create adapter
    gateway = get_gateway()
    adapter = gateway.get_adapter(channel_id)

    if not adapter:
        stored = _dingtalk_configs.get(channel_id)
        if stored:
            dingtalk_config = DingTalkConfig(**stored)
            adapter = DingTalkAdapter(config=dingtalk_config, channel_id=channel_id)
        else:
            adapter = DingTalkAdapter(channel_id=channel_id)

    # Parse message
    try:
        message = await adapter.parse_message(data)
    except Exception as e:
        logger.error("dingtalk_message_parse_error", error=str(e))
        raise HTTPException(status_code=400, detail=f"Failed to parse message: {e}")

    # Handle verification request
    if message.metadata.get("test"):
        logger.info("dingtalk_verification_acknowledged", channel_id=channel_id)
        return {"success": True}

    # Route message to gateway
    if message.content:
        gateway.route_message(message)
        logger.info("dingtalk_message_routed", message_id=message.message_id)

    return {"success": True}


@router.post("/send", response_model=DingTalkSendResponse)
async def send_dingtalk_message(
    request: DingTalkSendRequest, channel_id: str = "dingtalk"
) -> DingTalkSendResponse:
    """Send a message to DingTalk."""
    gateway = get_gateway()
    adapter = gateway.get_adapter(channel_id)

    if not adapter:
        stored = _dingtalk_configs.get(channel_id)
        if not stored:
            return DingTalkSendResponse(
                success=False,
                error="DingTalk channel not configured",
            )

        dingtalk_config = DingTalkConfig(**stored)
        adapter = DingTalkAdapter(config=dingtalk_config, channel_id=channel_id)

    outbound = OutboundMessage(
        channel_id=channel_id,
        content=request.content,
        recipient_id=request.recipient_id,
        message_type=MessageType(request.message_type),
    )

    success = await adapter.send(outbound)

    if success:
        return DingTalkSendResponse(success=True, message_id=outbound.recipient_id)
    else:
        return DingTalkSendResponse(success=False, error="Failed to send message")


@router.get("/adapters")
async def list_dingtalk_adapters() -> dict[str, Any]:
    """List all registered DingTalk adapters."""
    gateway = get_gateway()
    adapters = gateway.list_adapters()

    dingtalk_adapters = [a for a in adapters if a["channel_type"] == "dingtalk"]

    return {
        "adapters": dingtalk_adapters,
        "count": len(dingtalk_adapters),
    }
