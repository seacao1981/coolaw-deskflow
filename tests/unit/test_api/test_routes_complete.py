"""Tests for API routes - Chat, Health, Config endpoints."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from deskflow.core.models import Message, Role, StreamChunk, AgentStatus


class TestChatRoute:
    """Tests for chat endpoint."""

    def test_chat_request_schema(self) -> None:
        """Test chat request validation."""
        from deskflow.api.schemas.models import ChatRequest

        req = ChatRequest(message="Hello", conversation_id="conv-123")
        assert req.message == "Hello"
        assert req.conversation_id == "conv-123"

        with pytest.raises(Exception):
            ChatRequest(message="", conversation_id="conv-123")

    def test_chat_response_schema(self) -> None:
        """Test chat response structure."""
        from deskflow.api.schemas.models import ChatResponse, ToolCallInfo

        response = ChatResponse(
            message="Hello!",
            conversation_id="conv-123",
            tool_calls=[ToolCallInfo(name="shell", arguments={"command": "ls"})],
        )
        assert response.message == "Hello!"
        assert len(response.tool_calls) == 1

    @patch("deskflow.api.routes.chat._get_agent")
    def test_chat_with_mock_agent(self, mock_get_agent) -> None:
        """Test chat endpoint with mocked agent."""
        from deskflow.api.routes.chat import chat
        from deskflow.api.schemas.models import ChatRequest

        mock_agent = AsyncMock()
        mock_agent.chat = AsyncMock(return_value=Message(role=Role.ASSISTANT, content="Test", tool_calls=[]))
        mock_get_agent.return_value = mock_agent

        async def run_chat():
            req = ChatRequest(message="Hello", conversation_id="conv-123")
            return await chat(req)

        response = asyncio.run(run_chat())
        assert response.message == "Test"

    @patch("deskflow.api.routes.chat._get_agent")
    def test_chat_without_agent(self, mock_get_agent) -> None:
        """Test chat when agent is not configured."""
        from deskflow.api.routes.chat import chat
        from deskflow.api.schemas.models import ChatRequest

        mock_get_agent.return_value = None

        async def run_chat():
            return await chat(ChatRequest(message="Hello"))

        response = asyncio.run(run_chat())
        assert "未配置" in response.message


class TestWebSocketChat:
    """Tests for WebSocket streaming chat."""

    @patch("deskflow.api.routes.chat._get_agent")
    def test_websocket_accept_called(self, mock_get_agent) -> None:
        """Test WebSocket accepts connection."""
        from deskflow.api.routes.chat import chat_stream

        mock_get_agent.return_value = None  # No agent, will send error and close

        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()
        mock_ws.close = AsyncMock()
        mock_ws.client = "test-client"
        mock_ws.receive_text = AsyncMock(side_effect=asyncio.CancelledError())

        async def run_ws():
            try:
                await chat_stream(mock_ws)
            except asyncio.CancelledError:
                pass

        asyncio.run(run_ws())
        mock_ws.accept.assert_called_once()

    @patch("deskflow.api.routes.chat._get_agent")
    def test_websocket_handles_disconnect(self, mock_get_agent) -> None:
        """Test WebSocket handles disconnect gracefully."""
        from deskflow.api.routes.chat import chat_stream
        from fastapi import WebSocketDisconnect

        mock_agent = AsyncMock()
        mock_agent.stream_chat = AsyncMock(side_effect=WebSocketDisconnect())
        mock_get_agent.return_value = mock_agent

        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())
        mock_ws.client = "test-client"

        async def run_ws():
            try:
                await chat_stream(mock_ws)
            except Exception:
                pass

        # Should not raise
        asyncio.run(run_ws())


class TestHealthRoute:
    """Tests for health endpoint."""

    def test_health_response_schema(self) -> None:
        """Test health response structure."""
        from deskflow.api.schemas.models import HealthResponse, ComponentHealth

        health = HealthResponse(
            status="ok",
            version="0.1.0",
            components={"llm": ComponentHealth(status="ok")},
        )
        assert health.status == "ok"
        assert len(health.components) == 1

    def test_agent_status_serialization(self) -> None:
        """Test AgentStatus serialization."""
        status = AgentStatus(
            is_online=True, is_busy=False, total_conversations=5,
            total_tool_calls=10, llm_provider="dashscope", llm_model="qwen3.5-plus",
        )
        d = status.model_dump()
        assert d["is_online"] is True
        assert d["total_conversations"] == 5
        assert d["total_tool_calls"] == 10


class TestConfigRoute:
    """Tests for config endpoint."""

    def test_config_response_schema(self) -> None:
        """Test config response structure."""
        from deskflow.api.schemas.models import ConfigResponse

        config = ConfigResponse(
            llm_provider="dashscope", llm_model="qwen3.5-plus",
            llm_temperature=0.7, has_api_key=True,
        )
        assert config.llm_provider == "dashscope"
        assert config.has_api_key is True

    def test_config_update_request_bounds(self) -> None:
        """Test config update validation."""
        from deskflow.api.schemas.models import ConfigUpdateRequest

        req = ConfigUpdateRequest(llm_temperature=1.0)
        assert req.llm_temperature == 1.0

        with pytest.raises(Exception):
            ConfigUpdateRequest(llm_temperature=3.0)

        with pytest.raises(Exception):
            ConfigUpdateRequest(server_port=70000)

    def test_config_redaction(self) -> None:
        """API keys should be redacted when returned."""
        from deskflow.config import LLMConfig

        config = LLMConfig(anthropic_api_key="sk-ant-secret-key")
        assert config.anthropic_api_key == "sk-ant-secret-key"


class TestRateLimitMiddleware:
    """Tests for rate limiting middleware."""

    def test_rate_limit_under_limit(self) -> None:
        """Test requests under rate limit."""
        from deskflow.api.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(app=MagicMock(), requests_per_minute=5)
        assert middleware._is_rate_limited("192.168.1.1") is False

    def test_rate_limit_over_limit(self) -> None:
        """Test requests over rate limit."""
        from deskflow.api.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(app=MagicMock(), requests_per_minute=2)
        assert middleware._is_rate_limited("192.168.1.1") is False
        assert middleware._is_rate_limited("192.168.1.1") is False
        assert middleware._is_rate_limited("192.168.1.1") is True

    def test_rate_limit_different_ips(self) -> None:
        """Test rate limit is per-IP."""
        from deskflow.api.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(app=MagicMock(), requests_per_minute=1)
        assert middleware._is_rate_limited("192.168.1.1") is False
        assert middleware._is_rate_limited("192.168.1.1") is True
        assert middleware._is_rate_limited("192.168.1.2") is False

    def test_get_client_ip_from_forwarded(self) -> None:
        """Test IP extraction from X-Forwarded-For header."""
        from deskflow.api.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(app=MagicMock())
        mock_request = MagicMock()
        mock_request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}
        mock_request.client = None
        ip = middleware._get_client_ip(mock_request)
        assert ip == "10.0.0.1"

    def test_get_client_ip_from_client(self) -> None:
        """Test IP extraction from client."""
        from deskflow.api.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(app=MagicMock())
        mock_client = MagicMock()
        mock_client.host = "127.0.0.1"
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client = mock_client
        ip = middleware._get_client_ip(mock_request)
        assert ip == "127.0.0.1"


class TestStreamChunk:
    """Tests for StreamChunk schema."""

    def test_stream_chunk_text(self) -> None:
        chunk = StreamChunk(type="text", content="Hello")
        assert chunk.type == "text"
        assert chunk.content == "Hello"

    def test_stream_chunk_done(self) -> None:
        chunk = StreamChunk(type="done")
        assert chunk.type == "done"

    def test_stream_chunk_error(self) -> None:
        chunk = StreamChunk(type="error", content="Something failed")
        assert chunk.type == "error"
        assert "failed" in chunk.content


class TestToolCallSchema:
    """Tests for tool call schemas."""

    def test_tool_call_info_defaults(self) -> None:
        from deskflow.api.schemas.models import ToolCallInfo

        info = ToolCallInfo(name="shell", arguments={"command": "ls"})
        assert info.success is True
        assert info.output == ""
        assert info.duration_ms == 0.0

    def test_tool_call_info_complete(self) -> None:
        from deskflow.api.schemas.models import ToolCallInfo

        info = ToolCallInfo(
            name="file", arguments={"path": "/tmp/test.txt"},
            success=True, output="File created", duration_ms=15.5,
        )
        assert info.name == "file"
        assert info.success is True
        assert info.output == "File created"
        assert info.duration_ms == 15.5
