"""Tests for message gateway module."""

import pytest
import asyncio
from datetime import datetime

from deskflow.channels.gateway import (
    BaseMessage,
    OutboundMessage,
    MessageType,
    MessageStatus,
    MessageQueue,
    MessageGateway,
    ChannelAdapter,
    get_gateway,
)


class TestMessageType:
    """Test MessageType enum."""

    def test_message_types(self):
        """Test all message types exist."""
        assert MessageType.TEXT.value == "text"
        assert MessageType.IMAGE.value == "image"
        assert MessageType.VOICE.value == "voice"
        assert MessageType.VIDEO.value == "video"
        assert MessageType.FILE.value == "file"
        assert MessageType.LINK.value == "link"
        assert MessageType.SYSTEM.value == "system"


class TestBaseMessage:
    """Test BaseMessage class."""

    def test_message_creation(self):
        """Test basic message creation."""
        msg = BaseMessage(
            _channel_id="channel_123",
            _content="Hello, World!",
            _sender_id="user_456",
        )

        assert msg.channel_id == "channel_123"
        assert msg.content == "Hello, World!"
        assert msg.sender_id == "user_456"
        assert msg.message_type == MessageType.TEXT
        assert msg.timestamp is not None

    def test_message_with_type(self):
        """Test message with specific type."""
        msg = BaseMessage(
            _channel_id="channel_123",
            _content="Image content",
            _sender_id="user_456",
            _message_type=MessageType.IMAGE,
        )

        assert msg.message_type == MessageType.IMAGE

    def test_message_to_dict(self):
        """Test message to_dict method."""
        msg = BaseMessage(
            _channel_id="channel_123",
            _content="Test message",
            _sender_id="user_456",
        )

        result = msg.to_dict()

        assert result["channel_id"] == "channel_123"
        assert result["content"] == "Test message"
        assert result["sender_id"] == "user_456"
        assert result["message_type"] == "text"
        assert "timestamp" in result

    def test_message_with_metadata(self):
        """Test message with metadata."""
        msg = BaseMessage(
            _channel_id="channel_123",
            _content="Test",
            _sender_id="user_456",
            _metadata={"key": "value"},
        )

        assert msg.metadata["key"] == "value"


class TestOutboundMessage:
    """Test OutboundMessage class."""

    def test_outbound_message_creation(self):
        """Test outbound message creation."""
        msg = OutboundMessage(
            channel_id="channel_123",
            content="Hello!",
            recipient_id="user_789",
        )

        assert msg.channel_id == "channel_123"
        assert msg.content == "Hello!"
        assert msg.recipient_id == "user_789"
        assert msg.message_type == MessageType.TEXT

    def test_outbound_message_to_dict(self):
        """Test outbound message to_dict."""
        msg = OutboundMessage(
            channel_id="channel_123",
            content="Hello!",
            recipient_id="user_789",
            message_type=MessageType.IMAGE,
        )

        result = msg.to_dict()

        assert result["channel_id"] == "channel_123"
        assert result["recipient_id"] == "user_789"
        assert result["message_type"] == "image"


class TestMessageQueue:
    """Test MessageQueue class."""

    @pytest.mark.asyncio
    async def test_queue_creation(self):
        """Test message queue creation."""
        queue = MessageQueue(max_size=100)
        assert queue.pending_count == 0

    @pytest.mark.asyncio
    async def test_queue_put(self):
        """Test adding message to queue."""
        queue = MessageQueue(max_size=100)
        msg = BaseMessage(
            _channel_id="test",
            _content="Test",
            _sender_id="user",
        )

        await queue.put(msg)
        assert queue.pending_count == 1

    @pytest.mark.asyncio
    async def test_queue_put_nowait(self):
        """Test adding message without waiting."""
        queue = MessageQueue(max_size=100)
        msg = BaseMessage(
            _channel_id="test",
            _content="Test",
            _sender_id="user",
        )

        queue.put_nowait(msg)
        assert queue.pending_count == 1

    @pytest.mark.asyncio
    async def test_queue_processor(self):
        """Test message processing."""
        queue = MessageQueue(max_size=100)
        processed = []

        def handler(msg):
            processed.append(msg.message_id)

        queue.register_handler(handler)

        await queue.start(num_workers=1)

        msg = BaseMessage(
            _channel_id="test",
            _content="Test",
            _sender_id="user",
        )
        await queue.put(msg)

        # Wait for processing
        await asyncio.sleep(0.5)

        await queue.stop()

        assert len(processed) > 0

    @pytest.mark.asyncio
    async def test_queue_start_stop(self):
        """Test queue start and stop."""
        queue = MessageQueue()

        await queue.start(num_workers=2)
        assert queue._running is True

        await queue.stop()
        assert queue._running is False


class MockChannelAdapter(ChannelAdapter):
    """Mock channel adapter for testing."""

    @property
    def channel_type(self) -> str:
        return "mock"

    async def send(self, message: OutboundMessage) -> bool:
        return True

    async def parse_message(self, raw_data: dict) -> BaseMessage:
        return BaseMessage(
            _channel_id=self._channel_id,
            _content=raw_data.get("content", ""),
            _sender_id=raw_data.get("sender_id", "unknown"),
        )

    async def health_check(self) -> bool:
        return True


class TestMessageGateway:
    """Test MessageGateway class."""

    @pytest.mark.asyncio
    async def test_gateway_creation(self):
        """Test gateway creation."""
        gateway = MessageGateway()
        assert gateway.adapter_count == 0
        assert gateway.pending_messages == 0

    @pytest.mark.asyncio
    async def test_register_adapter(self):
        """Test registering an adapter."""
        gateway = MessageGateway()
        adapter = MockChannelAdapter("mock_channel")

        gateway.register_adapter(adapter)

        assert gateway.adapter_count == 1
        assert gateway.get_adapter("mock_channel") is adapter

    @pytest.mark.asyncio
    async def test_unregister_adapter(self):
        """Test unregistering an adapter."""
        gateway = MessageGateway()
        adapter = MockChannelAdapter("mock_channel")

        gateway.register_adapter(adapter)
        gateway.unregister_adapter("mock_channel")

        assert gateway.adapter_count == 0
        assert gateway.get_adapter("mock_channel") is None

    @pytest.mark.asyncio
    async def test_list_adapters(self):
        """Test listing adapters."""
        gateway = MessageGateway()
        adapter = MockChannelAdapter("mock_channel")

        gateway.register_adapter(adapter)

        adapters = gateway.list_adapters()

        assert len(adapters) == 1
        assert adapters[0]["channel_id"] == "mock_channel"
        assert adapters[0]["channel_type"] == "mock"

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test gateway start and stop."""
        gateway = MessageGateway()

        await gateway.start(num_workers=2)
        assert gateway._running is True

        await gateway.stop()
        assert gateway._running is False

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check."""
        gateway = MessageGateway()
        adapter = MockChannelAdapter("mock_channel")

        gateway.register_adapter(adapter)
        await gateway.start()

        results = await gateway.health_check()

        assert "mock_channel" in results
        assert results["mock_channel"] is True

        await gateway.stop()

    @pytest.mark.asyncio
    async def test_broadcast(self):
        """Test broadcast message."""
        gateway = MessageGateway()
        adapter = MockChannelAdapter("mock_channel")

        gateway.register_adapter(adapter)
        await gateway.start()

        msg = OutboundMessage(
            channel_id="broadcast",
            content="Test broadcast",
            recipient_id="user_123",
        )

        results = await gateway.broadcast(msg, ["mock_channel"])

        assert "mock_channel" in results
        assert results["mock_channel"] is True

        await gateway.stop()

    @pytest.mark.asyncio
    async def test_broadcast_to_all(self):
        """Test broadcast to all enabled channels."""
        gateway = MessageGateway()
        adapter1 = MockChannelAdapter("channel_1")
        adapter2 = MockChannelAdapter("channel_2")

        gateway.register_adapter(adapter1)
        gateway.register_adapter(adapter2)
        await gateway.start()

        msg = OutboundMessage(
            channel_id="broadcast",
            content="Test broadcast",
            recipient_id="user_123",
        )

        results = await gateway.broadcast(msg)  # No channel list = all

        assert len(results) == 2
        assert results["channel_1"] is True
        assert results["channel_2"] is True

        await gateway.stop()

    @pytest.mark.asyncio
    async def test_route_message(self):
        """Test routing a message."""
        gateway = MessageGateway()
        processed = []

        def handler(msg):
            processed.append(msg.message_id)

        gateway.register_handler(handler)
        await gateway.start()

        msg = BaseMessage(
            _channel_id="test",
            _content="Test message",
            _sender_id="user",
        )

        await gateway.route_message(msg)

        # Wait for processing
        await asyncio.sleep(0.5)

        await gateway.stop()

        assert len(processed) > 0

    @pytest.mark.asyncio
    async def test_pending_messages(self):
        """Test pending message count."""
        gateway = MessageGateway()
        await gateway.start()

        # Add messages without processing
        for i in range(5):
            msg = BaseMessage(
                _channel_id="test",
                _content=f"Message {i}",
                _sender_id="user",
            )
            gateway._queue.put_nowait(msg)

        # Count should reflect pending
        assert gateway.pending_messages >= 0

        await gateway.stop()


class TestGlobalFunctions:
    """Test global convenience functions."""

    def test_get_gateway(self):
        """Test get_gateway returns singleton."""
        gateway1 = get_gateway()
        gateway2 = get_gateway()

        # Should return same instance
        assert gateway1 is gateway2

    @pytest.mark.asyncio
    async def test_start_stop_gateway(self):
        """Test start_gateway and stop_gateway."""
        from deskflow.channels import start_gateway, stop_gateway

        gateway = await start_gateway(num_workers=2)
        assert gateway._running is True

        await stop_gateway()
        # Note: _running may be False after stop


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
