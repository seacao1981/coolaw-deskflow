"""Tests for AppConfig and related configuration."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from deskflow.config import (
    AppConfig,
    Environment,
    LLMConfig,
    LLMProvider,
    MemoryConfig,
    ServerConfig,
    ToolConfig,
    load_config,
)


class TestLLMConfig:
    """Tests for LLM configuration."""

    def test_defaults(self) -> None:
        """Test LLM configuration default values."""
        config = LLMConfig()
        assert config.llm_provider == LLMProvider.DASHSCOPE
        assert config.llm_max_tokens == 4096
        assert config.llm_temperature == 0.7
        assert config.dashscope_model == "qwen3.5-plus"

    def test_temperature_bounds(self) -> None:
        config = LLMConfig(llm_temperature=0.0)
        assert config.llm_temperature == 0.0

        config = LLMConfig(llm_temperature=2.0)
        assert config.llm_temperature == 2.0

    def test_max_tokens_bounds(self) -> None:
        config = LLMConfig(llm_max_tokens=1)
        assert config.llm_max_tokens == 1


class TestServerConfig:
    """Tests for server configuration."""

    def test_defaults(self) -> None:
        config = ServerConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 8420
        assert config.log_level == "INFO"


class TestMemoryConfig:
    """Tests for memory configuration."""

    def test_defaults(self) -> None:
        config = MemoryConfig()
        assert config.db_path == "data/db/deskflow.db"
        assert config.memory_cache_size == 1000


class TestToolConfig:
    """Tests for tool configuration."""

    def test_defaults(self) -> None:
        config = ToolConfig()
        assert config.tool_timeout == 30.0
        assert config.tool_max_parallel == 3

    def test_expand_paths(self) -> None:
        config = ToolConfig(allowed_paths="~/Projects,~/Documents")
        home = os.path.expanduser("~")
        assert home in config.allowed_paths
        assert "~" not in config.allowed_paths

    def test_get_allowed_paths(self) -> None:
        config = ToolConfig(allowed_paths="/tmp,/home")
        paths = config.get_allowed_paths()
        assert len(paths) == 2
        assert paths[0] == Path("/tmp")


class TestAppConfig:
    """Tests for root application config."""

    def test_defaults(self) -> None:
        config = AppConfig()
        assert config.env == Environment.DEV
        assert config.app_name == "Coolaw DeskFlow"
        assert config.version == "0.1.0"

    def test_nested_configs(self) -> None:
        config = AppConfig()
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.server, ServerConfig)
        assert isinstance(config.memory, MemoryConfig)
        assert isinstance(config.tools, ToolConfig)

    def test_get_project_root(self) -> None:
        config = AppConfig()
        root = config.get_project_root()
        assert root.exists()

    def test_get_data_dir(self) -> None:
        config = AppConfig()
        data_dir = config.get_data_dir()
        assert data_dir.exists()

    def test_load_config(self) -> None:
        config = load_config()
        assert isinstance(config, AppConfig)
