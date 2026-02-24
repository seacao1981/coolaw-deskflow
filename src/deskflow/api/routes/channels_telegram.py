"""Telegram Bot API channel routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any

from deskflow.channels import (
    TelegramAdapter,
    TelegramConfig,
    get_gateway,
)
from deskflow.channels.gateway import OutboundMessage
from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


class TelegramConfigRequest(BaseModel):
    """Telegram configuration request."""

    bot_token: str = Field("", description="Telegram Bot Token")
    webhook_url: str = Field("", description="Webhook URL")
    use_webhook: bool = Field(False, description="Use webhook mode")
    allowed_updates: list[str] = Field(
        default_factory=lambda: ["message", "callback_query"],
        description="Allowed update types",
    )
    secret_token: str = Field("", description="Secret token for webhook verification")


class TelegramConfigResponse(BaseModel):
    """Telegram configuration response."""

    bot_token: str = Field("", description="Masked bot token")
    webhook_url: str = Field("", description="Webhook URL")
    use_webhook: bool = Field(False, description="Use webhook mode")
    allowed_updates: list[str] = Field(default_factory=list, description="Allowed update types")
    enabled: bool = Field(False, description="Channel enabled status")


class TelegramSendRequest(BaseModel):
    """Telegram send message request."""

    chat_id: str = Field(..., description="Target chat ID")
    content: str = Field(..., description="Message content")
    message_type: str = Field("text", description="Message type: text, photo, document")


class TelegramTestResponse(BaseModel):
    """Telegram test connection response."""

    success: bool
    bot_username: str | None = None
    message: str = ""


@router.get("/config", response_model=TelegramConfigResponse)
async def get_config() -> TelegramConfigResponse:
    """Get Telegram configuration."""
    try:
        gateway = get_gateway()
        adapter = gateway.get_adapter("telegram")

        if not adapter:
            return TelegramConfigResponse(enabled=False)

        config = adapter.to_dict()
        return TelegramConfigResponse(
            bot_token=config.get("bot_token", ""),
            webhook_url=config.get("webhook_url", ""),
            use_webhook=config.get("use_webhook", False),
            allowed_updates=config.get("allowed_updates", []),
            enabled=adapter.enabled,
        )
    except Exception as e:
        logger.error("telegram_get_config_error", error=str(e))
        return TelegramConfigResponse(enabled=False)


@router.post("/config")
async def save_config(request: TelegramConfigRequest) -> dict[str, Any]:
    """Save Telegram configuration."""
    try:
        gateway = get_gateway()

        config = TelegramConfig(
            bot_token=request.bot_token,
            webhook_url=request.webhook_url,
            use_webhook=request.use_webhook,
            allowed_updates=request.allowed_updates,
            secret_token=request.secret_token,
        )

        adapter = TelegramAdapter(config=config)

        # Register adapter
        gateway.register_adapter(adapter)

        # Set webhook if enabled
        if request.use_webhook and request.webhook_url:
            await adapter.set_webhook(request.webhook_url)

        logger.info(
            "telegram_config_saved",
            use_webhook=request.use_webhook,
            webhook_url=request.webhook_url,
        )

        return {"success": True, "message": "Telegram configuration saved"}

    except Exception as e:
        logger.error("telegram_save_config_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/config")
async def delete_config() -> dict[str, Any]:
    """Delete Telegram configuration."""
    try:
        gateway = get_gateway()

        # Delete webhook before removing config
        adapter = gateway.get_adapter("telegram")
        if adapter and isinstance(adapter, TelegramAdapter):
            await adapter.set_webhook(None)

        # Unregister adapter
        gateway.unregister_adapter("telegram")

        logger.info("telegram_config_deleted")
        return {"success": True, "message": "Telegram configuration deleted"}

    except Exception as e:
        logger.error("telegram_delete_config_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/toggle")
async def toggle_channel(enable: bool = True) -> dict[str, Any]:
    """Toggle Telegram channel."""
    try:
        gateway = get_gateway()
        adapter = gateway.get_adapter("telegram")

        if not adapter:
            raise HTTPException(status_code=404, detail="Telegram adapter not found")

        if enable:
            adapter.enable()
            logger.info("telegram_channel_enabled")
        else:
            adapter.disable()
            logger.info("telegram_channel_disabled")

        return {"success": True, "enabled": enable}

    except Exception as e:
        logger.error("telegram_toggle_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test", response_model=TelegramTestResponse)
async def test_connection() -> TelegramTestResponse:
    """Test Telegram connection."""
    try:
        gateway = get_gateway()
        adapter = gateway.get_adapter("telegram")

        if not adapter:
            return TelegramTestResponse(
                success=False,
                message="Telegram adapter not configured",
            )

        if not isinstance(adapter, TelegramAdapter):
            return TelegramTestResponse(
                success=False,
                message="Invalid adapter type",
            )

        # Test connection
        healthy = await adapter.health_check()

        if healthy:
            bot_info = await adapter.get_me()
            bot_username = bot_info.get("username") if bot_info else None

            return TelegramTestResponse(
                success=True,
                bot_username=bot_username,
                message=f"Connected to bot: @{bot_username}" if bot_username else "Connection successful",
            )
        else:
            return TelegramTestResponse(
                success=False,
                message="Health check failed",
            )

    except Exception as e:
        logger.error("telegram_test_connection_error", error=str(e))
        return TelegramTestResponse(
            success=False,
            message=f"Connection test failed: {str(e)}",
        )


@router.post("/callback")
async def handle_callback(request: dict[str, Any]) -> dict[str, Any]:
    """Handle Telegram webhook callback.

    This endpoint receives updates from Telegram when using webhook mode.
    """
    try:
        gateway = get_gateway()
        adapter = gateway.get_adapter("telegram")

        if not adapter or not isinstance(adapter, TelegramAdapter):
            logger.warning("telegram_callback_adapter_not_found")
            return {"ok": False, "error": "Adapter not configured"}

        # Parse message
        msg = await adapter.parse_message(request)

        if msg.content:
            # Route message to gateway
            await gateway.route_message(msg)
            logger.info(
                "telegram_callback_processed",
                chat_id=msg.chat_id,
                sender_id=msg.sender_id,
            )

        return {"ok": True}

    except Exception as e:
        logger.error("telegram_callback_error", error=str(e))
        return {"ok": False, "error": str(e)}


@router.post("/send")
async def send_message(request: TelegramSendRequest) -> dict[str, Any]:
    """Send a message to Telegram."""
    try:
        gateway = get_gateway()
        adapter = gateway.get_adapter("telegram")

        if not adapter or not isinstance(adapter, TelegramAdapter):
            raise HTTPException(status_code=404, detail="Telegram adapter not found")

        if not adapter.enabled:
            raise HTTPException(status_code=400, detail="Telegram channel is disabled")

        # Map message type
        from deskflow.channels.gateway import MessageType

        type_mapping = {
            "text": MessageType.TEXT,
            "photo": MessageType.IMAGE,
            "document": MessageType.FILE,
            "image": MessageType.IMAGE,
            "file": MessageType.FILE,
        }
        message_type = type_mapping.get(request.message_type.lower(), MessageType.TEXT)

        # Create outbound message
        outbound_msg = OutboundMessage(
            channel_id="telegram",
            content=request.content,
            recipient_id=request.chat_id,
            message_type=message_type,
        )

        # Send message
        success = await adapter.send(outbound_msg)

        if success:
            logger.info("telegram_api_message_sent", chat_id=request.chat_id)
            return {"success": True, "message": "Message sent"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send message")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("telegram_send_message_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/adapters")
async def list_adapters() -> dict[str, Any]:
    """List registered Telegram adapters."""
    try:
        gateway = get_gateway()
        adapter = gateway.get_adapter("telegram")

        if not adapter:
            return {"adapters": []}

        return {
            "adapters": [
                {
                    "channel_id": adapter.channel_id,
                    "channel_type": adapter.channel_type,
                    "enabled": adapter.enabled,
                }
            ]
        }

    except Exception as e:
        logger.error("telegram_list_adapters_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
