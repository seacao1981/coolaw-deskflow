"""Tests for DingTalk channel adapter."""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from deskflow.channels.dingtalk import (
    DingTalkAdapter,
    DingTalkConfig,
    DingTalkMessage,
)
from deskflow.channels.gateway import OutboundMessage, MessageType


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TestDingTalkConfig:
    """Test DingTalkConfig class."""

    def test_default_config(self):
        """Test default configuration."""
        config = DingTalkConfig()

        assert config.app_key == ""
        assert config.app_secret == ""
        assert config.access_token == ""
        assert config.webhook_url == ""
        assert config.agent_id == ""

    def test_config_with_values(self):
        """Test configuration with values."""
        config = DingTalkConfig(
            app_key="test_app_key",
            app_secret="test_secret",
            agent_id="123456",
        )

        assert config.app_key == "test_app_key"
        assert config.app_secret == "test_secret"
        assert config.agent_id == "123456"

    def test_config_to_dict(self):
        """Test config to_dict method."""
        config = DingTalkConfig(app_key="test_key", app_secret="test_secret")
        result = config.to_dict()

        assert result["app_key"] == "test_key"
        assert result["app_secret"] == "test_secret"

    def test_config_from_dict(self):
        """Test config from_dict method."""
        data = {
            "app_key": "restored_key",
            "app_secret": "restored_secret",
            "agent_id": "123457",
        }

        config = DingTalkConfig.from_dict(data)

        assert config.app_key == "restored_key"
        assert config.app_secret == "restored_secret"
        assert config.agent_id == "123457"


class TestDingTalkMessage:
    """Test DingTalkMessage class."""

    def test_message_creation(self):
        """Test basic message creation."""
        msg = DingTalkMessage(_content="Hello", _sender_id="user_123")

        assert msg.content == "Hello"
        assert msg.sender_id == "user_123"
        assert msg.channel_id == "dingtalk"
        assert msg.message_type == MessageType.TEXT

    def test_message_with_msg_id(self):
        """Test message with DingTalk message ID."""
        msg = DingTalkMessage(
            _content="Hello",
            _sender_id="user_123",
            msg_id="msg_123456",
        )

        assert msg.msg_id == "msg_123456"
        assert msg.message_id == "msg_123456"

    def test_message_to_dict(self):
        """Test message to_dict method."""
        msg = DingTalkMessage(
            _content="Test",
            _sender_id="user_456",
            conversation_id="conv_789",
        )

        result = msg.to_dict()

        assert result["content"] == "Test"
        assert result["sender_id"] == "user_456"


class TestDingTalkAdapter:
    """Test DingTalkAdapter class."""

    def test_adapter_creation(self):
        """Test adapter creation."""
        config = DingTalkConfig(app_key="test_key")
        adapter = DingTalkAdapter(config=config)

        assert adapter.channel_type == "dingtalk"
        assert adapter.channel_id == "dingtalk"
        assert adapter.enabled is True

    def test_adapter_enable_disable(self):
        """Test adapter enable/disable."""
        adapter = DingTalkAdapter()

        adapter.disable()
        assert adapter.enabled is False

        adapter.enable()
        assert adapter.enabled is True

    def test_adapter_to_dict(self):
        """Test adapter to_dict method."""
        config = DingTalkConfig(app_key="test_key", app_secret="test_secret")
        adapter = DingTalkAdapter(config=config)

        result = adapter.to_dict()

        assert result["app_key"] == "test_key"
        assert result["app_secret"] == "test_secret"

    def test_adapter_from_dict(self):
        """Test adapter from_dict method."""
        data = {
            "app_key": "restored_key",
            "app_secret": "restored_secret",
            "channel_id": "dingtalk_custom",
        }

        adapter = DingTalkAdapter.from_dict(data)

        assert adapter.to_dict()["app_key"] == "restored_key"
        assert adapter.channel_id == "dingtalk_custom"

    def test_parse_dingtalk_message_type(self):
        """Test DingTalk message type parsing."""
        adapter = DingTalkAdapter()

        assert adapter._parse_dingtalk_message_type("text") == MessageType.TEXT
        assert adapter._parse_dingtalk_message_type("markdown") == MessageType.TEXT
        assert adapter._parse_dingtalk_message_type("link") == MessageType.LINK
        assert adapter._parse_dingtalk_message_type("action_card") == MessageType.TEXT
        assert adapter._parse_dingtalk_message_type("image") == MessageType.IMAGE
        assert adapter._parse_dingtalk_message_type("voice") == MessageType.VOICE
        assert adapter._parse_dingtalk_message_type("video") == MessageType.VIDEO
        assert adapter._parse_dingtalk_message_type("file") == MessageType.FILE
        assert adapter._parse_dingtalk_message_type("unknown") == MessageType.TEXT


class TestDingTalkAdapterSignature:
    """Test DingTalkAdapter signature verification."""

    def test_verify_signature_skip_no_secret(self):
        """Test signature verification skips when no secret configured."""
        adapter = DingTalkAdapter()

        result = adapter._verify_signature(
            timestamp="1234567890",
            signature="any_sig",
        )

        assert result is True

    def test_verify_signature_valid(self):
        """Test signature verification with valid signature."""
        config = DingTalkConfig(app_secret="secret_key")
        adapter = DingTalkAdapter(config=config)

        # Calculate valid signature
        import hmac
        import hashlib
        import base64
        from urllib.parse import quote

        timestamp = "1234567890"
        secret_bytes = "secret_key".encode("utf-8")
        timestamp_bytes = timestamp.encode("utf-8")

        mac = hmac.new(secret_bytes, timestamp_bytes, hashlib.sha256)
        signature = base64.b64encode(mac.digest()).decode("utf-8")
        encoded_signature = quote(signature, safe="")

        result = adapter._verify_signature(
            timestamp=timestamp,
            signature=encoded_signature,
        )

        assert result is True

    def test_verify_signature_invalid(self):
        """Test signature verification with invalid signature."""
        config = DingTalkConfig(app_secret="secret_key")
        adapter = DingTalkAdapter(config=config)

        result = adapter._verify_signature(
            timestamp="1234567890",
            signature="invalid_signature",
        )

        assert result is False

    def test_calc_signature(self):
        """Test signature calculation."""
        config = DingTalkConfig(app_secret="test_secret")
        adapter = DingTalkAdapter(config=config)

        timestamp = "1234567890"
        signature = adapter._calc_signature(timestamp)

        assert signature is not None
        assert len(signature) > 0


class TestDingTalkAdapterParseMessage:
    """Test DingTalkAdapter message parsing."""

    @pytest.mark.asyncio
    async def test_parse_text_message(self):
        """Test parsing text message."""
        adapter = DingTalkAdapter()

        raw_data = {
            "msgtype": "text",
            "text": {"content": "Hello World"},
            "senderId": "user_123",
            "conversationId": "conv_456",
            "msgId": "msg_789",
            "timestamp": "1234567890",
        }

        msg = await adapter.parse_message(raw_data)

        assert msg.content == "Hello World"
        assert msg.sender_id == "user_123"
        assert msg.msg_id == "msg_789"
        assert msg.message_type == MessageType.TEXT

    @pytest.mark.asyncio
    async def test_parse_markdown_message(self):
        """Test parsing markdown message."""
        adapter = DingTalkAdapter()

        raw_data = {
            "msgtype": "markdown",
            "markdown": {"text": "# Heading\n**Bold** text"},
            "senderId": "user_md",
            "timestamp": "1234567890",
        }

        msg = await adapter.parse_message(raw_data)

        assert "# Heading" in msg.content
        assert msg.message_type == MessageType.TEXT

    @pytest.mark.asyncio
    async def test_parse_link_message(self):
        """Test parsing link message."""
        adapter = DingTalkAdapter()

        raw_data = {
            "msgtype": "link",
            "link": {
                "title": "Test Link",
                "text": "Link description",
                "messageUrl": "https://example.com",
            },
            "senderId": "user_link",
            "timestamp": "1234567890",
        }

        msg = await adapter.parse_message(raw_data)

        assert "Test Link" in msg.content
        assert msg.message_type == MessageType.LINK

    @pytest.mark.asyncio
    async def test_parse_verification_request(self):
        """Test parsing verification request."""
        adapter = DingTalkAdapter()

        raw_data = {
            "test": True,
            "senderId": "dingtalk_system",
        }

        msg = await adapter.parse_message(raw_data)

        assert msg._content == "verification"
        assert msg.metadata["test"] is True


class TestDingTalkAdapterSend:
    """Test DingTalkAdapter message sending."""

    @pytest.mark.asyncio
    async def test_send_text_message_by_webhook(self):
        """Test sending text message via webhook."""
        config = DingTalkConfig(webhook_url="https://oapi.dingtalk.com/robot/send?access_token=test")
        adapter = DingTalkAdapter(config=config)

        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        message = OutboundMessage(
            channel_id="dingtalk",
            content="Hello",
            recipient_id="user_123",
        )

        result = await adapter.send(message)

        assert result is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_markdown_message_by_webhook(self):
        """Test sending markdown message via webhook."""
        config = DingTalkConfig(webhook_url="https://oapi.dingtalk.com/robot/send?access_token=test")
        adapter = DingTalkAdapter(config=config)

        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        message = OutboundMessage(
            channel_id="dingtalk",
            content="# Heading\n**Bold** text",
            recipient_id="user_123",
        )

        result = await adapter.send(message)

        assert result is True

    @pytest.mark.asyncio
    async def test_send_message_failure(self):
        """Test sending message fails gracefully."""
        adapter = DingTalkAdapter()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        message = OutboundMessage(
            channel_id="dingtalk",
            content="Hello",
            recipient_id="user_123",
        )

        result = await adapter.send(message)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_access_token_cached(self):
        """Test access token is cached."""
        adapter = DingTalkAdapter()
        adapter._access_token = "cached_token"
        adapter._token_expire_at = 9999999999

        token = await adapter._get_access_token()

        assert token == "cached_token"

    @pytest.mark.asyncio
    async def test_get_access_token_fetch_new(self):
        """Test fetching new access token."""
        config = DingTalkConfig(app_key="test_key", app_secret="test_secret")
        adapter = DingTalkAdapter(config=config)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new_token",
            "expires_in": 7200,
            "errcode": 0,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        token = await adapter._get_access_token()

        assert token == "new_token"
        assert adapter._access_token == "new_token"


class TestDingTalkAdapterHealthCheck:
    """Test DingTalkAdapter health check."""

    @pytest.mark.asyncio
    async def test_health_check_webhook_success(self):
        """Test health check success via webhook."""
        config = DingTalkConfig(webhook_url="https://oapi.dingtalk.com/robot/send?access_token=test")
        adapter = DingTalkAdapter(config=config)

        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 0}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        result = await adapter.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check failure."""
        adapter = DingTalkAdapter()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection error"))
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        result = await adapter.health_check()

        assert result is False


class TestDingTalkAdapterHelpers:
    """Test DingTalkAdapter helper methods."""

    @pytest.mark.asyncio
    async def test_send_link_message(self):
        """Test sending link message."""
        config = DingTalkConfig(webhook_url="https://oapi.dingtalk.com/robot/send?access_token=test")
        adapter = DingTalkAdapter(config=config)

        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 0}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        result = await adapter.send_link(
            recipient_id="user_123",
            title="Test Link",
            text="Link description",
            message_url="https://example.com",
            pic_url="https://example.com/image.png",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_action_card_message(self):
        """Test sending action card message."""
        config = DingTalkConfig(webhook_url="https://oapi.dingtalk.com/robot/send?access_token=test")
        adapter = DingTalkAdapter(config=config)

        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 0}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        result = await adapter.send_action_card(
            recipient_id="user_123",
            title="Test Card",
            content="Card content",
            btn_title="Click Me",
            btn_url="https://example.com",
        )

        assert result is True


class TestDingTalkGatewayIntegration:
    """Test DingTalk adapter integration with MessageGateway."""

    def test_register_dingtalk_adapter(self):
        """Test registering DingTalk adapter to gateway."""
        from deskflow.channels.gateway import MessageGateway

        gateway = MessageGateway()
        adapter = DingTalkAdapter()

        gateway.register_adapter(adapter)

        retrieved = gateway.get_adapter("dingtalk")
        assert retrieved is adapter
        assert retrieved.channel_type == "dingtalk"

    def test_list_adapters_includes_dingtalk(self):
        """Test listing adapters includes DingTalk."""
        from deskflow.channels.gateway import MessageGateway

        gateway = MessageGateway()
        adapter = DingTalkAdapter()

        gateway.register_adapter(adapter)

        adapters = gateway.list_adapters()

        assert len(adapters) == 1
        assert adapters[0]["channel_type"] == "dingtalk"

    def test_unregister_dingtalk_adapter(self):
        """Test unregistering DingTalk adapter."""
        from deskflow.channels.gateway import MessageGateway

        gateway = MessageGateway()
        adapter = DingTalkAdapter()

        gateway.register_adapter(adapter)
        gateway.unregister_adapter("dingtalk")

        retrieved = gateway.get_adapter("dingtalk")
        assert retrieved is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
