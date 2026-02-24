"""Tests for LLM adapter and providers."""

from __future__ import annotations

import pytest

from deskflow.llm.adapter import BaseLLMAdapter
from deskflow.llm.providers.anthropic import AnthropicAdapter
from deskflow.llm.providers.openai_compat import OpenAICompatAdapter
from deskflow.llm.providers.dashscope import DashScopeAdapter


class TestAnthropicAdapter:
    """Tests for AnthropicAdapter construction and utilities."""

    def test_provider_name(self) -> None:
        adapter = AnthropicAdapter(
            api_key="test-key", model="claude-3-5-sonnet-20241022"
        )
        assert adapter.provider_name == "Anthropic"
        assert adapter.model_name == "claude-3-5-sonnet-20241022"


class TestOpenAICompatAdapter:
    """Tests for OpenAICompatAdapter construction."""

    def test_provider_name(self) -> None:
        adapter = OpenAICompatAdapter(
            api_key="test-key",
            model="gpt-4",
            base_url="https://api.openai.com/v1",
        )
        assert adapter.provider_name == "OpenAI"
        assert adapter.model_name == "gpt-4"

    def test_default_base_url(self) -> None:
        adapter = OpenAICompatAdapter(
            api_key="test-key", model="gpt-4"
        )
        assert "openai" in adapter._base_url


class TestDashScopeAdapter:
    """Tests for DashScopeAdapter construction."""

    def test_provider_name(self) -> None:
        adapter = DashScopeAdapter(
            api_key="test-key", model="qwen-max"
        )
        assert adapter.provider_name == "DashScope"
        assert adapter.model_name == "qwen-max"

    def test_inherits_openai_compat(self) -> None:
        adapter = DashScopeAdapter(api_key="test-key", model="qwen-max")
        assert isinstance(adapter, OpenAICompatAdapter)

    def test_uses_dashscope_base_url(self) -> None:
        adapter = DashScopeAdapter(api_key="test-key", model="qwen-max")
        assert "dashscope" in adapter._base_url


class TestBaseLLMAdapter:
    """Tests for BaseLLMAdapter base class."""

    def test_model_name_property(self) -> None:
        adapter = AnthropicAdapter(api_key="test", model="claude-3-haiku")
        assert adapter.model_name == "claude-3-haiku"


class TestCreateAdapter:
    """Tests for the create_adapter factory function."""

    def test_missing_api_key_raises(self) -> None:
        from deskflow.config import AppConfig, LLMProvider

        config = AppConfig()
        config.llm.llm_provider = LLMProvider.ANTHROPIC
        config.llm.anthropic_api_key = ""

        from deskflow.llm.client import create_adapter

        with pytest.raises(ValueError, match="API_KEY"):
            create_adapter(config)

    def test_missing_openai_key_raises(self) -> None:
        from deskflow.config import AppConfig, LLMProvider
        from deskflow.llm.client import create_adapter

        config = AppConfig()
        config.llm.llm_provider = LLMProvider.OPENAI
        config.llm.openai_api_key = ""

        with pytest.raises(ValueError, match="API_KEY"):
            create_adapter(config)

    def test_missing_dashscope_key_raises(self) -> None:
        from deskflow.config import AppConfig, LLMProvider
        from deskflow.llm.client import create_adapter

        config = AppConfig()
        config.llm.llm_provider = LLMProvider.DASHSCOPE
        config.llm.dashscope_api_key = ""

        with pytest.raises(ValueError, match="API_KEY"):
            create_adapter(config)

    def test_unsupported_provider_raises(self) -> None:
        from deskflow.config import AppConfig
        from deskflow.llm.client import create_adapter

        config = AppConfig()
        config.llm.llm_provider = "invalid"  # type: ignore[assignment]

        with pytest.raises(ValueError, match="Unsupported"):
            create_adapter(config)

    def test_anthropic_adapter_created(self) -> None:
        from deskflow.config import AppConfig, LLMProvider
        from deskflow.llm.client import create_adapter

        config = AppConfig()
        config.llm.llm_provider = LLMProvider.ANTHROPIC
        config.llm.anthropic_api_key = "sk-test-key"

        adapter = create_adapter(config)
        assert adapter.provider_name == "Anthropic"

    def test_openai_adapter_created(self) -> None:
        from deskflow.config import AppConfig, LLMProvider
        from deskflow.llm.client import create_adapter

        config = AppConfig()
        config.llm.llm_provider = LLMProvider.OPENAI
        config.llm.openai_api_key = "sk-test-key"

        adapter = create_adapter(config)
        assert adapter.provider_name == "OpenAI"

    def test_dashscope_adapter_created(self) -> None:
        from deskflow.config import AppConfig, LLMProvider
        from deskflow.llm.client import create_adapter

        config = AppConfig()
        config.llm.llm_provider = LLMProvider.DASHSCOPE
        config.llm.dashscope_api_key = "sk-test-key"

        adapter = create_adapter(config)
        assert adapter.provider_name == "DashScope"
