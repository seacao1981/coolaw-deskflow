"""Tests for WeCom (Enterprise WeChat) channel adapter."""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from deskflow.channels.wework import (
    WeComAdapter,
    WeComConfig,
    WeComMessage,
    _pkcs7_pad,
    _pkcs7_unpad,
)
from deskflow.channels.gateway import OutboundMessage, MessageType


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TestPKCS7Padding:
    """Test PKCS7 padding functions."""

    def test_pkcs7_pad(self):
        """Test PKCS7 padding."""
        data = b"Hello World"
        padded = _pkcs7_pad(data, 32)

        assert len(padded) % 32 == 0
        assert padded[-1] == 21  # Padding length

    def test_pkcs7_unpad(self):
        """Test PKCS7 unpadding."""
        data = b"Hello World" + bytes([21] * 21)
        unpadded = _pkcs7_unpad(data)

        assert unpadded == b"Hello World"

    def test_pad_unpad_roundtrip(self):
        """Test padding/unpadding roundtrip."""
        original = b"Test message for padding"
        padded = _pkcs7_pad(original, 32)
        unpadded = _pkcs7_unpad(padded)

        assert unpadded == original


class TestWeComConfig:
    """Test WeComConfig class."""

    def test_default_config(self):
        """Test default configuration."""
        config = WeComConfig()

        assert config.corp_id == ""
        assert config.agent_id == ""
        assert config.secret == ""
        assert config.token == ""
        assert config.encoding_aes_key == ""

    def test_config_with_values(self):
        """Test configuration with values."""
        config = WeComConfig(
            corp_id="test_corp",
            agent_id="1000001",
            secret="test_secret",
        )

        assert config.corp_id == "test_corp"
        assert config.agent_id == "1000001"

    def test_config_to_dict(self):
        """Test config to_dict method."""
        config = WeComConfig(corp_id="test_corp", secret="test_secret")
        result = config.to_dict()

        assert result["corp_id"] == "test_corp"
        assert result["secret"] == "test_secret"

    def test_config_from_dict(self):
        """Test config from_dict method."""
        data = {
            "corp_id": "restored_corp",
            "agent_id": "1000002",
            "secret": "restored_secret",
        }

        config = WeComConfig.from_dict(data)

        assert config.corp_id == "restored_corp"
        assert config.agent_id == "1000002"


class TestWeComMessage:
    """Test WeComMessage class."""

    def test_message_creation(self):
        """Test basic message creation."""
        msg = WeComMessage(_content="Hello", _sender_id="user_123")

        assert msg.content == "Hello"
        assert msg.sender_id == "user_123"
        assert msg.channel_id == "wecom"
        assert msg.message_type == MessageType.TEXT

    def test_message_with_msg_id(self):
        """Test message with WeCom message ID."""
        msg = WeComMessage(
            _content="Hello",
            _sender_id="user_123",
            msg_id="msg_123456",
        )

        assert msg.msg_id == "msg_123456"
        assert msg.message_id == "msg_123456"

    def test_message_to_dict(self):
        """Test message to_dict method."""
        msg = WeComMessage(
            _content="Test",
            _sender_id="user_456",
            agent_id="1000001",
        )

        result = msg.to_dict()

        assert result["content"] == "Test"
        assert result["sender_id"] == "user_456"


class TestWeComAdapter:
    """Test WeComAdapter class."""

    def test_adapter_creation(self):
        """Test adapter creation."""
        config = WeComConfig(corp_id="test_corp")
        adapter = WeComAdapter(config=config)

        assert adapter.channel_type == "wecom"
        assert adapter.channel_id == "wecom"
        assert adapter.enabled is True

    def test_adapter_enable_disable(self):
        """Test adapter enable/disable."""
        adapter = WeComAdapter()

        adapter.disable()
        assert adapter.enabled is False

        adapter.enable()
        assert adapter.enabled is True

    def test_adapter_to_dict(self):
        """Test adapter to_dict method."""
        config = WeComConfig(corp_id="test_corp", secret="test_secret")
        adapter = WeComAdapter(config=config)

        result = adapter.to_dict()

        assert result["corp_id"] == "test_corp"
        assert result["secret"] == "test_secret"

    def test_adapter_from_dict(self):
        """Test adapter from_dict method."""
        data = {
            "corp_id": "restored_corp",
            "secret": "restored_secret",
            "channel_id": "wecom_custom",
        }

        adapter = WeComAdapter.from_dict(data)

        assert adapter.to_dict()["corp_id"] == "restored_corp"
        assert adapter.channel_id == "wecom_custom"

    def test_parse_wecom_message_type(self):
        """Test WeCom message type parsing."""
        adapter = WeComAdapter()

        assert adapter._parse_wecom_message_type("text") == MessageType.TEXT
        assert adapter._parse_wecom_message_type("markdown") == MessageType.TEXT
        assert adapter._parse_wecom_message_type("image") == MessageType.IMAGE
        assert adapter._parse_wecom_message_type("voice") == MessageType.VOICE
        assert adapter._parse_wecom_message_type("video") == MessageType.VIDEO
        assert adapter._parse_wecom_message_type("file") == MessageType.FILE
        assert adapter._parse_wecom_message_type("link") == MessageType.LINK
        assert adapter._parse_wecom_message_type("textcard") == MessageType.LINK
        assert adapter._parse_wecom_message_type("unknown") == MessageType.TEXT


class TestWeComAdapterParseMessage:
    """Test WeComAdapter message parsing."""

    @pytest.mark.asyncio
    async def test_parse_text_message(self):
        """Test parsing text message."""
        adapter = WeComAdapter()

        raw_data = {
            "MsgType": "text",
            "Content": "Hello World",
            "FromUserName": "user_123",
            "ToUserName": "corp_abc",
            "CreateTime": 1708000000,
            "MsgId": "msg_456",
            "AgentID": 1000001,
        }

        msg = await adapter.parse_message(raw_data)

        assert msg.content == "Hello World"
        assert msg.sender_id == "user_123"
        assert msg.msg_id == "msg_456"
        assert msg.message_type == MessageType.TEXT

    @pytest.mark.asyncio
    async def test_parse_markdown_message(self):
        """Test parsing markdown message."""
        adapter = WeComAdapter()

        raw_data = {
            "MsgType": "markdown",
            "Content": "# Heading\n**Bold** text",
            "FromUserName": "user_md",
            "CreateTime": 1708000000,
        }

        msg = await adapter.parse_message(raw_data)

        assert "# Heading" in msg.content
        assert msg.message_type == MessageType.TEXT

    @pytest.mark.asyncio
    async def test_parse_event(self):
        """Test parsing event message."""
        adapter = WeComAdapter()

        raw_data = {
            "MsgType": "event",
            "Event": "subscribe",
            "FromUserName": "user_event",
            "CreateTime": 1708000000,
        }

        msg = await adapter.parse_message(raw_data)

        assert msg.content == "event:subscribe"
        assert msg.message_type == MessageType.SYSTEM
        assert msg.metadata["event"] == "subscribe"

    @pytest.mark.asyncio
    async def test_parse_xml(self):
        """Test parsing XML message."""
        adapter = WeComAdapter()

        xml_str = """
        <xml>
            <MsgType>text</MsgType>
            <Content>XML Content</Content>
            <FromUserName>user_xml</FromUserName>
        </xml>
        """

        result = adapter._parse_xml(xml_str)

        assert result["MsgType"] == "text"
        assert result["Content"] == "XML Content"
        assert result["FromUserName"] == "user_xml"


class TestWeComAdapterSignature:
    """Test WeComAdapter signature verification."""

    def test_verify_signature_skip_no_token(self):
        """Test signature verification skips when no token configured."""
        adapter = WeComAdapter()

        result = adapter._verify_signature(
            msg_signature="any_sig",
            timestamp="1234567890",
            nonce="test_nonce",
        )

        assert result is True

    def test_verify_signature_no_echo(self):
        """Test signature verification without echo_str."""
        config = WeComConfig(token="secret_token")
        adapter = WeComAdapter(config=config)

        # Create valid signature
        import hashlib
        sorted_list = sorted(["secret_token", "1234567890", "test_nonce"])
        signature = hashlib.sha1("".join(sorted_list).encode()).hexdigest()

        result = adapter._verify_signature(
            msg_signature=signature,
            timestamp="1234567890",
            nonce="test_nonce",
        )

        assert result is True

    def test_verify_signature_invalid(self):
        """Test signature verification with invalid signature."""
        config = WeComConfig(token="secret_token")
        adapter = WeComAdapter(config=config)

        result = adapter._verify_signature(
            msg_signature="invalid_signature",
            timestamp="1234567890",
            nonce="test_nonce",
        )

        assert result is False


class TestWeComAdapterSend:
    """Test WeComAdapter message sending."""

    @pytest.mark.asyncio
    async def test_send_text_message_success(self):
        """Test sending text message successfully."""
        adapter = WeComAdapter(config=WeComConfig(agent_id="1000001"))

        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._access_token = "mock_token"
        adapter._token_expire_at = 9999999999
        adapter._client = mock_client

        message = OutboundMessage(
            channel_id="wecom",
            content="Hello",
            recipient_id="user_123",
        )

        result = await adapter.send(message)

        assert result is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_text_message_failure(self):
        """Test sending text message fails gracefully."""
        adapter = WeComAdapter()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._access_token = "mock_token"
        adapter._token_expire_at = 9999999999
        adapter._client = mock_client

        message = OutboundMessage(
            channel_id="wecom",
            content="Hello",
            recipient_id="user_123",
        )

        result = await adapter.send(message)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_access_token_cached(self):
        """Test access token is cached."""
        adapter = WeComAdapter()
        adapter._access_token = "cached_token"
        adapter._token_expire_at = 9999999999

        token = await adapter._get_access_token()

        assert token == "cached_token"

    @pytest.mark.asyncio
    async def test_get_access_token_fetch_new(self):
        """Test fetching new access token."""
        adapter = WeComAdapter(
            config=WeComConfig(corp_id="test_corp", secret="test_secret")
        )

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


class TestWeComAdapterHealthCheck:
    """Test WeComAdapter health check."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test health check success."""
        adapter = WeComAdapter(config=WeComConfig(agent_id="1000001"))

        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 0}
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
        adapter = WeComAdapter()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection error"))
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        adapter._client = mock_client

        result = await adapter.health_check()

        assert result is False


class TestWeComGatewayIntegration:
    """Test WeCom adapter integration with MessageGateway."""

    def test_register_wecom_adapter(self):
        """Test registering WeCom adapter to gateway."""
        from deskflow.channels.gateway import MessageGateway

        gateway = MessageGateway()
        adapter = WeComAdapter()

        gateway.register_adapter(adapter)

        retrieved = gateway.get_adapter("wecom")
        assert retrieved is adapter
        assert retrieved.channel_type == "wecom"

    def test_list_adapters_includes_wecom(self):
        """Test listing adapters includes WeCom."""
        from deskflow.channels.gateway import MessageGateway

        gateway = MessageGateway()
        adapter = WeComAdapter()

        gateway.register_adapter(adapter)

        adapters = gateway.list_adapters()

        assert len(adapters) == 1
        assert adapters[0]["channel_type"] == "wecom"

    def test_unregister_wecom_adapter(self):
        """Test unregistering WeCom adapter."""
        from deskflow.channels.gateway import MessageGateway

        gateway = MessageGateway()
        adapter = WeComAdapter()

        gateway.register_adapter(adapter)
        gateway.unregister_adapter("wecom")

        retrieved = gateway.get_adapter("wecom")
        assert retrieved is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
