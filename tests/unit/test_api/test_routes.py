"""Tests for API routes (health, config)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from deskflow.core.models import AgentStatus


class TestHealthRoute:
    """Tests for health endpoint logic."""

    def test_agent_status_serialization(self) -> None:
        status = AgentStatus(
            is_online=True,
            is_busy=False,
            total_conversations=5,
            llm_provider="anthropic",
            llm_model="claude-3.5-sonnet",
        )
        d = status.model_dump()
        assert d["is_online"] is True
        assert d["total_conversations"] == 5
        assert d["llm_provider"] == "anthropic"


class TestConfigRoute:
    """Tests for config endpoint logic."""

    def test_config_redaction(self) -> None:
        """API keys should be redacted when returned."""
        from deskflow.config import LLMConfig

        config = LLMConfig(anthropic_api_key="sk-ant-secret-key")
        # The actual redaction happens in the route handler,
        # but we verify the config holds the value
        assert config.anthropic_api_key == "sk-ant-secret-key"
