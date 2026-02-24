"""Tests for Telegram Bot API channel adapter."""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from deskflow.channels.telegram import (
    TelegramAdapter,
    TelegramConfig,
    TelegramMessage,
)
from deskflow.channels.gateway import OutboundMessage, MessageType


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TestTelegramConfig:
    """Test TelegramConfig class."""

    def test_default_config(self):
        """Test default configuration."""
        config = TelegramConfig()

        assert config.bot_token == ""
        assert config.webhook_url == ""
        assert config.use_webhook is False
        assert config.allowed_updates == ["message", "callback_query"]
        assert config.secret_token == ""

    def test_config_with_values(self):
        """Test configuration with values."""
        config = TelegramConfig(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            webhook_url="https://example.com/webhook",
            use_webhook=True,
            secret_token="my_secret",
        )

        assert config.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        assert config.webhook_url == "https://example.com/webhook"
        assert config.use_webhook is True
        assert config.secret_token == "my_secret"

    def test_config_to_dict(self):
        """Test config to_dict method."""
        config = TelegramConfig(
            bot_token="test_token",
            webhook_url="https://example.com",
        )
        result = config.to_dict()

        assert result["bot_token"] == "test_token"
        assert result["webhook_url"] == "https://example.com"
        assert result["use_webhook"] is False

    def test_config_from_dict(self):
        """Test config from_dict method."""
        data = {
            "bot_token": "restored_token",
            "webhook_url": "https://restored.com",
            "use_webhook": True,
            "allowed_updates": ["message"],
            "secret_token": "restored_secret",
        }

        config = TelegramConfig.from_dict(data)

        assert config.bot_token == "restored_token"
        assert config.webhook_url == "https://restored.com"
        assert config.use_webhook is True
        assert config.allowed_updates == ["message"]
        assert config.secret_token == "restored_secret"


class TestTelegramMessage:
    """Test TelegramMessage class."""

    def test_message_creation(self):
        """Test basic message creation."""
        msg = TelegramMessage(_content="Hello", _sender_id="user_123")

        assert msg.content == "Hello"
        assert msg.sender_id == "user_123"
        assert msg.channel_id == "telegram"
        assert msg.message_type == MessageType.TEXT

    def test_message_with_telegram_id(self):
        """Test message with Telegram message ID."""
        msg = TelegramMessage(
            _content="Hello",
            _sender_id="user_123",
            telegram_message_id=12345,
        )

        assert msg.telegram_message_id == 12345
        assert msg.message_id == "12345"

    def test_message_with_chat_info(self):
        """Test message with chat information."""
        msg = TelegramMessage(
            _content="Test",
            _sender_id="user_456",
            chat_id="-1001234567890",
            chat_type="supergroup",
            username="testuser",
        )

        assert msg.chat_id == "-1001234567890"
        assert msg.chat_type == "supergroup"
        assert msg.username == "testuser"

    def test_message_to_dict(self):
        """Test message to_dict method."""
        msg = TelegramMessage(
            _content="Test",
            _sender_id="user_456",
            chat_id="-1001234567890",
        )

        result = msg.to_dict()

        assert result["content"] == "Test"
        assert result["sender_id"] == "user_456"


class TestTelegramAdapter:
    """Test TelegramAdapter class."""

    def test_adapter_creation(self):
        """Test adapter creation."""
        config = TelegramConfig(bot_token="test_token")
        adapter = TelegramAdapter(config=config)

        assert adapter.channel_type == "telegram"
        assert adapter.channel_id == "telegram"
        assert adapter.enabled is True

    def test_adapter_enable_disable(self):
        """Test adapter enable/disable."""
        adapter = TelegramAdapter()

        adapter.disable()
        assert adapter.enabled is False

        adapter.enable()
        assert adapter.enabled is True

    def test_adapter_to_dict(self):
        """Test adapter to_dict method."""
        config = TelegramConfig(
            bot_token="123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            webhook_url="https://example.com",
        )
        adapter = TelegramAdapter(config=config)

        result = adapter.to_dict()

        # Token should be masked
        assert result["bot_token"] == "1234...ew11"
        assert result["webhook_url"] == "https://example.com"

    def test_adapter_from_dict(self):
        """Test adapter from_dict method."""
        data = {
            "bot_token": "restored_token",
            "webhook_url": "https://restored.com",
            "use_webhook": True,
            "channel_id": "telegram_custom",
        }

        adapter = TelegramAdapter.from_dict(data)

        assert adapter.channel_id == "telegram_custom"
        # Token is masked in to_dict, check the config directly
        assert adapter._config.bot_token == "restored_token"

    def test_mask_token(self):
        """Test token masking."""
        assert TelegramAdapter._mask_token("") == ""
        assert TelegramAdapter._mask_token("short") == "***"
        assert TelegramAdapter._mask_token("123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11") == "1234...ew11"

    def test_parse_telegram_message_type(self):
        """Test Telegram message type parsing."""
        adapter = TelegramAdapter()

        assert adapter._parse_telegram_message_type({"text": "Hello"}) == MessageType.TEXT
        assert adapter._parse_telegram_message_type({"photo": []}) == MessageType.IMAGE
        assert adapter._parse_telegram_message_type({"document": {}}) == MessageType.FILE
        assert adapter._parse_telegram_message_type({"voice": {}}) == MessageType.VOICE
        assert adapter._parse_telegram_message_type({"video": {}}) == MessageType.VIDEO
        assert adapter._parse_telegram_message_type({"audio": {}}) == MessageType.VOICE
        assert adapter._parse_telegram_message_type({"sticker": {}}) == MessageType.IMAGE
        assert adapter._parse_telegram_message_type({"contact": {}}) == MessageType.TEXT
        assert adapter._parse_telegram_message_type({"location": {}}) == MessageType.TEXT
        assert adapter._parse_telegram_message_type({}) == MessageType.TEXT


class TestTelegramAdapterSignature:
    """Test TelegramAdapter signature verification."""

    def test_verify_signature_skip_no_secret(self):
        """Test signature verification skips when no secret configured."""
        adapter = TelegramAdapter()

        result = adapter._verify_webhook_signature(
            payload=b"test payload",
            signature="any_sig",
        )

        assert result is True

    def test_verify_signature_valid(self):
        """Test signature verification with valid signature."""
        import hmac
        import hashlib

        secret = "my_secret_token"
        config = TelegramConfig(secret_token=secret)
        adapter = TelegramAdapter(config=config)

        payload = b'{"update_id": 123}'
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

        result = adapter._verify_webhook_signature(
            payload=payload,
            signature=expected_signature,
        )

        assert result is True

    def test_verify_signature_invalid(self):
        """Test signature verification with invalid signature."""
        config = TelegramConfig(secret_token="my_secret")
        adapter = TelegramAdapter(config=config)

        result = adapter._verify_webhook_signature(
            payload=b'{"update_id": 123}',
            signature="invalid_signature",
        )

        assert result is False


class TestTelegramAdapterParseMessage:
    """Test TelegramAdapter message parsing."""

    @pytest.mark.asyncio
    async def test_parse_text_message(self):
        """Test parsing text message."""
        adapter = TelegramAdapter()

        raw_data = {
            "update_id": 12345,
            "message": {
                "message_id": 100,
                "from": {"id": 999, "username": "testuser"},
                "chat": {"id": -1001234567890, "type": "supergroup"},
                "text": "Hello World",
                "date": 1234567890,
            },
        }

        msg = await adapter.parse_message(raw_data)

        assert msg.content == "Hello World"
        assert msg.sender_id == "999"
        assert msg.telegram_message_id == 100
        assert msg.chat_id == "-1001234567890"
        assert msg.chat_type == "supergroup"
        assert msg.username == "testuser"
        assert msg.update_id == 12345
        assert msg.message_type == MessageType.TEXT

    @pytest.mark.asyncio
    async def test_parse_photo_message(self):
        """Test parsing photo message."""
        adapter = TelegramAdapter()

        raw_data = {
            "update_id": 12346,
            "message": {
                "message_id": 101,
                "from": {"id": 888, "username": "photouser"},
                "chat": {"id": 123, "type": "private"},
                "photo": [{"file_id": "AgADxxx", "file_size": 1024}],
                "caption": "Nice photo",
                "date": 1234567891,
            },
        }

        msg = await adapter.parse_message(raw_data)

        assert "Nice photo" in msg.content
        assert msg.message_type == MessageType.IMAGE

    @pytest.mark.asyncio
    async def test_parse_document_message(self):
        """Test parsing document message."""
        adapter = TelegramAdapter()

        raw_data = {
            "update_id": 12347,
            "message": {
                "message_id": 102,
                "from": {"id": 777},
                "chat": {"id": 456, "type": "private"},
                "document": {"file_name": "document.pdf", "file_size": 2048},
                "date": 1234567892,
            },
        }

        msg = await adapter.parse_message(raw_data)

        assert "document.pdf" in msg.content
        assert msg.message_type == MessageType.FILE

    @pytest.mark.asyncio
    async def test_parse_voice_message(self):
        """Test parsing voice message."""
        adapter = TelegramAdapter()

        raw_data = {
            "update_id": 12348,
            "message": {
                "message_id": 103,
                "from": {"id": 666},
                "chat": {"id": 789, "type": "private"},
                "voice": {"duration": 10},
                "date": 1234567893,
            },
        }

        msg = await adapter.parse_message(raw_data)

        assert "[Voice message]" in msg.content
        assert msg.message_type == MessageType.VOICE

    @pytest.mark.asyncio
    async def test_parse_edited_message(self):
        """Test parsing edited message."""
        adapter = TelegramAdapter()

        raw_data = {
            "update_id": 12349,
            "edited_message": {
                "message_id": 104,
                "from": {"id": 555},
                "chat": {"id": 321, "type": "private"},
                "text": "Edited text",
                "date": 1234567894,
            },
        }

        msg = await adapter.parse_message(raw_data)

        assert msg.content == "Edited text"
        assert msg.telegram_message_id == 104

    @pytest.mark.asyncio
    async def test_parse_callback_query(self):
        """Test parsing callback query."""
        adapter = TelegramAdapter()

        raw_data = {
            "update_id": 12350,
            "callback_query": {
                "id": "cb_123",
                "from": {"id": 444, "username": "callbackuser"},
                "message": {
                    "message_id": 105,
                    "chat": {"id": 654, "type": "private"},
                    "text": "Button clicked",
                },
                "data": "button_1",
            },
        }

        msg = await adapter.parse_message(raw_data)

        assert msg.content == "Button clicked"
        assert msg.sender_id == "444"
        assert msg.username == "callbackuser"

    @pytest.mark.asyncio
    async def test_parse_empty_update(self):
        """Test parsing update with no message."""
        adapter = TelegramAdapter()

        raw_data = {
            "update_id": 12351,
        }

        msg = await adapter.parse_message(raw_data)

        assert msg.content == ""
        assert msg.sender_id == "system"
        # update_id is set in metadata but telegram_message_id defaults to 0
        assert msg.telegram_message_id == 0

    @pytest.mark.asyncio
    async def test_parse_channel_post(self):
        """Test parsing channel post."""
        adapter = TelegramAdapter()

        raw_data = {
            "update_id": 12352,
            "channel_post": {
                "message_id": 200,
                "chat": {"id": -1009876543210, "type": "channel", "title": "Test Channel"},
                "text": "Channel announcement",
                "date": 1234567895,
            },
        }

        msg = await adapter.parse_message(raw_data)

        assert msg.content == "Channel announcement"
        assert msg.chat_id == "-1009876543210"
        assert msg.chat_type == "channel"


class TestTelegramAdapterSend:
    """Test TelegramAdapter message sending."""

    @pytest.mark.asyncio
    async def test_send_text_message(self):
        """Test sending text message."""
        config = TelegramConfig(bot_token="test_token")
        adapter = TelegramAdapter(config=config)

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 999}}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        message = OutboundMessage(
            channel_id="telegram",
            content="Hello from bot",
            recipient_id="123456789",
        )

        result = await adapter.send(message)

        assert result is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_photo_message(self):
        """Test sending photo message."""
        config = TelegramConfig(bot_token="test_token")
        adapter = TelegramAdapter(config=config)

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        message = OutboundMessage(
            channel_id="telegram",
            content="https://example.com/image.jpg",
            recipient_id="123456789",
            message_type=MessageType.IMAGE,
        )

        result = await adapter.send(message)

        assert result is True

    @pytest.mark.asyncio
    async def test_send_document_message(self):
        """Test sending document message."""
        config = TelegramConfig(bot_token="test_token")
        adapter = TelegramAdapter(config=config)

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        message = OutboundMessage(
            channel_id="telegram",
            content="https://example.com/doc.pdf",
            recipient_id="123456789",
            message_type=MessageType.FILE,
        )

        result = await adapter.send(message)

        assert result is True

    @pytest.mark.asyncio
    async def test_send_message_no_token(self):
        """Test sending message without bot token."""
        adapter = TelegramAdapter()

        message = OutboundMessage(
            channel_id="telegram",
            content="Hello",
            recipient_id="123456789",
        )

        result = await adapter.send(message)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_failure(self):
        """Test sending message fails gracefully."""
        config = TelegramConfig(bot_token="test_token")
        adapter = TelegramAdapter(config=config)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        message = OutboundMessage(
            channel_id="telegram",
            content="Hello",
            recipient_id="123456789",
        )

        result = await adapter.send(message)

        assert result is False


class TestTelegramAdapterWebhook:
    """Test TelegramAdapter webhook operations."""

    @pytest.mark.asyncio
    async def test_set_webhook(self):
        """Test setting webhook."""
        config = TelegramConfig(
            bot_token="test_token",
            webhook_url="https://example.com/webhook",
            secret_token="my_secret",
        )
        adapter = TelegramAdapter(config=config)

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        result = await adapter.set_webhook("https://example.com/webhook")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_webhook(self):
        """Test deleting webhook."""
        config = TelegramConfig(bot_token="test_token")
        adapter = TelegramAdapter(config=config)

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        result = await adapter.set_webhook(None)

        assert result is True


class TestTelegramAdapterUpdates:
    """Test TelegramAdapter getUpdates operations."""

    @pytest.mark.asyncio
    async def test_get_updates(self):
        """Test getting updates via long polling."""
        config = TelegramConfig(bot_token="test_token")
        adapter = TelegramAdapter(config=config)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": [
                {
                    "update_id": 100,
                    "message": {"message_id": 1, "text": "Hello", "from": {}, "chat": {}},
                }
            ],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        updates = await adapter.get_updates(offset=0, limit=10, timeout=30)

        assert len(updates) == 1
        assert updates[0]["update_id"] == 100


class TestTelegramAdapterHealthCheck:
    """Test TelegramAdapter health check."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test health check success."""
        config = TelegramConfig(bot_token="test_token")
        adapter = TelegramAdapter(config=config)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {"id": 123, "username": "testbot", "is_bot": True},
        }
        mock_response.raise_for_status = MagicMock()
        mock_response.get = AsyncMock(return_value=mock_response)

        mock_client = AsyncMock()
        mock_client.get = mock_response.get
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        result = await adapter.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_no_token(self):
        """Test health check without bot token."""
        adapter = TelegramAdapter()

        result = await adapter.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check failure."""
        config = TelegramConfig(bot_token="test_token")
        adapter = TelegramAdapter(config=config)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection error"))
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        result = await adapter.health_check()

        assert result is False


class TestTelegramAdapterGetMe:
    """Test TelegramAdapter getMe operation."""

    @pytest.mark.asyncio
    async def test_get_me_success(self):
        """Test getMe success."""
        config = TelegramConfig(bot_token="test_token")
        adapter = TelegramAdapter(config=config)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {"id": 123, "username": "testbot", "is_bot": True},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        bot_info = await adapter.get_me()

        assert bot_info is not None
        assert bot_info["username"] == "testbot"

    @pytest.mark.asyncio
    async def test_get_me_failure(self):
        """Test getMe failure."""
        config = TelegramConfig(bot_token="test_token")
        adapter = TelegramAdapter(config=config)

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False, "error_code": 401, "description": "Unauthorized"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        bot_info = await adapter.get_me()

        assert bot_info is None


class TestTelegramGatewayIntegration:
    """Test Telegram adapter integration with MessageGateway."""

    def test_register_telegram_adapter(self):
        """Test registering Telegram adapter to gateway."""
        from deskflow.channels.gateway import MessageGateway

        gateway = MessageGateway()
        adapter = TelegramAdapter()

        gateway.register_adapter(adapter)

        retrieved = gateway.get_adapter("telegram")
        assert retrieved is adapter
        assert retrieved.channel_type == "telegram"

    def test_list_adapters_includes_telegram(self):
        """Test listing adapters includes Telegram."""
        from deskflow.channels.gateway import MessageGateway

        gateway = MessageGateway()
        adapter = TelegramAdapter()

        gateway.register_adapter(adapter)

        adapters = gateway.list_adapters()

        assert len(adapters) == 1
        assert adapters[0]["channel_type"] == "telegram"

    def test_unregister_telegram_adapter(self):
        """Test unregistering Telegram adapter."""
        from deskflow.channels.gateway import MessageGateway

        gateway = MessageGateway()
        adapter = TelegramAdapter()

        gateway.register_adapter(adapter)
        gateway.unregister_adapter("telegram")

        retrieved = gateway.get_adapter("telegram")
        assert retrieved is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
