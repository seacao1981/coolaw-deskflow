"""Tests for the exception hierarchy."""

from __future__ import annotations

from deskflow.errors.exceptions import (
    ConfigError,
    ConfigValidationError,
    DeskFlowError,
    DeskFlowMemoryError,
    LLMAllProvidersFailedError,
    LLMConnectionError,
    LLMContextOverflowError,
    LLMError,
    LLMRateLimitError,
    LLMResponseError,
    MemoryRetrievalError,
    MemoryStorageError,
    SkillError,
    SkillNotFoundError,
    SkillSandboxError,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolSecurityError,
    ToolTimeoutError,
)


class TestDeskFlowError:
    """Tests for base DeskFlowError."""

    def test_message_and_code(self) -> None:
        err = DeskFlowError("something broke", code="TEST_ERR")
        assert str(err) == "something broke"
        assert err.code == "TEST_ERR"

    def test_default_code(self) -> None:
        err = DeskFlowError("test")
        assert err.code == "DESKFLOW_ERROR"

    def test_to_dict(self) -> None:
        err = DeskFlowError("test", code="ERR", details={"key": "val"})
        d = err.to_dict()
        assert d["error"] == "DeskFlowError"
        assert d["code"] == "ERR"
        assert d["message"] == "test"
        assert d["details"]["key"] == "val"


class TestLLMErrors:
    """Tests for LLM error hierarchy."""

    def test_connection_error(self) -> None:
        err = LLMConnectionError("anthropic", "timeout")
        assert "anthropic" in str(err)
        assert err.code == "LLM_CONNECTION_ERROR"
        assert err.details["provider"] == "anthropic"
        assert isinstance(err, LLMError)
        assert isinstance(err, DeskFlowError)

    def test_rate_limit_error_with_retry(self) -> None:
        err = LLMRateLimitError("openai", retry_after=30.0)
        assert "30.0s" in str(err)
        assert err.details["retry_after"] == 30.0

    def test_rate_limit_error_without_retry(self) -> None:
        err = LLMRateLimitError("openai")
        assert err.details["retry_after"] is None

    def test_context_overflow(self) -> None:
        err = LLMContextOverflowError(200000, 128000)
        assert "200000" in str(err)
        assert "128000" in str(err)
        assert err.code == "LLM_CONTEXT_OVERFLOW"

    def test_response_error(self) -> None:
        err = LLMResponseError("anthropic", "empty content")
        assert err.code == "LLM_RESPONSE_ERROR"

    def test_all_providers_failed(self) -> None:
        err = LLMAllProvidersFailedError(
            providers=["anthropic", "openai"],
            errors=["timeout", "rate limit"],
        )
        assert "anthropic" in str(err)
        assert err.code == "LLM_ALL_FAILED"
        assert len(err.details["providers"]) == 2


class TestToolErrors:
    """Tests for tool error hierarchy."""

    def test_not_found(self) -> None:
        err = ToolNotFoundError("magic_tool")
        assert "magic_tool" in str(err)
        assert err.code == "TOOL_NOT_FOUND"
        assert isinstance(err, ToolError)

    def test_execution_error(self) -> None:
        err = ToolExecutionError("shell", "permission denied")
        assert err.code == "TOOL_EXECUTION_ERROR"
        assert err.details["tool_name"] == "shell"

    def test_timeout_error(self) -> None:
        err = ToolTimeoutError("web", 30.0)
        assert "30.0" in str(err)
        assert err.code == "TOOL_TIMEOUT"

    def test_security_error(self) -> None:
        err = ToolSecurityError("shell", "blocked command: rm -rf /")
        assert err.code == "TOOL_SECURITY_ERROR"
        assert "rm -rf" in str(err)


class TestMemoryErrors:
    """Tests for memory error hierarchy."""

    def test_storage_error(self) -> None:
        err = MemoryStorageError("disk full")
        assert "disk full" in str(err)
        assert isinstance(err, DeskFlowMemoryError)

    def test_retrieval_error(self) -> None:
        err = MemoryRetrievalError("FTS index corrupted")
        assert "FTS" in str(err)
        assert err.code == "MEMORY_RETRIEVAL_ERROR"


class TestSkillErrors:
    """Tests for skill error hierarchy."""

    def test_not_found(self) -> None:
        err = SkillNotFoundError("unknown_skill")
        assert "unknown_skill" in str(err)
        assert isinstance(err, SkillError)

    def test_sandbox_error(self) -> None:
        err = SkillSandboxError("risky_skill", "network access denied")
        assert err.code == "SKILL_SANDBOX_ERROR"


class TestConfigErrors:
    """Tests for config errors."""

    def test_config_error(self) -> None:
        err = ConfigError("invalid config")
        assert err.code == "CONFIG_ERROR"

    def test_config_validation_error(self) -> None:
        err = ConfigValidationError("port", "99999", "must be < 65536")
        assert "port" in str(err)
        assert err.details["field"] == "port"
