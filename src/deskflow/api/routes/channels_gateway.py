"""Channels management API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/channels", tags=["channels"])


def _get_state() -> Any:
    """Get app state at runtime."""
    from deskflow.app import get_app_state
    return get_app_state()


@router.get("/list")
async def list_channels():
    """List all registered channel adapters."""
    try:
        from deskflow.channels import get_gateway

        gateway = get_gateway()
        adapters = gateway.list_adapters()

        return {
            "success": True,
            "channels": adapters,
            "total": len(adapters),
            "pending_messages": gateway.pending_messages,
        }

    except Exception as e:
        logger.error("list_channels_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
async def start_channels(num_workers: int = 3):
    """Start the message gateway.

    Args:
        num_workers: Number of worker threads for message processing
    """
    try:
        from deskflow.channels import start_gateway

        gateway = await start_gateway(num_workers)

        return {
            "success": True,
            "message": "Message gateway started",
            "workers": num_workers,
            "adapter_count": gateway.adapter_count,
        }

    except Exception as e:
        logger.error("start_gateway_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_channels():
    """Stop the message gateway."""
    try:
        from deskflow.channels import stop_gateway

        await stop_gateway()

        return {
            "success": True,
            "message": "Message gateway stopped",
        }

    except Exception as e:
        logger.error("stop_gateway_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_channel_status():
    """Get message gateway status."""
    try:
        from deskflow.channels import get_gateway

        gateway = get_gateway()

        return {
            "success": True,
            "status": {
                "running": gateway._running,
                "adapter_count": gateway.adapter_count,
                "pending_messages": gateway.pending_messages,
            },
        }

    except Exception as e:
        logger.error("get_channel_status_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/health")
async def check_channel_health():
    """Check health of all channel adapters."""
    try:
        from deskflow.channels import get_gateway

        gateway = get_gateway()
        health_results = await gateway.health_check()

        all_healthy = all(health_results.values()) if health_results else False

        return {
            "success": True,
            "healthy": all_healthy,
            "channels": health_results,
        }

    except Exception as e:
        logger.error("check_channel_health_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/broadcast")
async def broadcast_message(request: dict):
    """Broadcast a message to multiple channels.

    Request body:
    - content: Message content
    - recipient_id: Target recipient
    - channels: Optional list of channel IDs (broadcasts to all if not specified)
    - message_type: Optional message type (default: text)
    """
    try:
        from deskflow.channels import get_gateway
        from deskflow.channels.gateway import OutboundMessage, MessageType

        content = request.get("content", "")
        recipient_id = request.get("recipient_id", "")
        channel_ids = request.get("channels")
        message_type_str = request.get("message_type", "text")

        if not content:
            raise HTTPException(status_code=400, detail="content is required")
        if not recipient_id:
            raise HTTPException(status_code=400, detail="recipient_id is required")

        # Parse message type
        try:
            message_type = MessageType(message_type_str)
        except ValueError:
            message_type = MessageType.TEXT

        msg = OutboundMessage(
            channel_id="broadcast",
            content=content,
            recipient_id=recipient_id,
            message_type=message_type,
        )

        gateway = get_gateway()
        results = await gateway.broadcast(msg, channel_ids)

        success_count = sum(1 for v in results.values() if v)

        return {
            "success": True,
            "results": results,
            "success_count": success_count,
            "total_count": len(results),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("broadcast_message_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supported")
async def get_supported_channels():
    """Get list of supported channel types."""
    # Return available channel adapter types
    supported = [
        {
            "type": "feishu",
            "name": "飞书",
            "description": "飞书开放平台",
        },
        {
            "type": "wework",
            "name": "企业微信",
            "description": "企业微信开放平台",
        },
        {
            "type": "dingtalk",
            "name": "钉钉",
            "description": "钉钉开放平台",
        },
        {
            "type": "telegram",
            "name": "Telegram",
            "description": "Telegram Bot API",
        },
    ]

    return {
        "success": True,
        "channels": supported,
        "total": len(supported),
    }
