"""ZeroMQ-based message bus for distributed multi-agent communication.

Features:
- PUB/SUB pattern for broadcast messages
- REQ/REP pattern for request/response
- Dealer/Router pattern for async request handling
- Automatic reconnection
- Message serialization with JSON
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

import zmq
import zmq.asyncio

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


class MessageType(str, Enum):
    """Types of messages that can be sent."""

    PUBLISH = "publish"
    REQUEST = "request"
    RESPONSE = "response"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


@dataclass
class ZMQMessage:
    """ZeroMQ message wrapper."""

    type: MessageType
    topic: str
    payload: Any
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reply_to: str | None = None
    timestamp: float = field(default_factory=asyncio.get_event_loop().time)

    def to_bytes(self) -> bytes:
        """Serialize message to bytes."""
        data = {
            "type": self.type.value,
            "topic": self.topic,
            "payload": self.payload,
            "message_id": self.message_id,
            "reply_to": self.reply_to,
            "timestamp": self.timestamp,
        }
        return json.dumps(data).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> ZMQMessage:
        """Deserialize message from bytes."""
        parsed = json.loads(data.decode("utf-8"))
        return cls(
            type=MessageType(parsed["type"]),
            topic=parsed["topic"],
            payload=parsed["payload"],
            message_id=parsed["message_id"],
            reply_to=parsed.get("reply_to"),
            timestamp=parsed.get("timestamp", asyncio.get_event_loop().time),
        )


class ZMQPublisher:
    """ZeroMQ PUB/SUB publisher for broadcast messages.

    Usage:
        publisher = ZMQPublisher(port=5555)
        await publisher.start()
        await publisher.publish("task_complete", {"task_id": "123"})
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        pub_port: int = 5555,
        topic_prefix: str = "deskflow",
    ) -> None:
        self._host = host
        self._pub_port = pub_port
        self._topic_prefix = topic_prefix
        self._context = zmq.asyncio.Context()
        self._socket: zmq.asyncio.Socket | None = None
        self._running = False

    async def start(self) -> None:
        """Start the publisher."""
        self._socket = self._context.socket(zmq.PUB)
        self._socket.setsockopt(zmq.SNDHWM, 1000)  # High water mark
        self._socket.setsockopt(zmq.LINGER, 0)  # Don't block on close
        bind_addr = f"tcp://{self._host}:{self._pub_port}"
        self._socket.bind(bind_addr)
        self._running = True
        logger.info("zmq_publisher_started", address=bind_addr)

    async def stop(self) -> None:
        """Stop the publisher."""
        self._running = False
        if self._socket:
            self._socket.close(linger=0)
        self._context.term()
        logger.info("zmq_publisher_stopped")

    async def publish(self, topic: str, payload: Any) -> None:
        """Publish a message to a topic.

        Args:
            topic: Topic name (will be prefixed)
            payload: Message payload (must be JSON serializable)
        """
        if not self._socket:
            raise RuntimeError("Publisher not started")

        full_topic = f"{self._topic_prefix}/{topic}"
        message = ZMQMessage(
            type=MessageType.PUBLISH,
            topic=full_topic,
            payload=payload,
        )
        await self._socket.send_multipart([full_topic.encode(), message.to_bytes()])
        logger.debug("zmq_message_published", topic=full_topic)


class ZMQSubscriber:
    """ZeroMQ PUB/SUB subscriber for receiving broadcast messages.

    Usage:
        subscriber = ZMQSubscriber(port=5555, topics=["task_*"])
        await subscriber.start()
        subscriber.subscribe("task_complete", callback)
        await subscriber.run()
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        pub_port: int = 5555,
        topics: list[str] | None = None,
    ) -> None:
        self._host = host
        self._pub_port = pub_port
        self._topics = topics or [""]
        self._context = zmq.asyncio.Context()
        self._socket: zmq.asyncio.Socket | None = None
        self._callbacks: dict[str, list[Callable]] = {}
        self._running = False

    def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to a topic with a callback.

        Args:
            topic: Topic pattern (supports wildcards like "task_*")
            callback: Function to call when message received
        """
        if topic not in self._callbacks:
            self._callbacks[topic] = []
        self._callbacks[topic].append(callback)
        logger.debug("zmq_subscriber_callback_added", topic=topic)

    async def start(self) -> None:
        """Start the subscriber."""
        self._socket = self._context.socket(zmq.SUB)
        self._socket.setsockopt(zmq.RCVHWM, 1000)
        self._socket.setsockopt(zmq.LINGER, 0)
        connect_addr = f"tcp://{self._host}:{self._pub_port}"
        self._socket.connect(connect_addr)

        # Subscribe to topics
        for topic in self._topics:
            self._socket.setsockopt_string(zmq.SUBSCRIBE, topic)

        self._running = True
        logger.info("zmq_subscriber_started", address=connect_addr)

    async def stop(self) -> None:
        """Stop the subscriber."""
        self._running = False
        if self._socket:
            self._socket.close(linger=0)
        self._context.term()
        logger.info("zmq_subscriber_stopped")

    async def run(self) -> None:
        """Run the subscriber loop."""
        if not self._socket:
            raise RuntimeError("Subscriber not started")

        while self._running:
            try:
                topic, data = await self._socket.recv_multipart()
                message = ZMQMessage.from_bytes(data)
                await self._dispatch_message(topic.decode(), message)
            except Exception as e:
                logger.error("zmq_subscriber_error", error=str(e))
                await asyncio.sleep(0.1)

    async def _dispatch_message(self, topic: str, message: ZMQMessage) -> None:
        """Dispatch message to matching callbacks."""
        for pattern, callbacks in self._callbacks.items():
            if self._matches_pattern(topic, pattern):
                for callback in callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(message.payload)
                        else:
                            callback(message.payload)
                    except Exception as e:
                        logger.error("zmq_callback_error", error=str(e))

    def _dispatch_message_sync(self, topic: str, message: ZMQMessage) -> None:
        """Dispatch message to matching callbacks (synchronous, non-await)."""
        for pattern, callbacks in self._callbacks.items():
            if self._matches_pattern(topic, pattern):
                for callback in callbacks:
                    try:
                        # Don't await - just call directly
                        if asyncio.iscoroutinefunction(callback):
                            # Schedule async callback but don't wait
                            asyncio.create_task(callback(message.payload))
                        else:
                            callback(message.payload)
                    except Exception as e:
                        logger.error("zmq_callback_error", error=str(e))

    def _matches_pattern(self, topic: str, pattern: str) -> bool:
        """Check if topic matches pattern (supports * wildcard)."""
        if pattern == "":
            return True
        if pattern.endswith("*"):
            return topic.startswith(pattern[:-1])
        return topic == pattern


class ZMQRequester:
    """ZeroMQ REQ/REP requester for synchronous requests.

    Usage:
        requester = ZMQRequester(port=5556)
        await requester.start()
        response = await requester.request("get_status", {"worker_id": "1"})
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        rep_port: int = 5556,
        timeout: float = 30.0,
    ) -> None:
        self._host = host
        self._rep_port = rep_port
        self._timeout = timeout
        self._context = zmq.asyncio.Context()
        self._socket: zmq.asyncio.Socket | None = None
        self._pending: dict[str, asyncio.Future] = {}

    async def start(self) -> None:
        """Start the requester."""
        self._socket = self._context.socket(zmq.REQ)
        self._socket.setsockopt(zmq.RCVTIMEO, int(self._timeout * 1000))
        self._socket.setsockopt(zmq.LINGER, 0)
        connect_addr = f"tcp://{self._host}:{self._rep_port}"
        self._socket.connect(connect_addr)
        logger.info("zmq_requester_started", address=connect_addr)

    async def stop(self) -> None:
        """Stop the requester."""
        if self._socket:
            self._socket.close(linger=0)
        self._context.term()
        logger.info("zmq_requester_stopped")

    async def request(self, method: str, payload: Any) -> Any:
        """Send a request and wait for response.

        Args:
            method: Method name
            payload: Request payload

        Returns:
            Response payload

        Raises:
            asyncio.TimeoutError: If request times out
        """
        if not self._socket:
            raise RuntimeError("Requester not started")

        request_id = str(uuid.uuid4())
        message = ZMQMessage(
            type=MessageType.REQUEST,
            topic=method,
            payload=payload,
            message_id=request_id,
        )

        await self._socket.send(message.to_bytes())

        try:
            data = await self._socket.recv()
            response = ZMQMessage.from_bytes(data)
            return response.payload
        except zmq.error.Again:
            logger.warning("zmq_request_timeout", request_id=request_id)
            raise asyncio.TimeoutError(f"Request {request_id} timed out")


class ZMQResponder:
    """ZeroMQ REQ/REP responder for handling requests.

    Usage:
        responder = ZMQResponder(port=5556)
        responder.register_handler("get_status", handle_status)
        await responder.start()
        await responder.serve()
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        rep_port: int = 5556,
    ) -> None:
        self._host = host
        self._rep_port = rep_port
        self._context = zmq.asyncio.Context()
        self._socket: zmq.asyncio.Socket | None = None
        self._handlers: dict[str, Callable] = {}
        self._running = False

    def register_handler(self, method: str, handler: Callable) -> None:
        """Register a request handler.

        Args:
            method: Method name
            handler: Handler function (can be async)
        """
        self._handlers[method] = handler
        logger.debug("zmq_handler_registered", method=method)

    async def start(self) -> None:
        """Start the responder."""
        self._socket = self._context.socket(zmq.REP)
        self._socket.setsockopt(zmq.LINGER, 0)
        bind_addr = f"tcp://{self._host}:{self._rep_port}"
        self._socket.bind(bind_addr)
        self._running = True
        logger.info("zmq_responder_started", address=bind_addr)

    async def stop(self) -> None:
        """Stop the responder."""
        self._running = False
        if self._socket:
            self._socket.close(linger=0)
        self._context.term()
        logger.info("zmq_responder_stopped")

    async def serve(self) -> None:
        """Serve requests."""
        if not self._socket:
            raise RuntimeError("Responder not started")

        while self._running:
            try:
                data = await self._socket.recv()
                request = ZMQMessage.from_bytes(data)
                response = await self._handle_request(request)
                await self._socket.send(response.to_bytes())
            except Exception as e:
                logger.error("zmq_responder_error", error=str(e))
                error_response = ZMQMessage(
                    type=MessageType.ERROR,
                    topic="",
                    payload={"error": str(e)},
                )
                try:
                    await self._socket.send(error_response.to_bytes())
                except Exception:
                    pass

    async def _handle_request(self, request: ZMQMessage) -> ZMQMessage:
        """Handle a request and create response."""
        method = request.topic
        handler = self._handlers.get(method)

        if not handler:
            return ZMQMessage(
                type=MessageType.ERROR,
                topic=request.topic,
                payload={"error": f"No handler for method: {method}"},
                reply_to=request.message_id,
            )

        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(request.payload)
            else:
                result = handler(request.payload)

            return ZMQMessage(
                type=MessageType.RESPONSE,
                topic=request.topic,
                payload=result,
                reply_to=request.message_id,
            )
        except Exception as e:
            logger.error("zmq_handler_error", method=method, error=str(e))
            return ZMQMessage(
                type=MessageType.ERROR,
                topic=request.topic,
                payload={"error": str(e)},
                reply_to=request.message_id,
            )


class ZMQBus:
    """Combined ZeroMQ message bus with PUB/SUB and REQ/REP.

    Features:
    - Broadcast messages via PUB/SUB
    - Request/response via REQ/REP
    - Worker registration and discovery
    - Health monitoring

    Usage:
        # Master node
        bus = ZMQBus(role="master", host="127.0.0.1")
        await bus.start()
        await bus.publish("task_assigned", {"task_id": "123"})
        result = await bus.request("get_worker_status", {"worker_id": "1"})

        # Worker node
        bus = ZMQBus(role="worker", host="127.0.0.1")
        await bus.start()
        bus.subscribe("task_*", handle_task)
        bus.register_handler("get_status", get_status)
        await bus.serve()
    """

    def __init__(
        self,
        role: str = "master",
        host: str = "127.0.0.1",
        pub_port: int = 5555,
        rep_port: int = 5556,
    ) -> None:
        self.role = role
        self.host = host
        self.pub_port = pub_port
        self.rep_port = rep_port

        self._publisher: ZMQPublisher | None = None
        self._subscriber: ZMQSubscriber | None = None
        self._requester: ZMQRequester | None = None
        self._responder: ZMQResponder | None = None
        self._running = False

    async def start(self) -> None:
        """Start the message bus based on role."""
        if self.role == "master":
            # Master publishes and responds
            self._publisher = ZMQPublisher(
                host=self.host,
                pub_port=self.pub_port,
            )
            self._responder = ZMQResponder(
                host=self.host,
                rep_port=self.rep_port,
            )
            await self._publisher.start()
            await self._responder.start()

        elif self.role == "worker":
            # Worker subscribes and requests
            self._subscriber = ZMQSubscriber(
                host=self.host,
                pub_port=self.pub_port,
            )
            self._requester = ZMQRequester(
                host=self.host,
                rep_port=self.rep_port,
            )
            await self._subscriber.start()
            await self._requester.start()

        self._running = True
        logger.info("zmq_bus_started", role=self.role)

    async def stop(self) -> None:
        """Stop the message bus."""
        self._running = False

        # Stop components based on role
        if self.role == "master":
            if self._publisher:
                await self._publisher.stop()
            if self._responder:
                await self._responder.stop()
        elif self.role == "worker":
            if self._subscriber:
                await self._subscriber.stop()
            if self._requester:
                await self._requester.stop()

        logger.info("zmq_bus_stopped")

    async def publish(self, topic: str, payload: Any) -> None:
        """Publish a broadcast message."""
        if not self._publisher:
            raise RuntimeError("Cannot publish: not a master node")
        await self._publisher.publish(topic, payload)

    def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to broadcast messages."""
        if not self._subscriber:
            raise RuntimeError("Cannot subscribe: not a worker node")
        self._subscriber.subscribe(topic, callback)

    async def request(self, method: str, payload: Any) -> Any:
        """Send a request and wait for response."""
        if not self._requester:
            raise RuntimeError("Cannot request: not a worker node")
        return await self._requester.request(method, payload)

    def register_handler(self, method: str, handler: Callable) -> None:
        """Register a request handler."""
        if not self._responder:
            raise RuntimeError("Cannot register handler: not a master node")
        self._responder.register_handler(method, handler)

    async def serve(self) -> None:
        """Serve incoming requests (for master node)."""
        if self._responder:
            await self._responder.serve()

    async def run_listener(self) -> None:
        """Run subscriber listener loop (for worker node).

        Runs for a limited time then returns.
        """
        if self._subscriber:
            # Run for a limited time
            end_time = asyncio.get_event_loop().time() + 2.0
            while self._subscriber._running and asyncio.get_event_loop().time() < end_time:
                try:
                    topic, data = await asyncio.wait_for(
                        self._subscriber._socket.recv_multipart(),
                        timeout=0.5
                    )
                    message = ZMQMessage.from_bytes(data)
                    # Dispatch without await since callback may not be async
                    self._subscriber._dispatch_message_sync(topic.decode(), message)
                except asyncio.TimeoutError:
                    pass
                except Exception as e:
                    logger.error("zmq_listener_error", error=str(e))
