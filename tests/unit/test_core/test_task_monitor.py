"""Tests for TaskMonitor."""

from __future__ import annotations

import time

from deskflow.core.task_monitor import TaskMonitor


class TestTaskMonitor:
    """Tests for TaskMonitor."""

    def test_initial_state(self, task_monitor: TaskMonitor) -> None:
        status = task_monitor.get_status()
        assert status.is_online is True
        assert status.is_busy is False
        assert status.current_task is None
        assert status.total_conversations == 0
        assert status.total_tool_calls == 0
        assert status.total_tokens_used == 0

    def test_record_conversation(self, task_monitor: TaskMonitor) -> None:
        task_monitor.record_conversation()
        task_monitor.record_conversation()
        status = task_monitor.get_status()
        assert status.total_conversations == 2

    def test_record_tool_call(self, task_monitor: TaskMonitor) -> None:
        task_monitor.record_tool_call("shell", 150.0, True)
        task_monitor.record_tool_call("file", 20.0, False)
        status = task_monitor.get_status()
        assert status.total_tool_calls == 2

    def test_record_tokens(self, task_monitor: TaskMonitor) -> None:
        task_monitor.record_tokens(100, 50)
        task_monitor.record_tokens(200, 100)
        status = task_monitor.get_status()
        assert status.total_tokens_used == 450

    def test_set_busy_and_idle(self, task_monitor: TaskMonitor) -> None:
        task_monitor.set_busy("processing chat")
        status = task_monitor.get_status()
        assert status.is_busy is True
        assert status.current_task == "processing chat"

        task_monitor.set_idle()
        status = task_monitor.get_status()
        assert status.is_busy is False
        assert status.current_task is None

    def test_uptime(self, task_monitor: TaskMonitor) -> None:
        time.sleep(0.05)
        status = task_monitor.get_status()
        assert status.uptime_seconds >= 0.04

    def test_get_status_with_external_info(self, task_monitor: TaskMonitor) -> None:
        status = task_monitor.get_status(
            memory_count=42,
            active_tools=3,
            available_tools=5,
            llm_provider="anthropic",
            llm_model="claude-3.5-sonnet",
        )
        assert status.memory_count == 42
        assert status.active_tools == 3
        assert status.available_tools == 5
        assert status.llm_provider == "anthropic"
        assert status.llm_model == "claude-3.5-sonnet"

    def test_activity_log(self, task_monitor: TaskMonitor) -> None:
        task_monitor.record_tool_call("shell", 100.0, True)
        task_monitor.record_tokens(50, 25)

        activity = task_monitor.get_recent_activity()
        assert len(activity) == 2
        assert activity[0]["type"] == "tool_call"
        assert activity[1]["type"] == "llm_call"

    def test_activity_log_limit(self, task_monitor: TaskMonitor) -> None:
        for i in range(10):
            task_monitor.record_tool_call(f"tool_{i}", 10.0, True)

        recent = task_monitor.get_recent_activity(limit=3)
        assert len(recent) == 3

    def test_activity_log_trimming(self) -> None:
        monitor = TaskMonitor()
        monitor._max_activity_log = 5
        for i in range(10):
            monitor.record_tool_call(f"tool_{i}", 10.0, True)

        assert len(monitor._activity_log) == 5
