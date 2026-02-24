"""Feishu (Lark) channel adapter for IM integration.

Provides:
- Feishu message parsing (text, rich text, images)
- Feishu message sending (text, rich text)
- Webhook signature verification
- Health check for Feishu connection
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

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
class FeishuMessage(BaseMessage):
    """Feishu-specific message with additional fields."""

    _channel_id: str = "feishu"
    _content: str = ""
    _sender_id: str = ""
    _message_id: str = field(default_factory=lambda: "")
    _message_type: MessageType = MessageType.TEXT
    _timestamp: datetime = field(default_factory=datetime.now)
    _metadata: dict[str, Any] = field(default_factory=dict)

    # Feishu-specific fields
    open_message_id: str = ""  # Feishu message ID
    chat_type: str = "private"  # 'private' or 'group'
    tenant_key: str = ""  # Feishu tenant key

    def __post_init__(self):
        if not self._message_id:
            self._message_id = self.open_message_id or f"feishu_{int(time.time())}"


@dataclass
class FeishuConfig:
    """Feishu configuration."""

    app_id: str = ""
    app_secret: str = ""
    verification_token: str = ""
    encrypt_key: str = ""
    bot_name: str = ""
    webhook_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
            "verification_token": self.verification_token,
            "encrypt_key": self.encrypt_key,
            "bot_name": self.bot_name,
            "webhook_url": self.webhook_url,
        }


class FeishuAdapter(ChannelAdapter):
    """Feishu channel adapter."""

    def __init__(
        self,
        config: FeishuConfig | None = None,
        channel_id: str = "feishu",
    ):
        super().__init__(channel_id=channel_id, config=config.to_dict() if config else {})
        self._config = config or FeishuConfig()
        self._client = httpx.AsyncClient(timeout=30.0)
        self._access_token: str | None = None
        self._token_expire_at: int = 0

    @property
    def channel_type(self) -> str:
        return "feishu"

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary (for serialization)."""
        return {
            "app_id": self._config.app_id,
            "app_secret": self._config.app_secret,
            "verification_token": self._config.verification_token,
            "encrypt_key": self._config.encrypt_key,
            "bot_name": self._config.bot_name,
            "webhook_url": self._config.webhook_url,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> FeishuAdapter:
        """Create adapter from dictionary."""
        config = FeishuConfig(
            app_id=data.get("app_id", ""),
            app_secret=data.get("app_secret", ""),
            verification_token=data.get("verification_token", ""),
            encrypt_key=data.get("encrypt_key", ""),
            bot_name=data.get("bot_name", ""),
            webhook_url=data.get("webhook_url", ""),
        )
        return FeishuAdapter(config=config, channel_id=data.get("channel_id", "feishu"))

    async def _get_access_token(self) -> str:
        """Get Feishu access token with caching."""
        current_time = int(time.time())

        # Return cached token if still valid
        if self._access_token and current_time < self._token_expire_at:
            return self._access_token

        # Request new token
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self._config.app_id,
            "app_secret": self._config.app_secret,
        }

        async with self._client as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        if data.get("code") != 0:
            raise ValueError(f"Failed to get access token: {data}")

        self._access_token = data["tenant_access_token"]
        self._token_expire_at = current_time + data.get("expire", 7200) - 600  # Refresh 10min early

        logger.info("feishu_access_token_refreshed", expire_in=data.get("expire", 7200))
        return self._access_token

    def _verify_signature(
        self,
        timestamp: str,
        nonce: str,
        signature: str,
        body: bytes,
    ) -> bool:
        """Verify Feishu webhook signature."""
        if not self._config.verification_token:
            logger.warning("feishu_verification_token_not_configured")
            return True  # Skip verification if token not configured

        # Build signature string
        timestamp_nonce = timestamp + nonce
        signature_str = self._config.verification_token + timestamp_nonce + self._config.verification_token

        # Calculate HMAC-SHA256
        calculated = hmac.new(
            signature_str.encode("utf-8"),
            body,
            hashlib.sha256,
        ).digest()

        # Compare signatures
        expected = base64.b64encode(calculated).decode("utf-8")
        return hmac.compare_digest(expected, signature)

    def _parse_feishu_message_type(self, msg_type: str) -> MessageType:
        """Parse Feishu message type to MessageType."""
        type_mapping = {
            "text": MessageType.TEXT,
            "post": MessageType.TEXT,  # Rich text
            "image": MessageType.IMAGE,
            "file": MessageType.FILE,
            "audio": MessageType.VOICE,
            "video": MessageType.VIDEO,
            "share_chat": MessageType.LINK,
            "share_user": MessageType.LINK,
        }
        return type_mapping.get(msg_type, MessageType.TEXT)

    async def parse_message(self, raw_data: dict[str, Any]) -> FeishuMessage:
        """Parse Feishu webhook data into FeishuMessage.

        Args:
            raw_data: Raw webhook data from Feishu

        Returns:
            Parsed FeishuMessage instance
        """
        # Handle URL verification challenge
        if "challenge" in raw_data:
            logger.info("feishu_url_verification_received")
            return FeishuMessage(
                _content=str(raw_data.get("challenge", "")),
                _sender_id="feishu_system",
                _metadata={"challenge": True},
            )

        # Parse message data
        header = raw_data.get("header", {})
        event = raw_data.get("event", {})
        message = event.get("message", {})

        # Extract message content based on type
        msg_type = message.get("message_type", "text")
        content_raw = message.get("content", "")

        # Parse content based on message type
        if msg_type == "text":
            content = content_raw
        elif msg_type == "post":
            # Parse rich text content
            content = self._parse_post_content(content_raw)
        else:
            content = content_raw

        return FeishuMessage(
            _channel_id="feishu",
            _content=content,
            _sender_id=event.get("sender", {}).get("sender_id", {}).get("open_id", "unknown"),
            _message_type=self._parse_feishu_message_type(msg_type),
            _timestamp=datetime.fromtimestamp(header.get("create_time", 0) / 1000),
            _metadata={
                "raw_data": raw_data,
                "message_type": msg_type,
                "event_type": header.get("event_type", ""),
            },
            open_message_id=message.get("message_id", ""),
            chat_type=message.get("chat_type", "private"),
            tenant_key=header.get("tenant_key", ""),
        )

    def _parse_post_content(self, content: str | dict) -> str:
        """Parse Feishu post (rich text) content to plain text."""
        if isinstance(content, str):
            import json
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                return content

        if not isinstance(content, dict):
            return str(content)

        # Extract text from post content
        content_obj = content.get("content", [])
        texts = []

        def extract_text(items):
            for item in items:
                if isinstance(item, dict):
                    tag = item.get("tag", "")
                    if tag == "text":
                        texts.append(item.get("text", ""))
                    elif tag == "a":
                        texts.append(item.get("text", ""))
                    elif tag == "at":
                        texts.append(f"@{item.get('user_name', 'user')}")
                    # Recursively extract from nested items
                    if "children" in item:
                        extract_text(item["children"])

        extract_text(content_obj)
        return "".join(texts)

    async def send(self, message: OutboundMessage) -> bool:
        """Send a message to Feishu.

        Args:
            message: OutboundMessage to send

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Get access token
            token = await self._get_access_token()

            # Build request
            url = "https://open.feishu.cn/open-apis/im/v1/messages"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Build message content based on type
            if message.message_type == MessageType.TEXT:
                content = {"text": message.content}
                msg_type = "text"
            elif message.message_type == MessageType.IMAGE:
                # Upload image first, then send
                image_key = await self._upload_image(message.content)
                content = {"image_key": image_key}
                msg_type = "image"
            else:
                # Default to text with mentions
                content = {"text": message.content}
                msg_type = "text"

            # Build request body
            body = {
                "receive_id": message.recipient_id,
                "msg_type": msg_type,
                "content": content,
            }

            # Add receive_id type if specified
            receive_id_type = message.metadata.get("receive_id_type", "open_id")
            params = {"receive_id_type": receive_id_type}

            async with self._client as client:
                response = await client.post(url, headers=headers, params=params, json=body)
                response.raise_for_status()
                result = response.json()

            success = result.get("code") == 0
            if success:
                logger.info(
                    "feishu_message_sent",
                    recipient=message.recipient_id,
                    type=msg_type,
                )
            else:
                logger.error(
                    "feishu_message_send_failed",
                    code=result.get("code"),
                    msg=result.get("msg"),
                )

            return success

        except Exception as e:
            logger.error("feishu_message_send_error", error=str(e))
            return False

    async def _upload_image(self, image_data: str) -> str:
        """Upload image to Feishu and return image_key.

        Args:
            image_data: Image URL or base64 data

        Returns:
            Feishu image_key
        """
        token = await self._get_access_token()
        url = "https://open.feishu.cn/open-apis/im/v1/images"
        headers = {"Authorization": f"Bearer {token}"}

        # Determine image source
        if image_data.startswith("http"):
            # Download from URL
            async with self._client as client:
                image_response = await client.get(image_data)
                image_bytes = image_response.content
        elif image_data.startswith("data:"):
            # Base64 data
            image_bytes = base64.b64decode(image_data.split(",")[1])
        else:
            # Local file path
            with open(image_data, "rb") as f:
                image_bytes = f.read()

        # Upload
        files = {"image": ("image.png", image_bytes)}
        data = {"image_type": "message"}

        async with self._client as client:
            response = await client.post(url, headers=headers, data=data, files=files)
            response.raise_for_status()
            result = response.json()

        if result.get("code") != 0:
            raise ValueError(f"Failed to upload image: {result}")

        return result["data"]["image_key"]

    async def health_check(self) -> bool:
        """Check Feishu connection health.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Try to get access token
            await self._get_access_token()

            # Try to get bot info
            token = await self._get_access_token()
            url = "https://open.feishu.cn/open-apis/auth/v3/app_info/v2"
            headers = {"Authorization": f"Bearer {token}"}

            async with self._client as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                result = response.json()

            healthy = result.get("code") == 0
            if healthy:
                logger.info("feishu_health_check_passed")
            else:
                logger.warning("feishu_health_check_failed", code=result.get("code"))

            return healthy

        except Exception as e:
            logger.error("feishu_health_check_error", error=str(e))
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
        logger.info("feishu_adapter_closed")

    # Rich text message helper
    async def send_rich_text(
        self,
        recipient_id: str,
        content: list[dict[str, Any]],
        receive_id_type: str = "open_id",
    ) -> bool:
        """Send a rich text (post) message.

        Args:
            recipient_id: Recipient's open_id or user_id
            content: Rich text content as list of elements
            receive_id_type: ID type ('open_id' or 'user_id')

        Returns:
            True if sent successfully
        """
        message = OutboundMessage(
            channel_id=self._channel_id,
            content="",  # Not used for rich text
            recipient_id=recipient_id,
            message_type=MessageType.TEXT,
            metadata={
                "rich_text_content": content,
                "receive_id_type": receive_id_type,
            },
        )

        # Override send logic for rich text
        token = await self._get_access_token()
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        post_content = {"content": content}
        body = {
            "receive_id": recipient_id,
            "msg_type": "post",
            "content": post_content,
        }

        params = {"receive_id_type": receive_id_type}

        async with self._client as client:
            response = await client.post(url, headers=headers, params=params, json=body)
            response.raise_for_status()
            result = response.json()

        success = result.get("code") == 0
        if success:
            logger.info("feishu_rich_text_sent", recipient=recipient_id)

        return success
