"""Message gateway for unified IM message routing and dispatch.

Provides:
- Unified message interface (IMessage Protocol)
- Message router for dispatching to adapters
- Message queue for async processing
- Channel adapter registration
"""

from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


class MessageType(Enum):
    """Type of message."""

    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    VIDEO = "video"
    FILE = "file"
    LINK = "link"
    SYSTEM = "system"


class MessageStatus(Enum):
    """Message processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"


@runtime_checkable
class IMessage(Protocol):
    """Protocol for unified message interface."""

    @property
    def channel_id(self) -> str:
        """Return the channel ID where message originated."""
        ...

    @property
    def content(self) -> str:
        """Return the message content."""
        ...

    @property
    def sender_id(self) -> str:
        """Return the sender's ID."""
        ...

    @property
    def message_id(self) -> str:
        """Return unique message ID."""
        ...

    @property
    def message_type(self) -> MessageType:
        """Return the message type."""
        ...

    @property
    def timestamp(self) -> datetime:
        """Return message timestamp."""
        ...

    @property
    def metadata(self) -> dict[str, Any]:
        """Return additional message metadata."""
        ...


@dataclass
class BaseMessage:
    """Base implementation of IMessage."""

    _channel_id: str
    _content: str
    _sender_id: str
    _message_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    _message_type: MessageType = MessageType.TEXT
    _timestamp: datetime = field(default_factory=datetime.now)
    _metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def channel_id(self) -> str:
        return self._channel_id

    @property
    def content(self) -> str:
        return self._content

    @property
    def sender_id(self) -> str:
        return self._sender_id

    @property
    def message_id(self) -> str:
        return self._message_id

    @property
    def message_type(self) -> MessageType:
        return self._message_type

    @property
    def timestamp(self) -> datetime:
        return self._timestamp

    @property
    def metadata(self) -> dict[str, Any]:
        return self._metadata

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "message_id": self._message_id,
            "channel_id": self._channel_id,
            "sender_id": self._sender_id,
            "content": self._content,
            "message_type": self._message_type.value,
            "timestamp": self._timestamp.isoformat(),
            "metadata": self._metadata,
        }


@dataclass
class OutboundMessage:
    """Message to be sent to a channel."""

    channel_id: str
    content: str
    recipient_id: str
    message_type: MessageType = MessageType.TEXT
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "channel_id": self.channel_id,
            "recipient_id": self.recipient_id,
            "content": self.content,
            "message_type": self.message_type.value,
            "metadata": self.metadata,
        }


class ChannelAdapter(ABC):
    """Base class for channel adapters."""

    def __init__(self, channel_id: str, config: dict[str, Any] | None = None):
        self._channel_id = channel_id
        self._config = config or {}
        self._enabled = True

    @property
    def channel_id(self) -> str:
        return self._channel_id

    @property
    def channel_type(self) -> str:
        """Return the channel type (e.g., 'feishu', 'wework', 'dingtalk')."""
        raise NotImplementedError

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    @abstractmethod
    async def send(self, message: OutboundMessage) -> bool:
        """Send a message to this channel.

        Args:
            message: Message to send

        Returns:
            True if sent successfully, False otherwise
        """
        pass

    @abstractmethod
    async def parse_message(self, raw_data: dict[str, Any]) -> BaseMessage:
        """Parse raw data into a BaseMessage.

        Args:
            raw_data: Raw message data from the channel

        Returns:
            Parsed BaseMessage instance
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the channel connection is healthy.

        Returns:
            True if healthy, False otherwise
        """
        pass


class MessageQueue:
    """Async message queue for processing messages."""

    def __init__(self, max_size: int = 1000):
        self._queue: asyncio.Queue[BaseMessage] = asyncio.Queue(maxsize=max_size)
        self._processors: list[asyncio.Task] = []
        self._running = False
        self._handlers: list[callable] = []

    async def start(self, num_workers: int = 3) -> None:
        """Start message queue processing."""
        if self._running:
            return

        self._running = True
        logger.info("message_queue_started", workers=num_workers)

        # Start worker tasks
        for i in range(num_workers):
            task = asyncio.create_task(self._worker(f"worker-{i}"))
            self._processors.append(task)

    async def stop(self) -> None:
        """Stop message queue processing."""
        self._running = False

        # Wait for workers to finish
        for task in self._processors:
            task.cancel()

        await asyncio.gather(*self._processors, return_exceptions=True)
        self._processors.clear()

        logger.info("message_queue_stopped")

    async def put(self, message: BaseMessage) -> None:
        """Add a message to the queue."""
        await self._queue.put(message)
        logger.debug("message_queued", message_id=message.message_id)

    def put_nowait(self, message: BaseMessage) -> None:
        """Add a message to the queue without waiting."""
        self._queue.put_nowait(message)

    def register_handler(self, handler: callable) -> None:
        """Register a message handler."""
        self._handlers.append(handler)

    async def _worker(self, name: str) -> None:
        """Worker coroutine to process messages."""
        while self._running:
            try:
                message = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            try:
                await self._process_message(message)
            except Exception as e:
                logger.error(
                    "message_processing_failed",
                    worker=name,
                    message_id=message.message_id,
                    error=str(e),
                )
            finally:
                self._queue.task_done()

    async def _process_message(self, message: BaseMessage) -> None:
        """Process a single message through registered handlers."""
        logger.debug("message_processing", message_id=message.message_id)

        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.warning(
                    "message_handler_failed",
                    message_id=message.message_id,
                    handler=handler.__name__,
                    error=str(e),
                )

        logger.debug("message_processed", message_id=message.message_id)

    @property
    def pending_count(self) -> int:
        """Return number of pending messages in queue."""
        return self._queue.qsize()


class MessageGateway:
    """Main message gateway for routing and dispatching messages."""

    def __init__(self):
        self._adapters: dict[str, ChannelAdapter] = {}
        self._queue = MessageQueue()
        self._running = False

    async def start(self, num_workers: int = 3) -> None:
        """Start the message gateway."""
        self._running = True
        await self._queue.start(num_workers)
        logger.info("message_gateway_started")

    async def stop(self) -> None:
        """Stop the message gateway."""
        self._running = False
        await self._queue.stop()
        logger.info("message_gateway_stopped")

    def register_adapter(self, adapter: ChannelAdapter) -> None:
        """Register a channel adapter."""
        self._adapters[adapter.channel_id] = adapter
        logger.info(
            "channel_adapter_registered",
            channel_id=adapter.channel_id,
            channel_type=adapter.channel_type,
        )

    def unregister_adapter(self, channel_id: str) -> None:
        """Unregister a channel adapter."""
        if channel_id in self._adapters:
            del self._adapters[channel_id]
            logger.info("channel_adapter_unregistered", channel_id=channel_id)

    def get_adapter(self, channel_id: str) -> ChannelAdapter | None:
        """Get a registered adapter by channel ID."""
        return self._adapters.get(channel_id)

    def list_adapters(self) -> list[dict[str, Any]]:
        """List all registered adapters."""
        return [
            {
                "channel_id": adapter.channel_id,
                "channel_type": adapter.channel_type,
                "enabled": adapter.enabled,
            }
            for adapter in self._adapters.values()
        ]

    async def route_message(self, msg: BaseMessage) -> None:
        """Route a message to the appropriate handler.

        Args:
            msg: Message to route
        """
        if not self._running:
            logger.warning("gateway_not_running")
            return

        await self._queue.put(msg)

    def route_message_nowait(self, msg: BaseMessage) -> None:
        """Route a message without waiting."""
        if not self._running:
            logger.warning("gateway_not_running")
            return

        self._queue.put_nowait(msg)

    async def broadcast(
        self,
        msg: OutboundMessage,
        channels: list[str] | None = None,
    ) -> dict[str, bool]:
        """Broadcast a message to multiple channels.

        Args:
            msg: Message to broadcast
            channels: List of channel IDs to broadcast to.
                      If None, broadcast to all enabled channels.

        Returns:
            Dict mapping channel_id to send status
        """
        results = {}

        target_channels = channels or [
            cid for cid, adapter in self._adapters.items()
            if adapter.enabled
        ]

        for channel_id in target_channels:
            adapter = self._adapters.get(channel_id)
            if adapter and adapter.enabled:
                try:
                    success = await adapter.send(msg)
                    results[channel_id] = success
                except Exception as e:
                    logger.error(
                        "broadcast_failed",
                        channel_id=channel_id,
                        error=str(e),
                    )
                    results[channel_id] = False
            else:
                results[channel_id] = False

        return results

    def register_handler(self, handler: callable) -> None:
        """Register a message handler."""
        self._queue.register_handler(handler)

    async def health_check(self) -> dict[str, bool]:
        """Check health of all registered adapters.

        Returns:
            Dict mapping channel_id to health status
        """
        results = {}
        for channel_id, adapter in self._adapters.items():
            try:
                healthy = await adapter.health_check()
                results[channel_id] = healthy
            except Exception as e:
                logger.error(
                    "health_check_failed",
                    channel_id=channel_id,
                    error=str(e),
                )
                results[channel_id] = False

        return results

    @property
    def pending_messages(self) -> int:
        """Return number of pending messages."""
        return self._queue.pending_count

    @property
    def adapter_count(self) -> int:
        """Return number of registered adapters."""
        return len(self._adapters)


# Global gateway instance
_gateway: MessageGateway | None = None


def get_gateway() -> MessageGateway:
    """Get or create global message gateway."""
    global _gateway
    if _gateway is None:
        _gateway = MessageGateway()
    return _gateway


async def start_gateway(num_workers: int = 3) -> MessageGateway:
    """Start the global message gateway."""
    gateway = get_gateway()
    await gateway.start(num_workers)
    return gateway


async def stop_gateway() -> None:
    """Stop the global message gateway."""
    gateway = get_gateway()
    await gateway.stop()


def register_adapter(adapter: ChannelAdapter) -> None:
    """Register a channel adapter with the global gateway."""
    gateway = get_gateway()
    gateway.register_adapter(adapter)
