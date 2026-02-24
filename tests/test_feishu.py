"""Tests for Feishu channel adapter."""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from deskflow.channels.feishu import (
    FeishuAdapter,
    FeishuConfig,
    FeishuMessage,
)
from deskflow.channels.gateway import (
    OutboundMessage,
    MessageType,
    MessageGateway,
    get_gateway,
)


# Helper to get current UTC time
def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TestFeishuConfig:
    """Test FeishuConfig class."""

    def test_default_config(self):
        """Test default configuration."""
        config = FeishuConfig()

        assert config.app_id == ""
        assert config.app_secret == ""
        assert config.verification_token == ""
        assert config.encrypt_key == ""
        assert config.bot_name == ""
        assert config.webhook_url == ""

    def test_config_with_values(self):
        """Test configuration with values."""
        config = FeishuConfig(
            app_id="test_app_id",
            app_secret="test_app_secret",
            verification_token="test_token",
        )

        assert config.app_id == "test_app_id"
        assert config.app_secret == "test_app_secret"
        assert config.verification_token == "test_token"


class TestFeishuMessage:
    """Test FeishuMessage class."""

    def test_message_creation(self):
        """Test basic message creation."""
        msg = FeishuMessage(
            _content="Hello",
            _sender_id="user_123",
        )

        assert msg.content == "Hello"
        assert msg.sender_id == "user_123"
        assert msg.channel_id == "feishu"
        assert msg.message_type == MessageType.TEXT
        assert msg.chat_type == "private"

    def test_message_with_open_message_id(self):
        """Test message with Feishu message ID."""
        msg = FeishuMessage(
            _content="Hello",
            _sender_id="user_123",
            open_message_id="om_123456",
        )

        assert msg.open_message_id == "om_123456"
        assert msg.message_id == "om_123456"

    def test_message_to_dict(self):
        """Test message to_dict method."""
        msg = FeishuMessage(
            _content="Test message",
            _sender_id="user_456",
            chat_type="group",
            tenant_key="tenant_abc",
        )

        result = msg.to_dict()

        assert result["content"] == "Test message"
        assert result["sender_id"] == "user_456"
        assert result["channel_id"] == "feishu"


class TestFeishuAdapter:
    """Test FeishuAdapter class."""

    def test_adapter_creation(self):
        """Test adapter creation."""
        config = FeishuConfig(app_id="test_id")
        adapter = FeishuAdapter(config=config)

        assert adapter.channel_type == "feishu"
        assert adapter.channel_id == "feishu"
        assert adapter.enabled is True

    def test_adapter_enable_disable(self):
        """Test adapter enable/disable."""
        adapter = FeishuAdapter()

        adapter.disable()
        assert adapter.enabled is False

        adapter.enable()
        assert adapter.enabled is True

    def test_adapter_to_dict(self):
        """Test adapter to_dict method."""
        config = FeishuConfig(
            app_id="test_app",
            app_secret="test_secret",
            bot_name="Test Bot",
        )
        adapter = FeishuAdapter(config=config)

        result = adapter.to_dict()

        assert result["app_id"] == "test_app"
        assert result["app_secret"] == "test_secret"
        assert result["bot_name"] == "Test Bot"

    def test_adapter_from_dict(self):
        """Test adapter from_dict method."""
        data = {
            "app_id": "restored_app",
            "app_secret": "restored_secret",
            "bot_name": "Restored Bot",
            "channel_id": "feishu_custom",
        }

        adapter = FeishuAdapter.from_dict(data)

        assert adapter.to_dict()["app_id"] == "restored_app"
        assert adapter.channel_id == "feishu_custom"

    def test_parse_feishu_message_type(self):
        """Test Feishu message type parsing."""
        adapter = FeishuAdapter()

        assert adapter._parse_feishu_message_type("text") == MessageType.TEXT
        assert adapter._parse_feishu_message_type("post") == MessageType.TEXT
        assert adapter._parse_feishu_message_type("image") == MessageType.IMAGE
        assert adapter._parse_feishu_message_type("file") == MessageType.FILE
        assert adapter._parse_feishu_message_type("audio") == MessageType.VOICE
        assert adapter._parse_feishu_message_type("video") == MessageType.VIDEO
        assert adapter._parse_feishu_message_type("unknown") == MessageType.TEXT


class TestFeishuAdapterParseMessage:
    """Test FeishuAdapter message parsing."""

    @pytest.mark.asyncio
    async def test_parse_text_message(self):
        """Test parsing text message."""
        adapter = FeishuAdapter()

        raw_data = {
            "header": {
                "event_type": "im.message.receive_v1",
                "create_time": 1708000000000,
                "tenant_key": "tenant_123",
            },
            "event": {
                "sender": {
                    "sender_id": {"open_id": "ou_123"}
                },
                "message": {
                    "message_id": "om_456",
                    "message_type": "text",
                    "content": "Hello World",
                    "chat_type": "private",
                },
            },
        }

        msg = await adapter.parse_message(raw_data)

        assert msg.content == "Hello World"
        assert msg.sender_id == "ou_123"
        assert msg.open_message_id == "om_456"
        assert msg.message_type == MessageType.TEXT
        assert msg.chat_type == "private"

    @pytest.mark.asyncio
    async def test_parse_challenge(self):
        """Test parsing URL verification challenge."""
        adapter = FeishuAdapter()

        raw_data = {
            "challenge": "test_challenge_123",
            "type": "url_verification",
        }

        msg = await adapter.parse_message(raw_data)

        assert msg.content == "test_challenge_123"
        assert msg.metadata.get("challenge") is True

    @pytest.mark.asyncio
    async def test_parse_post_message(self):
        """Test parsing rich text (post) message."""
        adapter = FeishuAdapter()

        raw_data = {
            "header": {
                "event_type": "im.message.receive_v1",
                "create_time": 1708000000000,
            },
            "event": {
                "sender": {
                    "sender_id": {"open_id": "ou_789"}
                },
                "message": {
                    "message_id": "om_post_123",
                    "message_type": "post",
                    "content": '{"content": [{"tag": "text", "text": "Hello "}, {"tag": "a", "text": "Link", "href": "http://example.com"}]}',
                    "chat_type": "group",
                },
            },
        }

        msg = await adapter.parse_message(raw_data)

        assert "Hello" in msg.content
        assert msg.message_type == MessageType.TEXT

    @pytest.mark.asyncio
    async def test_parse_image_message(self):
        """Test parsing image message."""
        adapter = FeishuAdapter()

        raw_data = {
            "header": {
                "event_type": "im.message.receive_v1",
                "create_time": 1708000000000,
            },
            "event": {
                "sender": {
                    "sender_id": {"open_id": "ou_img"}
                },
                "message": {
                    "message_id": "om_img_123",
                    "message_type": "image",
                    "content": "image_key_abc",
                    "chat_type": "private",
                },
            },
        }

        msg = await adapter.parse_message(raw_data)

        assert msg.message_type == MessageType.IMAGE
        assert msg.content == "image_key_abc"


class TestFeishuAdapterSignature:
    """Test FeishuAdapter signature verification."""

    def test_verify_signature_skip_no_token(self):
        """Test signature verification skips when no token configured."""
        adapter = FeishuAdapter()

        result = adapter._verify_signature(
            timestamp="1234567890",
            nonce="test_nonce",
            signature="any_signature",
            body=b"test body",
        )

        assert result is True

    def test_verify_signature_with_token(self):
        """Test signature verification with token."""
        config = FeishuConfig(verification_token="secret_token")
        adapter = FeishuAdapter(config=config)

        # This will fail because we're not providing valid signature
        # but it tests the verification logic exists
        result = adapter._verify_signature(
            timestamp="1234567890",
            nonce="test_nonce",
            signature="invalid_signature",
            body=b"test body",
        )

        assert result is False


class TestFeishuAdapterSend:
    """Test FeishuAdapter message sending."""

    @pytest.mark.asyncio
    async def test_send_text_message_success(self):
        """Test sending text message successfully."""
        adapter = FeishuAdapter()

        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.json.return_value = {"code": 0, "data": {"message_id": "msg_123"}}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Mock token retrieval
        adapter._access_token = "mock_token"
        adapter._token_expire_at = 9999999999
        adapter._client = mock_client

        message = OutboundMessage(
            channel_id="feishu",
            content="Hello",
            recipient_id="ou_123",
        )

        result = await adapter.send(message)

        assert result is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_text_message_failure(self):
        """Test sending text message fails gracefully."""
        adapter = FeishuAdapter()

        # Mock the HTTP client to raise error
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._access_token = "mock_token"
        adapter._token_expire_at = 9999999999
        adapter._client = mock_client

        message = OutboundMessage(
            channel_id="feishu",
            content="Hello",
            recipient_id="ou_123",
        )

        result = await adapter.send(message)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_access_token_cached(self):
        """Test access token is cached."""
        adapter = FeishuAdapter()
        adapter._access_token = "cached_token"
        adapter._token_expire_at = 9999999999

        token = await adapter._get_access_token()

        assert token == "cached_token"

    @pytest.mark.asyncio
    async def test_get_access_token_fetch_new(self):
        """Test fetching new access token."""
        adapter = FeishuAdapter(
            config=FeishuConfig(app_id="test_app", app_secret="test_secret")
        )

        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 0,
            "tenant_access_token": "new_token",
            "expire": 7200,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        token = await adapter._get_access_token()

        assert token == "new_token"
        assert adapter._access_token == "new_token"


class TestFeishuAdapterHealthCheck:
    """Test FeishuAdapter health check."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test health check success."""
        adapter = FeishuAdapter()

        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.json.return_value = {"code": 0}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._access_token = "mock_token"
        adapter._token_expire_at = 9999999999
        adapter._client = mock_client

        result = await adapter.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check failure."""
        adapter = FeishuAdapter()

        # Mock the HTTP client to raise error
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection error"))
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        result = await adapter.health_check()

        assert result is False


class TestFeishuAdapterPostContent:
    """Test FeishuAdapter rich text content parsing."""

    def test_parse_post_content_dict(self):
        """Test parsing post content from dict."""
        adapter = FeishuAdapter()

        content = {
            "content": [
                {"tag": "text", "text": "Hello "},
                {"tag": "a", "text": "World", "href": "http://example.com"},
                {"tag": "at", "user_name": "User1"},
            ]
        }

        result = adapter._parse_post_content(content)

        assert "Hello" in result
        assert "World" in result
        assert "@User1" in result

    def test_parse_post_content_string(self):
        """Test parsing post content from JSON string."""
        adapter = FeishuAdapter()

        content = '{"content": [{"tag": "text", "text": "Test content"}]}'

        result = adapter._parse_post_content(content)

        assert result == "Test content"

    def test_parse_post_content_nested(self):
        """Test parsing post content with nested structure."""
        adapter = FeishuAdapter()

        content = {
            "content": [
                {
                    "tag": "p",
                    "children": [
                        {"tag": "text", "text": "Paragraph "},
                        {"tag": "b", "children": [{"tag": "text", "text": "bold"}]},
                    ],
                }
            ]
        }

        result = adapter._parse_post_content(content)

        assert "Paragraph" in result
        assert "bold" in result


class TestFeishuGatewayIntegration:
    """Test Feishu adapter integration with MessageGateway."""

    def test_register_feishu_adapter(self):
        """Test registering Feishu adapter to gateway."""
        gateway = MessageGateway()
        adapter = FeishuAdapter()

        gateway.register_adapter(adapter)

        retrieved = gateway.get_adapter("feishu")
        assert retrieved is adapter
        assert retrieved.channel_type == "feishu"

    def test_list_adapters_includes_feishu(self):
        """Test listing adapters includes Feishu."""
        gateway = MessageGateway()
        adapter = FeishuAdapter()

        gateway.register_adapter(adapter)

        adapters = gateway.list_adapters()

        assert len(adapters) == 1
        assert adapters[0]["channel_type"] == "feishu"

    def test_unregister_feishu_adapter(self):
        """Test unregistering Feishu adapter."""
        gateway = MessageGateway()
        adapter = FeishuAdapter()

        gateway.register_adapter(adapter)
        gateway.unregister_adapter("feishu")

        retrieved = gateway.get_adapter("feishu")
        assert retrieved is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
