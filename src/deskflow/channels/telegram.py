"""Telegram Bot API channel adapter for IM integration.

Provides:
- Telegram message parsing (text, markdown, photo, document, etc.)
- Telegram message sending (text, markdown, photo, document)
- Webhook signature verification
- Health check for Telegram Bot API connection
- Long polling and Webhook modes support
"""

from __future__ import annotations

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
class TelegramMessage(BaseMessage):
    """Telegram-specific message with additional fields."""

    _channel_id: str = "telegram"
    _content: str = ""
    _sender_id: str = ""
    _message_id: str = field(default_factory=lambda: "")
    _message_type: MessageType = MessageType.TEXT
    _timestamp: datetime = field(default_factory=datetime.now)
    _metadata: dict[str, Any] = field(default_factory=dict)

    # Telegram-specific fields
    telegram_message_id: int = 0  # Telegram message ID
    chat_id: str = ""  # Chat ID
    chat_type: str = ""  # Chat type: private, group, supergroup, channel
    username: str = ""  # Sender username
    update_id: int = 0  # Telegram update ID

    def __post_init__(self):
        if not self._message_id:
            self._message_id = str(self.telegram_message_id) or f"tg_{int(time.time())}"


@dataclass
class TelegramConfig:
    """Telegram Bot configuration."""

    bot_token: str = ""
    webhook_url: str = ""
    use_webhook: bool = False
    allowed_updates: list[str] = field(default_factory=lambda: ["message", "callback_query"])
    secret_token: str = ""  # For webhook verification

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "bot_token": self.bot_token,
            "webhook_url": self.webhook_url,
            "use_webhook": self.use_webhook,
            "allowed_updates": self.allowed_updates,
            "secret_token": self.secret_token,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelegramConfig:
        """Create config from dictionary."""
        return cls(
            bot_token=data.get("bot_token", ""),
            webhook_url=data.get("webhook_url", ""),
            use_webhook=data.get("use_webhook", False),
            allowed_updates=data.get("allowed_updates", ["message", "callback_query"]),
            secret_token=data.get("secret_token", ""),
        )


class TelegramAdapter(ChannelAdapter):
    """Telegram Bot API channel adapter."""

    def __init__(
        self,
        config: TelegramConfig | None = None,
        channel_id: str = "telegram",
    ):
        super().__init__(channel_id=channel_id, config=config.to_dict() if config else {})
        self._config = config or TelegramConfig()
        self._client = httpx.AsyncClient(timeout=30.0)
        self._base_url = "https://api.telegram.org"
        self._last_update_offset: int = 0

    @property
    def channel_type(self) -> str:
        return "telegram"

    def to_dict(self) -> dict[str, Any]:
        """Convert adapter config to dictionary."""
        config_dict = self._config.to_dict()
        # Hide bot token for security
        config_dict["bot_token"] = self._mask_token(config_dict["bot_token"])
        return config_dict

    @staticmethod
    def _mask_token(token: str) -> str:
        """Mask bot token for security."""
        if not token:
            return ""
        if len(token) <= 8:
            return "***"
        return f"{token[:4]}...{token[-4:]}"

    @staticmethod
    def from_dict(data: dict[str, Any]) -> TelegramAdapter:
        """Create adapter from dictionary."""
        config = TelegramConfig.from_dict(data)
        return TelegramAdapter(config=config, channel_id=data.get("channel_id", "telegram"))

    def _verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Verify Telegram webhook signature using HMAC-SHA256.

        Args:
            payload: Raw request payload
            signature: X-Telegram-Bot-Api-Secret-Token header

        Returns:
            True if signature is valid, False otherwise
        """
        if not self._config.secret_token:
            logger.warning("telegram_webhook_secret_not_configured")
            return True  # Skip verification if not configured

        # Calculate expected signature
        expected_signature = hmac.new(
            self._config.secret_token.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

        # Compare signatures
        if signature != expected_signature:
            logger.error("telegram_signature_mismatch", received=signature)
            return False

        return True

    def _parse_telegram_message_type(self, raw_data: dict[str, Any]) -> MessageType:
        """Parse Telegram message type to MessageType."""
        if "text" in raw_data:
            return MessageType.TEXT
        elif "photo" in raw_data:
            return MessageType.IMAGE
        elif "document" in raw_data:
            return MessageType.FILE
        elif "voice" in raw_data:
            return MessageType.VOICE
        elif "video" in raw_data:
            return MessageType.VIDEO
        elif "audio" in raw_data:
            return MessageType.VOICE
        elif "sticker" in raw_data:
            return MessageType.IMAGE
        elif "contact" in raw_data:
            return MessageType.TEXT
        elif "location" in raw_data:
            return MessageType.TEXT
        return MessageType.TEXT

    async def parse_message(self, raw_data: dict[str, Any]) -> TelegramMessage:
        """Parse Telegram update data into TelegramMessage.

        Args:
            raw_data: Raw update data from Telegram

        Returns:
            Parsed TelegramMessage instance
        """
        # Handle different update types
        update_id = raw_data.get("update_id", 0)
        self._last_update_offset = max(self._last_update_offset, update_id + 1)

        # Extract message from update
        message_data = raw_data.get("message") or raw_data.get("edited_message") or raw_data.get("channel_post")

        if not message_data:
            # Handle callback query
            callback_query = raw_data.get("callback_query")
            if callback_query:
                message_data = callback_query.get("message")
                if message_data:
                    message_data["from"] = callback_query.get("from", {})

        if not message_data:
            logger.warning("telegram_no_message_in_update", update_id=update_id)
            return TelegramMessage(
                _content="",
                _sender_id="system",
                _metadata={"raw_data": raw_data, "update_id": update_id},
            )

        # Extract message fields
        telegram_message_id = message_data.get("message_id", 0)
        chat_data = message_data.get("chat", {})
        chat_id = str(chat_data.get("id", ""))
        chat_type = chat_data.get("type", "")

        # Extract sender info
        sender_data = message_data.get("from", {})
        sender_id = str(sender_data.get("id", ""))
        username = sender_data.get("username", "")

        # Extract content based on message type
        content = ""
        if "text" in message_data:
            content = message_data.get("text", "")
        elif "caption" in message_data:
            content = message_data.get("caption", "")
        elif "photo" in message_data:
            content = f"[Photo] {message_data.get('caption', '')}"
        elif "document" in message_data:
            doc = message_data.get("document", {})
            content = f"[File: {doc.get('file_name', 'unknown')}]"
        elif "voice" in message_data:
            content = "[Voice message]"
        elif "video" in message_data:
            content = "[Video]"

        # Build metadata
        metadata = {
            "raw_data": raw_data,
            "chat_title": chat_data.get("title", ""),
            "chat_username": chat_data.get("username", ""),
            "date": message_data.get("date", 0),
            "message_type": self._parse_telegram_message_type(message_data),
        }

        return TelegramMessage(
            _channel_id="telegram",
            _content=content,
            _sender_id=sender_id,
            _message_type=self._parse_telegram_message_type(message_data),
            _metadata=metadata,
            telegram_message_id=telegram_message_id,
            chat_id=chat_id,
            chat_type=chat_type,
            username=username,
            update_id=update_id,
        )

    async def _get_api_url(self, method: str) -> str:
        """Get Telegram API URL for a method."""
        return f"{self._base_url}/bot{self._config.bot_token}/{method}"

    async def send(self, message: OutboundMessage) -> bool:
        """Send a message to Telegram.

        Args:
            message: OutboundMessage to send

        Returns:
            True if sent successfully, False otherwise
        """
        if not self._config.bot_token:
            logger.error("telegram_bot_token_not_configured")
            return False

        try:
            # Parse chat_id from recipient_id
            chat_id = message.recipient_id

            # Send based on message type
            if message.message_type == MessageType.TEXT:
                return await self._send_text(chat_id, message.content)
            elif message.message_type == MessageType.IMAGE:
                return await self._send_photo(chat_id, message.content)
            elif message.message_type == MessageType.FILE:
                return await self._send_document(chat_id, message.content)
            else:
                # Default to text
                return await self._send_text(chat_id, message.content)

        except Exception as e:
            logger.error("telegram_message_send_error", error=str(e))
            return False

    async def _send_text(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "Markdown",
    ) -> bool:
        """Send a text message.

        Args:
            chat_id: Target chat ID
            text: Message text
            parse_mode: Parse mode (Markdown, HTML, or None)

        Returns:
            True if sent successfully
        """
        url = await self._get_api_url("sendMessage")
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        async with self._client as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

        success = result.get("ok", False)
        if success:
            logger.info("telegram_text_message_sent", chat_id=chat_id)
        else:
            logger.error(
                "telegram_message_send_failed",
                error_code=result.get("error_code"),
                description=result.get("description"),
            )

        return success

    async def _send_photo(
        self,
        chat_id: str,
        photo_url: str,
        caption: str = "",
    ) -> bool:
        """Send a photo message.

        Args:
            chat_id: Target chat ID
            photo_url: Photo URL or file ID
            caption: Optional caption

        Returns:
            True if sent successfully
        """
        url = await self._get_api_url("sendPhoto")
        payload = {
            "chat_id": chat_id,
            "photo": photo_url,
        }
        if caption:
            payload["caption"] = caption
            payload["parse_mode"] = "Markdown"

        async with self._client as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

        success = result.get("ok", False)
        if success:
            logger.info("telegram_photo_message_sent", chat_id=chat_id)

        return success

    async def _send_document(
        self,
        chat_id: str,
        document_url: str,
        caption: str = "",
    ) -> bool:
        """Send a document message.

        Args:
            chat_id: Target chat ID
            document_url: Document URL or file ID
            caption: Optional caption

        Returns:
            True if sent successfully
        """
        url = await self._get_api_url("sendDocument")
        payload = {
            "chat_id": chat_id,
            "document": document_url,
        }
        if caption:
            payload["caption"] = caption
            payload["parse_mode"] = "Markdown"

        async with self._client as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

        success = result.get("ok", False)
        if success:
            logger.info("telegram_document_message_sent", chat_id=chat_id)

        return success

    async def set_webhook(self, webhook_url: str | None = None) -> bool:
        """Set or delete webhook.

        Args:
            webhook_url: Webhook URL, or None to delete webhook

        Returns:
            True if set successfully
        """
        if webhook_url is None:
            # Delete webhook
            url = await self._get_api_url("deleteWebhook")
            payload = {}
        else:
            # Set webhook
            url = await self._get_api_url("setWebhook")
            payload = {
                "url": webhook_url,
                "allowed_updates": self._config.allowed_updates,
            }
            if self._config.secret_token:
                payload["secret_token"] = self._config.secret_token

        async with self._client as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

        success = result.get("ok", False)
        if success:
            if webhook_url:
                logger.info("telegram_webhook_set", url=webhook_url)
            else:
                logger.info("telegram_webhook_deleted")

        return success

    async def get_updates(
        self,
        offset: int | None = None,
        limit: int = 100,
        timeout: int = 30,
    ) -> list[dict[str, Any]]:
        """Get updates using long polling.

        Args:
            offset: Offset of the first update to return
            limit: Maximum number of updates to retrieve
            timeout: Timeout in seconds for long polling

        Returns:
            List of update dictionaries
        """
        if offset is None:
            offset = self._last_update_offset

        url = await self._get_api_url("getUpdates")
        params = {
            "offset": offset,
            "limit": limit,
            "timeout": timeout,
            "allowed_updates": self._config.allowed_updates,
        }

        async with self._client as client:
            response = await client.post(url, json=params)
            response.raise_for_status()
            result = response.json()

        if not result.get("ok", False):
            logger.error("telegram_get_updates_failed", description=result.get("description"))
            return []

        updates = result.get("result", [])
        logger.debug("telegram_updates_received", count=len(updates))
        return updates

    async def get_me(self) -> dict[str, Any] | None:
        """Get bot info.

        Returns:
            Bot info dictionary or None
        """
        url = await self._get_api_url("getMe")

        async with self._client as client:
            response = await client.get(url)
            response.raise_for_status()
            result = response.json()

        if result.get("ok", False):
            return result.get("result")
        return None

    async def health_check(self) -> bool:
        """Check Telegram Bot API connection health.

        Returns:
            True if healthy, False otherwise
        """
        try:
            if not self._config.bot_token:
                logger.warning("telegram_health_check_no_token")
                return False

            bot_info = await self.get_me()
            if bot_info:
                logger.info(
                    "telegram_health_check_success",
                    bot_username=bot_info.get("username"),
                )
                return True

            return False

        except Exception as e:
            logger.error("telegram_health_check_error", error=str(e))
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
        logger.info("telegram_adapter_closed")
