"""API request and response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request to send a message to the agent."""

    message: str = Field(..., min_length=1, max_length=100000)
    conversation_id: str | None = None
    stream: bool = False


class ChatResponse(BaseModel):
    """Response from the agent."""

    message: str
    conversation_id: str
    tool_calls: list[ToolCallInfo] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCallInfo(BaseModel):
    """Tool call information in response."""

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    output: str = ""
    duration_ms: float = 0.0


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str = ""
    components: dict[str, ComponentHealth] = Field(default_factory=dict)


class ComponentHealth(BaseModel):
    """Individual component health."""

    status: str = "ok"
    details: dict[str, Any] = Field(default_factory=dict)


class StatusResponse(BaseModel):
    """Agent status response."""

    is_online: bool = True
    is_busy: bool = False
    current_task: str | None = None
    uptime_seconds: float = 0.0
    total_conversations: int = 0
    total_tool_calls: int = 0
    total_tokens_used: int = 0
    memory_count: int = 0
    active_tools: int = 0
    available_tools: int = 0
    llm_provider: str = ""
    llm_model: str = ""


class ConfigResponse(BaseModel):
    """Configuration read response (sensitive fields redacted)."""

    llm_provider: str = ""
    llm_model: str = ""
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096
    has_api_key: bool = False
    openai_base_url: str = ""  # OpenAI Compatible base URL
    server_host: str = ""
    server_port: int = 8420
    memory_cache_size: int = 1000
    tool_timeout: float = 30.0
    log_level: str = "INFO"


class ConfigUpdateRequest(BaseModel):
    """Configuration update request."""

    llm_provider: str | None = None
    llm_model: str | None = None
    llm_temperature: float | None = Field(None, ge=0.0, le=2.0)
    llm_max_tokens: int | None = Field(None, ge=1, le=200000)
    api_key: str | None = None
    base_url: str | None = None  # OpenAI Compatible base URL
    # System settings
    server_port: int | None = Field(None, ge=1, le=65535)
    log_level: str | None = None
    memory_cache_size: int | None = Field(None, ge=100, le=100000)
    tool_timeout: float | None = Field(None, ge=5.0, le=300.0)


class LLMTestRequest(BaseModel):
    """LLM connection test request."""

    provider: str
    model: str
    api_key: str
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 100


class LLMTestResponse(BaseModel):
    """LLM connection test response."""

    success: bool
    message: str
    model: str | None = None
    provider: str | None = None
    latency_ms: float | None = None


class LLMModelsResponse(BaseModel):
    """LLM models list response."""

    models: list[str]
    provider: str
    base_url: str | None = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    code: str = "UNKNOWN_ERROR"
    details: dict[str, Any] = Field(default_factory=dict)


# Fix forward reference
ChatResponse.model_rebuild()
HealthResponse.model_rebuild()
