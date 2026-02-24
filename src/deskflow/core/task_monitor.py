"""Task monitor for tracking agent activity and performance."""

from __future__ import annotations

import time
from typing import Any

from deskflow.core.models import AgentStatus
from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


class TaskMonitor:
    """Tracks agent tasks, performance metrics, and status."""

    def __init__(self) -> None:
        self._start_time = time.time()
        self._total_conversations = 0
        self._total_tool_calls = 0
        self._total_tokens_used = 0
        self._is_busy = False
        self._current_task: str | None = None
        self._activity_log: list[dict[str, Any]] = []
        self._max_activity_log = 1000

    def record_conversation(self) -> None:
        """Record a new conversation."""
        self._total_conversations += 1

    def record_tool_call(self, tool_name: str, duration_ms: float, success: bool) -> None:
        """Record a tool execution."""
        self._total_tool_calls += 1
        self._add_activity({
            "type": "tool_call",
            "tool_name": tool_name,
            "duration_ms": duration_ms,
            "success": success,
            "timestamp": time.time(),
        })

    def record_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Record token usage."""
        self._total_tokens_used += input_tokens + output_tokens
        self._add_activity({
            "type": "llm_call",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "timestamp": time.time(),
        })

    def set_busy(self, task: str | None = None) -> None:
        """Mark the agent as busy."""
        self._is_busy = True
        self._current_task = task

    def set_idle(self) -> None:
        """Mark the agent as idle."""
        self._is_busy = False
        self._current_task = None

    def get_status(
        self,
        memory_count: int = 0,
        active_tools: int = 0,
        available_tools: int = 0,
        llm_provider: str = "",
        llm_model: str = "",
    ) -> AgentStatus:
        """Get current agent status."""
        return AgentStatus(
            is_online=True,
            is_busy=self._is_busy,
            current_task=self._current_task,
            uptime_seconds=time.time() - self._start_time,
            total_conversations=self._total_conversations,
            total_tool_calls=self._total_tool_calls,
            total_tokens_used=self._total_tokens_used,
            memory_count=memory_count,
            active_tools=active_tools,
            available_tools=available_tools,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )

    def get_recent_activity(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent activity entries."""
        return self._activity_log[-limit:]

    def _add_activity(self, entry: dict[str, Any]) -> None:
        """Add an activity log entry, trimming if over capacity."""
        self._activity_log.append(entry)
        if len(self._activity_log) > self._max_activity_log:
            self._activity_log = self._activity_log[-self._max_activity_log:]
