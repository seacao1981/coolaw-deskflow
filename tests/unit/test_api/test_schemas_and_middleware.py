"""Tests for API schemas, rate limiter, and logging."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from deskflow.api.schemas.models import (
    ChatRequest,
    ChatResponse,
    ComponentHealth,
    ConfigResponse,
    ConfigUpdateRequest,
    ErrorResponse,
    HealthResponse,
    StatusResponse,
    ToolCallInfo,
)


class TestChatSchemas:
    """Tests for chat request/response schemas."""

    def test_chat_request_valid(self) -> None:
        req = ChatRequest(message="Hello!")
        assert req.message == "Hello!"
        assert req.conversation_id is None
        assert req.stream is False

    def test_chat_request_with_options(self) -> None:
        req = ChatRequest(
            message="Hi", conversation_id="conv-1", stream=True
        )
        assert req.conversation_id == "conv-1"
        assert req.stream is True

    def test_chat_request_empty_message_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChatRequest(message="")

    def test_chat_response(self) -> None:
        resp = ChatResponse(
            message="Hello!",
            conversation_id="conv-1",
            tool_calls=[
                ToolCallInfo(name="shell", success=True, output="ok"),
            ],
        )
        assert resp.message == "Hello!"
        assert len(resp.tool_calls) == 1

    def test_tool_call_info_defaults(self) -> None:
        info = ToolCallInfo(name="test")
        assert info.success is True
        assert info.output == ""
        assert info.duration_ms == 0.0


class TestHealthSchemas:
    """Tests for health check schemas."""

    def test_health_response(self) -> None:
        resp = HealthResponse(
            status="ok",
            version="0.1.0",
            components={
                "agent": ComponentHealth(status="ok"),
                "memory": ComponentHealth(
                    status="ok", details={"count": 42}
                ),
            },
        )
        assert resp.status == "ok"
        assert len(resp.components) == 2

    def test_component_health_defaults(self) -> None:
        ch = ComponentHealth()
        assert ch.status == "ok"
        assert ch.details == {}

    def test_status_response(self) -> None:
        sr = StatusResponse(
            is_online=True,
            is_busy=False,
            total_conversations=10,
            llm_provider="anthropic",
        )
        assert sr.is_online is True
        assert sr.total_conversations == 10


class TestConfigSchemas:
    """Tests for config schemas."""

    def test_config_response(self) -> None:
        cr = ConfigResponse(
            llm_provider="anthropic",
            llm_model="claude-3.5-sonnet",
            has_api_key=True,
            server_host="127.0.0.1",
            server_port=8420,
        )
        assert cr.has_api_key is True
        assert cr.server_port == 8420

    def test_config_update_request_bounds(self) -> None:
        from pydantic import ValidationError

        # Valid
        req = ConfigUpdateRequest(llm_temperature=1.5, llm_max_tokens=8192)
        assert req.llm_temperature == 1.5

        # Invalid temperature
        with pytest.raises(ValidationError):
            ConfigUpdateRequest(llm_temperature=3.0)

    def test_error_response(self) -> None:
        err = ErrorResponse(error="not found", code="NOT_FOUND")
        assert err.error == "not found"
        assert err.code == "NOT_FOUND"


class TestRateLimiter:
    """Tests for rate limiting middleware logic."""

    def test_is_rate_limited_under_limit(self) -> None:
        from deskflow.api.middleware.rate_limit import RateLimitMiddleware

        rl = RateLimitMiddleware(MagicMock(), requests_per_minute=10)
        for _ in range(9):
            assert rl._is_rate_limited("1.2.3.4") is False

    def test_is_rate_limited_over_limit(self) -> None:
        from deskflow.api.middleware.rate_limit import RateLimitMiddleware

        rl = RateLimitMiddleware(MagicMock(), requests_per_minute=3)
        for _ in range(3):
            rl._is_rate_limited("1.2.3.4")

        assert rl._is_rate_limited("1.2.3.4") is True

    def test_different_ips_independent(self) -> None:
        from deskflow.api.middleware.rate_limit import RateLimitMiddleware

        rl = RateLimitMiddleware(MagicMock(), requests_per_minute=2)
        for _ in range(2):
            rl._is_rate_limited("10.0.0.1")
        # IP 10.0.0.1 is now limited
        assert rl._is_rate_limited("10.0.0.1") is True
        # IP 10.0.0.2 is fresh
        assert rl._is_rate_limited("10.0.0.2") is False

    def test_get_client_ip_from_header(self) -> None:
        from deskflow.api.middleware.rate_limit import RateLimitMiddleware

        rl = RateLimitMiddleware(MagicMock(), requests_per_minute=60)
        mock_request = MagicMock()
        mock_request.headers = {"X-Forwarded-For": "203.0.113.1, 198.51.100.1"}
        ip = rl._get_client_ip(mock_request)
        assert ip == "203.0.113.1"

    def test_get_client_ip_from_client(self) -> None:
        from deskflow.api.middleware.rate_limit import RateLimitMiddleware

        rl = RateLimitMiddleware(MagicMock(), requests_per_minute=60)
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client.host = "192.168.1.1"
        ip = rl._get_client_ip(mock_request)
        assert ip == "192.168.1.1"

    def test_get_client_ip_unknown(self) -> None:
        from deskflow.api.middleware.rate_limit import RateLimitMiddleware

        rl = RateLimitMiddleware(MagicMock(), requests_per_minute=60)
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client = None
        ip = rl._get_client_ip(mock_request)
        assert ip == "unknown"


class TestLogging:
    """Tests for structured logging."""

    def test_setup_logging(self) -> None:
        from deskflow.observability.logging import setup_logging

        # Should not raise
        setup_logging(log_level="DEBUG", json_output=False)
        setup_logging(log_level="INFO", json_output=True)

    def test_get_logger(self) -> None:
        from deskflow.observability.logging import get_logger

        log = get_logger("test_module")
        assert log is not None
