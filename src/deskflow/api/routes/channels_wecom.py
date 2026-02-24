"""WeCom (Enterprise WeChat) channel API routes."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from deskflow.channels.wework import WeComAdapter, WeComConfig, WeComMessage
from deskflow.channels.gateway import get_gateway, OutboundMessage, MessageType
from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/wecom", tags=["wecom"])


class WeComConfigRequest(BaseModel):
    """Request model for WeCom configuration."""

    corp_id: str = ""
    agent_id: str = ""
    secret: str = ""
    token: str = ""
    encoding_aes_key: str = ""
    webhook_url: str = ""


class WeComConfigResponse(BaseModel):
    """Response model for WeCom configuration."""

    channel_id: str
    channel_type: str = "wecom"
    enabled: bool
    configured: bool
    corp_id: str
    agent_id: str
    webhook_url: str


class WeComSendRequest(BaseModel):
    """Request model for sending WeCom message."""

    recipient_id: str
    content: str
    message_type: str = "text"


class WeComSendResponse(BaseModel):
    """Response model for send result."""

    success: bool
    message_id: str | None = None
    error: str | None = None


# In-memory config storage
_wecom_configs: dict[str, dict[str, Any]] = {}


@router.get("/config", response_model=WeComConfigResponse)
async def get_wecom_config(channel_id: str = "wecom") -> WeComConfigResponse:
    """Get WeCom channel configuration."""
    gateway = get_gateway()
    adapter = gateway.get_adapter(channel_id)

    if adapter:
        config_data = adapter.to_dict()
        return WeComConfigResponse(
            channel_id=channel_id,
            enabled=adapter.enabled,
            configured=bool(config_data.get("corp_id") and config_data.get("secret")),
            corp_id=config_data.get("corp_id", ""),
            agent_id=config_data.get("agent_id", ""),
            webhook_url=config_data.get("webhook_url", ""),
        )
    else:
        stored = _wecom_configs.get(channel_id, {})
        return WeComConfigResponse(
            channel_id=channel_id,
            enabled=False,
            configured=bool(stored.get("corp_id") and stored.get("secret")),
            corp_id=stored.get("corp_id", ""),
            agent_id=stored.get("agent_id", ""),
            webhook_url=stored.get("webhook_url", ""),
        )


@router.post("/config")
async def save_wecom_config(config: WeComConfigRequest, channel_id: str = "wecom") -> dict[str, Any]:
    """Save WeCom channel configuration."""
    _wecom_configs[channel_id] = {
        "corp_id": config.corp_id,
        "agent_id": config.agent_id,
        "secret": config.secret,
        "token": config.token,
        "encoding_aes_key": config.encoding_aes_key,
        "webhook_url": config.webhook_url,
        "channel_id": channel_id,
    }

    # Create and register adapter
    gateway = get_gateway()
    wecom_config = WeComConfig(
        corp_id=config.corp_id,
        agent_id=config.agent_id,
        secret=config.secret,
        token=config.token,
        encoding_aes_key=config.encoding_aes_key,
        webhook_url=config.webhook_url,
    )

    adapter = WeComAdapter(config=wecom_config, channel_id=channel_id)

    # Unregister existing if present
    existing = gateway.get_adapter(channel_id)
    if existing:
        gateway.unregister_adapter(channel_id)

    gateway.register_adapter(adapter)

    logger.info("wecom_config_saved", channel_id=channel_id)

    return {
        "success": True,
        "message": "WeCom configuration saved",
        "channel_id": channel_id,
    }


@router.delete("/config")
async def delete_wecom_config(channel_id: str = "wecom") -> dict[str, Any]:
    """Delete WeCom channel configuration."""
    if channel_id in _wecom_configs:
        del _wecom_configs[channel_id]

    gateway = get_gateway()
    existing = gateway.get_adapter(channel_id)
    if existing:
        gateway.unregister_adapter(channel_id)

    logger.info("wecom_config_deleted", channel_id=channel_id)

    return {
        "success": True,
        "message": "WeCom configuration deleted",
        "channel_id": channel_id,
    }


@router.post("/toggle")
async def toggle_wecom_channel(enable: bool, channel_id: str = "wecom") -> dict[str, Any]:
    """Enable or disable WeCom channel."""
    gateway = get_gateway()
    adapter = gateway.get_adapter(channel_id)

    if not adapter:
        stored = _wecom_configs.get(channel_id)
        if not stored:
            raise HTTPException(status_code=404, detail="WeCom channel not configured")

        wecom_config = WeComConfig(**stored)
        adapter = WeComAdapter(config=wecom_config, channel_id=channel_id)
        gateway.register_adapter(adapter)

    if enable:
        adapter.enable()
        logger.info("wecom_channel_enabled", channel_id=channel_id)
    else:
        adapter.disable()
        logger.info("wecom_channel_disabled", channel_id=channel_id)

    return {
        "success": True,
        "enabled": enable,
        "channel_id": channel_id,
    }


@router.post("/test")
async def test_wecom_connection(channel_id: str = "wecom") -> dict[str, Any]:
    """Test WeCom channel connection."""
    gateway = get_gateway()
    adapter = gateway.get_adapter(channel_id)

    if not adapter:
        stored = _wecom_configs.get(channel_id)
        if not stored:
            raise HTTPException(status_code=404, detail="WeCom channel not configured")

        wecom_config = WeComConfig(**stored)
        adapter = WeComAdapter(config=wecom_config, channel_id=channel_id)

    healthy = await adapter.health_check()

    return {
        "success": healthy,
        "healthy": healthy,
        "channel_id": channel_id,
        "channel_type": "wecom",
    }


@router.get("/callback")
async def wecom_callback_get(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
    channel_id: str = "wecom",
) -> str:
    """Handle WeCom URL verification callback (GET).

    WeCom sends this to verify the callback URL.
    """
    gateway = get_gateway()
    adapter = gateway.get_adapter(channel_id)

    if not adapter:
        stored = _wecom_configs.get(channel_id)
        if stored:
            wecom_config = WeComConfig(**stored)
            adapter = WeComAdapter(config=wecom_config, channel_id=channel_id)
        else:
            adapter = WeComAdapter(channel_id=channel_id)

    result = adapter._verify_signature(msg_signature, timestamp, nonce, echostr)

    if result is False:
        raise HTTPException(status_code=400, detail="Signature verification failed")

    logger.info("wecom_callback_verified", channel_id=channel_id)
    return str(result)


@router.post("/callback")
async def wecom_callback_post(
    request: Request,
    msg_signature: str = Query(None),
    timestamp: str = Query(None),
    nonce: str = Query(None),
    channel_id: str = "wecom",
) -> dict[str, Any]:
    """Handle WeCom message callback (POST)."""
    body = await request.body()

    # Parse based on content type
    content_type = request.headers.get("content-type", "")
    if "xml" in content_type.lower():
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(body)
            data = {child.tag: child.text or "" for child in root}
        except ET.ParseError:
            data = {}
    else:
        data = await request.json() if body else {}

    # Add query params to data
    if msg_signature:
        data["msg_signature"] = msg_signature
        data["timestamp"] = timestamp
        data["nonce"] = nonce

    logger.info("wecom_callback_received", channel_id=channel_id, msg_type=data.get("MsgType"))

    # Get or create adapter
    gateway = get_gateway()
    adapter = gateway.get_adapter(channel_id)

    if not adapter:
        stored = _wecom_configs.get(channel_id)
        if stored:
            wecom_config = WeComConfig(**stored)
            adapter = WeComAdapter(config=wecom_config, channel_id=channel_id)
        else:
            adapter = WeComAdapter(channel_id=channel_id)

    # Parse message
    try:
        message = await adapter.parse_message(data)
    except Exception as e:
        logger.error("wecom_message_parse_error", error=str(e))

        # Return error for encrypted messages
        if data.get("Encrypt"):
            return {"error": str(e)}
        raise HTTPException(status_code=400, detail=f"Failed to parse message: {e}")

    # Handle echo verification
    if message.metadata.get("echo_verification"):
        # Already handled in GET
        return {"message": "ok"}

    # Route message to gateway
    if message.content and not message.metadata.get("echo_verification"):
        gateway.route_message(message)
        logger.info("wecom_message_routed", message_id=message.message_id)

    return {"message": "ok"}


@router.post("/send", response_model=WeComSendResponse)
async def send_wecom_message(request: WeComSendRequest, channel_id: str = "wecom") -> WeComSendResponse:
    """Send a message to WeCom."""
    gateway = get_gateway()
    adapter = gateway.get_adapter(channel_id)

    if not adapter:
        stored = _wecom_configs.get(channel_id)
        if not stored:
            return WeComSendResponse(
                success=False,
                error="WeCom channel not configured",
            )

        wecom_config = WeComConfig(**stored)
        adapter = WeComAdapter(config=wecom_config, channel_id=channel_id)

    outbound = OutboundMessage(
        channel_id=channel_id,
        content=request.content,
        recipient_id=request.recipient_id,
        message_type=MessageType(request.message_type),
    )

    success = await adapter.send(outbound)

    if success:
        return WeComSendResponse(success=True, message_id=outbound.recipient_id)
    else:
        return WeComSendResponse(success=False, error="Failed to send message")


@router.get("/adapters")
async def list_wecom_adapters() -> dict[str, Any]:
    """List all registered WeCom adapters."""
    gateway = get_gateway()
    adapters = gateway.list_adapters()

    wecom_adapters = [a for a in adapters if a["channel_type"] == "wecom"]

    return {
        "adapters": wecom_adapters,
        "count": len(wecom_adapters),
    }
