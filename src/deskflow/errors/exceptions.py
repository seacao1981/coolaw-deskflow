"""DeskFlow exception hierarchy.

Provides fine-grained exceptions to replace generic try-except patterns.
Each exception carries a machine-readable code and optional detail dict.
"""

from __future__ import annotations

from typing import Any


class DeskFlowError(Exception):
    """Base exception for all DeskFlow errors."""

    def __init__(
        self,
        message: str,
        code: str = "DESKFLOW_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Serialize exception for API responses and logging."""
        return {
            "error": self.__class__.__name__,
            "code": self.code,
            "message": str(self),
            "details": self.details,
        }


# === LLM Errors ===


class LLMError(DeskFlowError):
    """Base class for LLM-related errors."""

    def __init__(
        self,
        message: str,
        code: str = "LLM_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code, details)


class LLMConnectionError(LLMError):
    """Failed to connect to LLM provider."""

    def __init__(self, provider: str, reason: str = "") -> None:
        super().__init__(
            f"Failed to connect to {provider}: {reason}",
            code="LLM_CONNECTION_ERROR",
            details={"provider": provider, "reason": reason},
        )


class LLMRateLimitError(LLMError):
    """Hit rate limit on LLM provider."""

    def __init__(self, provider: str, retry_after: float | None = None) -> None:
        msg = f"Rate limited by {provider}"
        if retry_after:
            msg += f", retry after {retry_after}s"
        super().__init__(
            msg,
            code="LLM_RATE_LIMIT",
            details={"provider": provider, "retry_after": retry_after},
        )


class LLMContextOverflowError(LLMError):
    """Prompt exceeds model context window."""

    def __init__(self, token_count: int, max_tokens: int) -> None:
        super().__init__(
            f"Context overflow: {token_count} tokens exceeds limit of {max_tokens}",
            code="LLM_CONTEXT_OVERFLOW",
            details={"token_count": token_count, "max_tokens": max_tokens},
        )


class LLMResponseError(LLMError):
    """Invalid or unexpected response from LLM."""

    def __init__(self, provider: str, reason: str = "") -> None:
        super().__init__(
            f"Invalid response from {provider}: {reason}",
            code="LLM_RESPONSE_ERROR",
            details={"provider": provider, "reason": reason},
        )


class LLMAllProvidersFailedError(LLMError):
    """All configured LLM providers failed."""

    def __init__(self, providers: list[str], errors: list[str]) -> None:
        super().__init__(
            f"All LLM providers failed: {', '.join(providers)}",
            code="LLM_ALL_FAILED",
            details={"providers": providers, "errors": errors},
        )


# === Tool Errors ===


class ToolError(DeskFlowError):
    """Base class for tool-related errors."""

    def __init__(
        self,
        message: str,
        code: str = "TOOL_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code, details)


class ToolNotFoundError(ToolError):
    """Requested tool does not exist in registry."""

    def __init__(self, tool_name: str) -> None:
        super().__init__(
            f"Tool not found: {tool_name}",
            code="TOOL_NOT_FOUND",
            details={"tool_name": tool_name},
        )


class ToolExecutionError(ToolError):
    """Tool execution failed."""

    def __init__(self, tool_name: str, reason: str = "") -> None:
        super().__init__(
            f"Tool '{tool_name}' execution failed: {reason}",
            code="TOOL_EXECUTION_ERROR",
            details={"tool_name": tool_name, "reason": reason},
        )


class ToolTimeoutError(ToolError):
    """Tool execution exceeded timeout."""

    def __init__(self, tool_name: str, timeout: float) -> None:
        super().__init__(
            f"Tool '{tool_name}' timed out after {timeout}s",
            code="TOOL_TIMEOUT",
            details={"tool_name": tool_name, "timeout": timeout},
        )


class ToolSecurityError(ToolError):
    """Tool operation blocked by security policy."""

    def __init__(self, tool_name: str, reason: str = "") -> None:
        super().__init__(
            f"Security violation in tool '{tool_name}': {reason}",
            code="TOOL_SECURITY_ERROR",
            details={"tool_name": tool_name, "reason": reason},
        )


# === Memory Errors ===


class DeskFlowMemoryError(DeskFlowError):
    """Base class for memory-related errors."""

    def __init__(
        self,
        message: str,
        code: str = "MEMORY_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code, details)


class MemoryStorageError(DeskFlowMemoryError):
    """Failed to store data in memory."""

    def __init__(self, reason: str = "") -> None:
        super().__init__(
            f"Memory storage failed: {reason}",
            code="MEMORY_STORAGE_ERROR",
            details={"reason": reason},
        )


class MemoryRetrievalError(DeskFlowMemoryError):
    """Failed to retrieve data from memory."""

    def __init__(self, reason: str = "") -> None:
        super().__init__(
            f"Memory retrieval failed: {reason}",
            code="MEMORY_RETRIEVAL_ERROR",
            details={"reason": reason},
        )


# === Skill Errors ===


class SkillError(DeskFlowError):
    """Base class for skill-related errors."""

    def __init__(
        self,
        message: str,
        code: str = "SKILL_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code, details)


class SkillNotFoundError(SkillError):
    """Requested skill does not exist."""

    def __init__(self, skill_name: str) -> None:
        super().__init__(
            f"Skill not found: {skill_name}",
            code="SKILL_NOT_FOUND",
            details={"skill_name": skill_name},
        )


class SkillSandboxError(SkillError):
    """Skill sandbox execution failed."""

    def __init__(self, skill_name: str, reason: str = "") -> None:
        super().__init__(
            f"Sandbox error for skill '{skill_name}': {reason}",
            code="SKILL_SANDBOX_ERROR",
            details={"skill_name": skill_name, "reason": reason},
        )


# === Config Errors ===


class ConfigError(DeskFlowError):
    """Configuration-related errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="CONFIG_ERROR", details=details)


class ConfigValidationError(ConfigError):
    """Invalid configuration value."""

    def __init__(self, field: str, value: str, reason: str = "") -> None:
        super().__init__(
            f"Invalid config '{field}' = '{value}': {reason}",
            details={"field": field, "value": value, "reason": reason},
        )
