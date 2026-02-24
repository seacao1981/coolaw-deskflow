"""DeskFlow configuration management using Pydantic Settings."""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Application environment."""

    DEV = "dev"
    PROD = "prod"
    TEST = "test"


class LLMProvider(StrEnum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    DASHSCOPE = "dashscope"


class LLMConfig(BaseSettings):
    """LLM provider configuration."""

    model_config = SettingsConfigDict(
        env_prefix="DESKFLOW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: LLMProvider = LLMProvider.DASHSCOPE
    llm_max_tokens: int = Field(default=4096, ge=1, le=200000)
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Anthropic
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # OpenAI Compatible
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"

    # DashScope
    dashscope_api_key: str | None = None
    dashscope_model: str = "qwen-max"


class ServerConfig(BaseSettings):
    """Server configuration."""

    model_config = SettingsConfigDict(env_prefix="DESKFLOW_")

    host: str = "127.0.0.1"
    port: int = Field(default=8420, ge=1024, le=65535)
    log_level: str = "INFO"


class MemoryConfig(BaseSettings):
    """Memory system configuration."""

    model_config = SettingsConfigDict(env_prefix="DESKFLOW_")

    db_path: str = "data/db/deskflow.db"
    memory_cache_size: int = Field(default=1000, ge=10, le=100000)


class ToolConfig(BaseSettings):
    """Tool system configuration."""

    model_config = SettingsConfigDict(env_prefix="DESKFLOW_")

    tool_timeout: float = Field(default=30.0, ge=1.0, le=300.0)
    tool_max_parallel: int = Field(default=3, ge=1, le=10)
    allowed_paths: str = "~/Projects,~/Documents"

    @field_validator("allowed_paths")
    @classmethod
    def expand_paths(cls, v: str) -> str:
        """Expand ~ in allowed paths."""
        parts = v.split(",")
        expanded = [os.path.expanduser(p.strip()) for p in parts]
        return ",".join(expanded)

    def get_allowed_paths(self) -> list[Path]:
        """Return list of allowed Path objects."""
        return [Path(p.strip()) for p in self.allowed_paths.split(",")]


class AppConfig(BaseSettings):
    """Root application configuration."""

    model_config = SettingsConfigDict(
        env_prefix="DESKFLOW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Environment = Environment.DEV
    app_name: str = "Coolaw DeskFlow"
    version: str = "0.1.0"

    llm: LLMConfig = Field(default_factory=LLMConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    tools: ToolConfig = Field(default_factory=ToolConfig)

    def get_project_root(self) -> Path:
        """Return the project root directory."""
        return Path(__file__).parent.parent.parent

    def get_data_dir(self) -> Path:
        """Return the data directory, creating it if needed."""
        data_dir = self.get_project_root() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    def get_db_path(self) -> Path:
        """Return the database file path, creating parent dir if needed."""
        db_path = self.get_project_root() / self.memory.db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path


def load_config() -> AppConfig:
    """Load application configuration from environment and .env file."""
    return AppConfig()
