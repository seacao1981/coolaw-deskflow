"""DingTalk (钉钉) channel adapter for IM integration.

Provides:
- DingTalk message parsing (text, markdown, link)
- DingTalk message sending (text, markdown, link, action card)
- Callback signature verification (HmacSHA256)
- Health check for DingTalk connection
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx

from deskflow.channels.gateway import (
    BaseMessage,
    ChannelAdapter,
    MessageType,
    OutboundMessage,
)
from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DingTalkMessage(BaseMessage):
    """DingTalk-specific message with additional fields."""

    _channel_id: str = "dingtalk"
    _content: str = ""
    _sender_id: str = ""
    _message_id: str = field(default_factory=lambda: "")
    _message_type: MessageType = MessageType.TEXT
    _timestamp: datetime = field(default_factory=datetime.now)
    _metadata: dict[str, Any] = field(default_factory=dict)

    # DingTalk-specific fields
    msg_id: str = ""  # DingTalk message ID
    conversation_id: str = ""  # Conversation ID
    sender_staff_id: str = ""  # Sender staff ID

    def __post_init__(self):
        if not self._message_id:
            self._message_id = self.msg_id or f"dingtalk_{int(time.time())}"


@dataclass
class DingTalkConfig:
    """DingTalk configuration."""

    app_key: str = ""
    app_secret: str = ""
    access_token: str = ""
    webhook_url: str = ""
    agent_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "access_token": self.access_token,
            "webhook_url": self.webhook_url,
            "agent_id": self.agent_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DingTalkConfig:
        """Create config from dictionary."""
        return cls(
            app_key=data.get("app_key", ""),
            app_secret=data.get("app_secret", ""),
            access_token=data.get("access_token", ""),
            webhook_url=data.get("webhook_url", ""),
            agent_id=data.get("agent_id", ""),
        )


class DingTalkAdapter(ChannelAdapter):
    """DingTalk channel adapter."""

    def __init__(
        self,
        config: DingTalkConfig | None = None,
        channel_id: str = "dingtalk",
    ):
        super().__init__(channel_id=channel_id, config=config.to_dict() if config else {})
        self._config = config or DingTalkConfig()
        self._client = httpx.AsyncClient(timeout=30.0)
        self._access_token: str | None = None
        self._token_expire_at: int = 0

    @property
    def channel_type(self) -> str:
        return "dingtalk"

    def to_dict(self) -> dict[str, Any]:
        """Convert adapter config to dictionary."""
        return self._config.to_dict()

    @staticmethod
    def from_dict(data: dict[str, Any]) -> DingTalkAdapter:
        """Create adapter from dictionary."""
        config = DingTalkConfig.from_dict(data)
        return DingTalkAdapter(config=config, channel_id=data.get("channel_id", "dingtalk"))

    def _calc_signature(self, timestamp: str) -> str:
        """Calculate DingTalk callback signature using HmacSHA256.

        Args:
            timestamp: Current timestamp in milliseconds

        Returns:
            URL-encoded signature string
        """
        if not self._config.app_secret:
            return ""

        # Calculate HMAC-SHA256
        secret_bytes = self._config.app_secret.encode("utf-8")
        timestamp_bytes = timestamp.encode("utf-8")

        mac = hmac.new(secret_bytes, timestamp_bytes, hashlib.sha256)
        signature = base64.b64encode(mac.digest()).decode("utf-8")

        # URL encode
        encoded = quote(signature, safe="")
        return encoded

    def _verify_signature(
        self,
        timestamp: str,
        signature: str,
    ) -> bool:
        """Verify DingTalk callback signature.

        Args:
            timestamp: Timestamp from request
            signature: Signature from request

        Returns:
            True if signature is valid, False otherwise
        """
        if not self._config.app_secret:
            logger.warning("dingtalk_app_secret_not_configured")
            return True

        # Calculate expected signature
        expected_signature = self._calc_signature(timestamp)

        # Compare signatures
        if signature != expected_signature:
            logger.error("dingtalk_signature_mismatch", received=signature, expected=expected_signature)
            return False

        return True

    def _parse_dingtalk_message_type(self, msg_type: str) -> MessageType:
        """Parse DingTalk message type to MessageType."""
        type_mapping = {
            "text": MessageType.TEXT,
            "markdown": MessageType.TEXT,
            "link": MessageType.LINK,
            "action_card": MessageType.TEXT,
            "oa": MessageType.LINK,
            "file": MessageType.FILE,
            "image": MessageType.IMAGE,
            "voice": MessageType.VOICE,
            "video": MessageType.VIDEO,
            "work": MessageType.TEXT,
        }
        return type_mapping.get(msg_type, MessageType.TEXT)

    async def parse_message(self, raw_data: dict[str, Any]) -> DingTalkMessage:
        """Parse DingTalk callback data into DingTalkMessage.

        Args:
            raw_data: Raw callback data from DingTalk

        Returns:
            Parsed DingTalkMessage instance
        """
        # Check if this is a verification request
        if raw_data.get("test"):
            logger.info("dingtalk_verification_request_received")
            return DingTalkMessage(
                _content="verification",
                _sender_id="dingtalk_system",
                _metadata={"test": True, "raw_data": raw_data},
            )

        # Parse message data
        msg_type = raw_data.get("msgtype", "text")
        conversation_id = raw_data.get("conversationId", "")
        sender_id = raw_data.get("senderId", "")
        sender_nick = raw_data.get("senderNick", "")
        msg_id = raw_data.get("msgId", "")
        timestamp = raw_data.get("timestamp", "")

        # Verify signature if provided
        signature = raw_data.get("signature")
        if signature:
            if not self._verify_signature(timestamp, signature):
                raise ValueError("DingTalk signature verification failed")

        # Extract content based on message type
        content = ""
        if msg_type == "text":
            text_content = raw_data.get("text", {})
            if isinstance(text_content, dict):
                content = text_content.get("content", "")
            else:
                content = str(text_content)
        elif msg_type == "markdown":
            markdown_content = raw_data.get("markdown", {})
            if isinstance(markdown_content, dict):
                content = markdown_content.get("text", "")
            else:
                content = str(markdown_content)
        elif msg_type == "link":
            link_content = raw_data.get("link", {})
            content = link_content.get("title", "") + ": " + link_content.get("text", "")
        else:
            # For other types, try to extract any available content
            content = raw_data.get("content", raw_data.get("text", ""))
            if isinstance(content, dict):
                content = content.get("content", "")

        # Build metadata
        metadata = {
            "raw_data": raw_data,
            "message_type": msg_type,
            "conversation_id": conversation_id,
            "sender_nick": sender_nick,
            "timestamp": timestamp,
        }

        return DingTalkMessage(
            _channel_id="dingtalk",
            _content=content,
            _sender_id=sender_id,
            _message_type=self._parse_dingtalk_message_type(msg_type),
            _metadata=metadata,
            msg_id=msg_id,
            conversation_id=conversation_id,
        )

    async def _get_access_token(self) -> str:
        """Get DingTalk access token with caching.

        Returns:
            Access token string
        """
        current_time = int(time.time())

        # Return cached token if still valid
        if self._access_token and current_time < self._token_expire_at:
            return self._access_token

        # Request new token
        url = "https://oapi.dingtalk.com/gettoken"
        params = {
            "appkey": self._config.app_key,
            "appsecret": self._config.app_secret,
        }

        async with self._client as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if data.get("errcode") != 0:
            raise ValueError(f"Failed to get access token: {data}")

        self._access_token = data["access_token"]
        # Token expires in 7200 seconds, refresh 600 seconds early
        self._token_expire_at = current_time + data.get("expires_in", 7200) - 600

        logger.info("dingtalk_access_token_refreshed", expire_in=data.get("expires_in", 7200))
        return self._access_token

    async def send(self, message: OutboundMessage) -> bool:
        """Send a message to DingTalk.

        Args:
            message: OutboundMessage to send

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Use webhook if configured, otherwise use API
            if self._config.webhook_url:
                return await self._send_by_webhook(message)
            else:
                return await self._send_by_api(message)

        except Exception as e:
            logger.error("dingtalk_message_send_error", error=str(e))
            return False

    async def _send_by_webhook(self, message: OutboundMessage) -> bool:
        """Send message via webhook (simpler, for group chat).

        Args:
            message: OutboundMessage to send

        Returns:
            True if sent successfully
        """
        # Build message content based on type
        if message.message_type == MessageType.TEXT:
            payload = {
                "msgtype": "text",
                "text": {"content": message.content},
            }
        elif "\n" in message.content or "#" in message.content:
            # Use markdown if content has newlines or markdown syntax
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": "消息通知",
                    "text": message.content,
                },
            }
        else:
            # Default to text
            payload = {
                "msgtype": "text",
                "text": {"content": message.content},
            }

        async with self._client as client:
            response = await client.post(self._config.webhook_url, json=payload)
            response.raise_for_status()
            result = response.json()

        success = result.get("errcode", 1) == 0
        if success:
            logger.info("dingtalk_webhook_message_sent", recipient=message.recipient_id)
        else:
            logger.error(
                "dingtalk_webhook_send_failed",
                errcode=result.get("errcode"),
                errmsg=result.get("errmsg"),
            )

        return success

    async def _send_by_api(self, message: OutboundMessage) -> bool:
        """Send message via API (more features, requires access token).

        Args:
            message: OutboundMessage to send

        Returns:
            True if sent successfully
        """
        # Get access token
        token = await self._get_access_token()

        # Build request
        url = "https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2"
        params = {"access_token": token}
        headers = {"Content-Type": "application/json"}

        # Build message content based on type
        if message.message_type == MessageType.TEXT:
            msg_content = {
                "msgtype": "text",
                "text": {"content": message.content},
            }
        elif "\n" in message.content or "#" in message.content:
            msg_content = {
                "msgtype": "markdown",
                "markdown": {
                    "title": "消息通知",
                    "text": message.content,
                },
            }
        else:
            msg_content = {
                "msgtype": "text",
                "text": {"content": message.content},
            }

        # Build request body
        body = {
            "agent_id": int(self._config.agent_id) if self._config.agent_id else None,
            "user_ids": message.recipient_id,
            "msg": msg_content,
        }

        # Remove None values
        body = {k: v for k, v in body.items() if v is not None}

        async with self._client as client:
            response = await client.post(url, params=params, headers=headers, json=body)
            response.raise_for_status()
            result = response.json()

        success = result.get("errcode") == 0
        if success:
            logger.info(
                "dingtalk_api_message_sent",
                recipient=message.recipient_id,
                type=msg_content.get("msgtype"),
            )
        else:
            logger.error(
                "dingtalk_api_message_send_failed",
                errcode=result.get("errcode"),
                errmsg=result.get("errmsg"),
            )

        return success

    async def health_check(self) -> bool:
        """Check DingTalk connection health.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # If using webhook, just check if URL is configured
            if self._config.webhook_url:
                # Send a test message
                test_msg = OutboundMessage(
                    channel_id=self.channel_id,
                    content="健康检查",
                    recipient_id="system",
                )
                return await self._send_by_webhook(test_msg)

            # If using API, try to get access token and check agent status
            if self._config.app_key and self._config.app_secret:
                token = await self._get_access_token()

                # Check agent status
                url = "https://oapi.dingtalk.com/topapi/agent/get"
                params = {"access_token": token, "agent_id": self._config.agent_id}

                async with self._client as client:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    result = response.json()

                healthy = result.get("errcode") == 0
                if not healthy:
                    logger.warning("dingtalk_health_check_failed", errcode=result.get("errcode"))

                return healthy

            logger.warning("dingtalk_health_check_no_config")
            return False

        except Exception as e:
            logger.error("dingtalk_health_check_error", error=str(e))
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
        logger.info("dingtalk_adapter_closed")

    # Link message helper
    async def send_link(
        self,
        recipient_id: str,
        title: str,
        text: str,
        message_url: str,
        pic_url: str = "",
    ) -> bool:
        """Send a link message.

        Args:
            recipient_id: Recipient's user ID
            title: Link title
            text: Link description
            message_url: Click URL
            pic_url: Thumbnail image URL

        Returns:
            True if sent successfully
        """
        try:
            if self._config.webhook_url:
                payload = {
                    "msgtype": "link",
                    "link": {
                        "title": title,
                        "text": text,
                        "picUrl": pic_url,
                        "messageUrl": message_url,
                    },
                }

                async with self._client as client:
                    response = await client.post(self._config.webhook_url, json=payload)
                    response.raise_for_status()
                    result = response.json()

                success = result.get("errcode", 1) == 0
                if success:
                    logger.info("dingtalk_link_message_sent", recipient=recipient_id)

                return success
            else:
                # Use API method
                token = await self._get_access_token()
                url = "https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2"
                params = {"access_token": token}

                body = {
                    "agent_id": int(self._config.agent_id) if self._config.agent_id else None,
                    "user_ids": recipient_id,
                    "msg": {
                        "msgtype": "link",
                        "link": {
                            "title": title,
                            "text": text,
                            "picUrl": pic_url,
                            "messageUrl": message_url,
                        },
                    },
                }

                body = {k: v for k, v in body.items() if v is not None}

                async with self._client as client:
                    response = await client.post(url, params=params, json=body)
                    response.raise_for_status()
                    result = response.json()

                success = result.get("errcode") == 0
                if success:
                    logger.info("dingtalk_link_message_sent", recipient=recipient_id)

                return success

        except Exception as e:
            logger.error("dingtalk_link_message_send_error", error=str(e))
            return False

    # Action card helper
    async def send_action_card(
        self,
        recipient_id: str,
        title: str,
        content: str,
        btn_title: str,
        btn_url: str,
        btn_orientation: str = "0",
    ) -> bool:
        """Send an action card message (single button).

        Args:
            recipient_id: Recipient's user ID
            title: Card title
            content: Card content
            btn_title: Button title
            btn_url: Button URL
            btn_orientation: Button orientation (0: horizontal, 1: vertical)

        Returns:
            True if sent successfully
        """
        try:
            if self._config.webhook_url:
                payload = {
                    "msgtype": "actionCard",
                    "actionCard": {
                        "title": title,
                        "markdown": content,
                        "singleTitle": btn_title,
                        "singleURL": btn_url,
                        "btnOrientation": btn_orientation,
                    },
                }

                async with self._client as client:
                    response = await client.post(self._config.webhook_url, json=payload)
                    response.raise_for_status()
                    result = response.json()

                success = result.get("errcode", 1) == 0
                if success:
                    logger.info("dingtalk_action_card_sent", recipient=recipient_id)

                return success

        except Exception as e:
            logger.error("dingtalk_action_card_send_error", error=str(e))
            return False

        return False
