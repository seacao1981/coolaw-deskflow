"""Unit tests for Worker Agent module."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from deskflow.orchestration.worker_agent import (
    WorkerAgent,
    WorkerAgentStatus,
    WorkerAgentConfig,
    TaskContext,
    create_default_worker,
    handle_shell_task,
    handle_file_task,
    handle_web_search_task,
    handle_code_generation_task,
    handle_text_processing_task,
)


# ============== WorkerAgentConfig Tests ==============

class TestWorkerAgentConfig:
    """Tests for WorkerAgentConfig dataclass."""

    def test_config_creation_basic(self):
        """Test basic config creation."""
        config = WorkerAgentConfig(
            worker_id="worker-1",
            capabilities=["python", "code"],
            max_concurrent_tasks=2,
        )

        assert config.worker_id == "worker-1"
        assert config.capabilities == ["python", "code"]
        assert config.max_concurrent_tasks == 2
        assert config.master_url == "http://localhost:8000/api/orchestration"
        assert config.heartbeat_interval == 10.0
        assert config.task_poll_interval == 1.0

    def test_config_creation_minimal(self):
        """Test config with minimal parameters."""
        config = WorkerAgentConfig(worker_id="test-worker")

        assert config.worker_id == "test-worker"
        assert config.capabilities == []
        assert config.max_concurrent_tasks == 1

    def test_config_custom_settings(self):
        """Test config with custom settings."""
        config = WorkerAgentConfig(
            worker_id="custom-worker",
            master_url="http://custom:8080/api",
            heartbeat_interval=30.0,
            task_poll_interval=2.0,
            reconnect_delay=10.0,
            max_reconnect_attempts=5,
        )

        assert config.master_url == "http://custom:8080/api"
        assert config.heartbeat_interval == 30.0
        assert config.reconnect_delay == 10.0
        assert config.max_reconnect_attempts == 5


# ============== TaskContext Tests ==============

class TestTaskContext:
    """Tests for TaskContext dataclass."""

    def test_context_creation(self):
        """Test task context creation."""
        ctx = TaskContext(
            task_id="task-1",
            task_type="code_generation",
            payload={"code": "print('hello')"},
        )

        assert ctx.task_id == "task-1"
        assert ctx.task_type == "code_generation"
        assert ctx.payload == {"code": "print('hello')"}
        assert ctx.progress == 0.0
        assert ctx.cancel_requested is False

    def test_context_to_dict(self):
        """Test context dictionary conversion."""
        ctx = TaskContext(
            task_id="1",
            task_type="test",
            payload={"key": "value"},
            progress=0.5,
        )

        d = {
            "task_id": ctx.task_id,
            "task_type": ctx.task_type,
            "payload": ctx.payload,
            "progress": ctx.progress,
        }

        assert d["task_id"] == "1"
        assert d["progress"] == 0.5


# ============== WorkerAgent Tests ==============

class TestWorkerAgent:
    """Tests for WorkerAgent class."""

    def test_agent_creation(self):
        """Test worker agent creation."""
        config = WorkerAgentConfig(worker_id="worker-1")
        agent = WorkerAgent(config)

        assert agent.config.worker_id == "worker-1"
        assert agent.status == WorkerAgentStatus.INITIALIZING
        assert agent._running is False
        assert len(agent._task_handlers) == 0

    def test_agent_register_handler(self):
        """Test registering task handler."""
        config = WorkerAgentConfig(worker_id="worker-1")
        agent = WorkerAgent(config)

        handler = MagicMock()
        agent.register_handler("test", handler)

        assert "test" in agent._task_handlers
        assert agent._task_handlers["test"] == handler

    def test_agent_register_wildcard_handler(self):
        """Test registering wildcard handler."""
        config = WorkerAgentConfig(worker_id="worker-1")
        agent = WorkerAgent(config)

        handler = MagicMock()
        agent.register_handler("*", handler)

        assert "*" in agent._task_handlers

    @pytest.mark.asyncio
    async def test_agent_start_stop(self):
        """Test agent start and stop."""
        config = WorkerAgentConfig(worker_id="worker-1")
        agent = WorkerAgent(config)

        # Mock the session and registration
        with patch.object(agent, '_register_with_master', new_callable=AsyncMock) as mock_register:
            with patch.object(agent, '_run_main_loop', new_callable=AsyncMock) as mock_loop:
                # Start and immediately stop
                asyncio.create_task(agent.start())
                await asyncio.sleep(0.1)
                await agent.stop()

                assert agent.status == WorkerAgentStatus.SHUTDOWN

    @pytest.mark.skip(reason="Requires complex aiohttp mock setup - integration test")
    @pytest.mark.asyncio
    async def test_agent_registration_success(self):
        """Test successful registration with master."""
        config = WorkerAgentConfig(worker_id="worker-1")
        agent = WorkerAgent(config)

        # This test requires proper aiohttp session mocking
        # Covered by integration tests instead
        pytest.skip("Integration test - requires aiohttp test utilities")

    @pytest.mark.skip(reason="Requires complex aiohttp mock setup - integration test")
    @pytest.mark.asyncio
    async def test_agent_registration_failure(self):
        """Test failed registration with master."""
        config = WorkerAgentConfig(worker_id="worker-1")
        agent = WorkerAgent(config)

        pytest.skip("Integration test - requires aiohttp test utilities")

    @pytest.mark.asyncio
    async def test_agent_heartbeat(self):
        """Test heartbeat sending."""
        config = WorkerAgentConfig(worker_id="worker-1")
        agent = WorkerAgent(config)

        # Heartbeat should not raise when session is None
        await agent._send_heartbeat()

        # Verify status update
        assert agent.status in [WorkerAgentStatus.INITIALIZING, WorkerAgentStatus.REGISTERED]

    @pytest.mark.skip(reason="Requires complex aiohttp mock setup - integration test")
    @pytest.mark.asyncio
    async def test_agent_poll_no_tasks(self):
        """Test polling when no tasks available."""
        config = WorkerAgentConfig(worker_id="worker-1")
        agent = WorkerAgent(config)

        pytest.skip("Integration test - requires aiohttp test utilities")

    @pytest.mark.skip(reason="Requires complex aiohttp mock setup - integration test")
    @pytest.mark.asyncio
    async def test_agent_poll_with_tasks(self):
        """Test polling when tasks are available."""
        config = WorkerAgentConfig(worker_id="worker-1")
        agent = WorkerAgent(config)

        pytest.skip("Integration test - requires aiohttp test utilities")

    @pytest.mark.asyncio
    async def test_agent_poll_max_concurrent(self):
        """Test polling respects max concurrent tasks."""
        config = WorkerAgentConfig(worker_id="worker-1", max_concurrent_tasks=2)
        agent = WorkerAgent(config)

        # Simulate max tasks already running
        agent._active_tasks = {
            "task-1": TaskContext("task-1", "test", {}),
            "task-2": TaskContext("task-2", "test", {}),
        }

        await agent._poll_for_tasks()

        # Should not poll when at capacity
        assert len(agent._active_tasks) == 2

    @pytest.mark.asyncio
    async def test_agent_execute_task_success(self):
        """Test successful task execution."""
        config = WorkerAgentConfig(worker_id="worker-1")
        agent = WorkerAgent(config)

        # Mock result reporting
        agent._report_result = AsyncMock()
        agent._report_progress = AsyncMock()

        # Register handler
        async def handler(task_id, payload, progress_cb):
            return {"result": "success"}

        agent.register_handler("test", handler)

        await agent._execute_task("task-1", "test", {"key": "value"})

        agent._report_result.assert_called_once_with("task-1", success=True, result={"result": "success"})
        assert agent._total_tasks_executed == 1

    @pytest.mark.asyncio
    async def test_agent_execute_task_no_handler(self):
        """Test task execution with no handler."""
        config = WorkerAgentConfig(worker_id="worker-1")
        agent = WorkerAgent(config)

        agent._report_result = AsyncMock()

        await agent._execute_task("task-1", "unknown", {})

        agent._report_result.assert_called_once()
        # Check the call was made with success=False
        call_kwargs = agent._report_result.call_args.kwargs
        assert call_kwargs.get("success") is False

    @pytest.mark.asyncio
    async def test_agent_execute_task_error(self):
        """Test task execution with error."""
        config = WorkerAgentConfig(worker_id="worker-1")
        agent = WorkerAgent(config)

        agent._report_result = AsyncMock()

        # Register handler that raises
        async def failing_handler(task_id, payload, progress_cb):
            raise RuntimeError("Task failed")

        agent.register_handler("test", failing_handler)

        await agent._execute_task("task-1", "test", {})

        agent._report_result.assert_called_once_with("task-1", success=False, error="Task failed")
        assert agent._total_tasks_failed == 1

    @pytest.mark.asyncio
    async def test_agent_report_progress(self):
        """Test progress reporting."""
        config = WorkerAgentConfig(worker_id="worker-1")
        agent = WorkerAgent(config)

        # Should not raise when session is None
        await agent._report_progress("task-1", 0.5, "Processing...")

    @pytest.mark.asyncio
    async def test_agent_report_result(self):
        """Test result reporting."""
        config = WorkerAgentConfig(worker_id="worker-1")
        agent = WorkerAgent(config)

        # Should not raise when session is None
        await agent._report_result("task-1", True, {"result": "data"})

    def test_agent_disconnection_handling(self):
        """Test disconnection handling."""
        config = WorkerAgentConfig(worker_id="worker-1", max_reconnect_attempts=3)
        agent = WorkerAgent(config)

        agent._reconnect_attempts = 2

        # Run disconnection handler
        asyncio.run(agent._handle_disconnection())

        # Should increment reconnect attempts
        assert agent._reconnect_attempts == 3
        assert agent.status == WorkerAgentStatus.DISCONNECTED

    def test_agent_disconnection_max_attempts(self):
        """Test disconnection after max attempts."""
        config = WorkerAgentConfig(worker_id="worker-1", max_reconnect_attempts=2)
        agent = WorkerAgent(config)

        agent._reconnect_attempts = 2
        agent._running = True

        asyncio.run(agent._handle_disconnection())

        # Should stop after max attempts
        assert agent._running is False


# ============== Built-in Handler Tests ==============

class TestBuiltInHandlers:
    """Tests for built-in task handlers."""

    @pytest.mark.asyncio
    async def test_shell_handler_success(self):
        """Test shell command handler success."""
        progress_called = False

        def progress_cb(task_id, progress, message):
            nonlocal progress_called
            progress_called = True

        result = await handle_shell_task(
            "task-1",
            {"command": "echo hello", "timeout": 5.0},
            progress_cb,
        )

        assert "stdout" in result
        assert "hello" in result["stdout"]
        assert result["returncode"] == 0
        assert progress_called is True

    @pytest.mark.asyncio
    async def test_shell_handler_timeout(self):
        """Test shell command handler timeout."""
        progress_cb = MagicMock()

        with pytest.raises(RuntimeError, match="timed out"):
            await handle_shell_task(
                "task-1",
                {"command": "sleep 10", "timeout": 0.1},
                progress_cb,
            )

    @pytest.mark.asyncio
    async def test_file_handler_read(self):
        """Test file read handler."""
        import tempfile
        import os

        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("test content")
            temp_path = f.name

        try:
            progress_cb = MagicMock()

            result = await handle_file_task(
                "task-1",
                {"operation": "read", "path": temp_path},
                progress_cb,
            )

            assert result["content"] == "test content"
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_file_handler_write(self):
        """Test file write handler."""
        import tempfile
        import os

        temp_path = tempfile.mktemp(suffix='.txt')

        try:
            progress_cb = MagicMock()

            result = await handle_file_task(
                "task-1",
                {"operation": "write", "path": temp_path, "content": "new content"},
                progress_cb,
            )

            assert result["written"] == 11

            # Verify file content
            with open(temp_path, 'r') as f:
                assert f.read() == "new content"
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_file_handler_delete(self):
        """Test file delete handler."""
        import tempfile
        import os

        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("to delete")
            temp_path = f.name

        try:
            progress_cb = MagicMock()

            result = await handle_file_task(
                "task-1",
                {"operation": "delete", "path": temp_path},
                progress_cb,
            )

            assert result["deleted"] is True
            assert not os.path.exists(temp_path)
        finally:
            # File should already be deleted
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_file_handler_exists(self):
        """Test file exists handler."""
        import tempfile
        import os

        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            temp_path = f.name

        try:
            progress_cb = MagicMock()

            # Test existing file
            result = await handle_file_task(
                "task-1",
                {"operation": "exists", "path": temp_path},
                progress_cb,
            )

            assert result["exists"] is True

            # Test non-existing file
            result = await handle_file_task(
                "task-2",
                {"operation": "exists", "path": "/nonexistent/path"},
                progress_cb,
            )

            assert result["exists"] is False
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_file_handler_no_path(self):
        """Test file handler with no path."""
        progress_cb = MagicMock()

        with pytest.raises(ValueError, match="File path is required"):
            await handle_file_task("task-1", {"operation": "read"}, progress_cb)

    @pytest.mark.asyncio
    async def test_file_handler_unknown_operation(self):
        """Test file handler with unknown operation."""
        progress_cb = MagicMock()

        with pytest.raises(ValueError, match="Unknown file operation"):
            await handle_file_task(
                "task-1",
                {"operation": "unknown", "path": "/tmp/test.txt"},
                progress_cb,
            )

    @pytest.mark.asyncio
    async def test_web_search_handler(self):
        """Test web search handler."""
        progress_cb = MagicMock()

        result = await handle_web_search_task(
            "task-1",
            {"query": "test query", "num_results": 3},
            progress_cb,
        )

        assert result["query"] == "test query"
        assert len(result["results"]) == 3
        assert "title" in result["results"][0]
        assert "url" in result["results"][0]

    @pytest.mark.asyncio
    async def test_web_search_handler_no_query(self):
        """Test web search handler with no query."""
        progress_cb = MagicMock()

        with pytest.raises(ValueError, match="Search query is required"):
            await handle_web_search_task("task-1", {}, progress_cb)

    @pytest.mark.asyncio
    async def test_code_generation_handler(self):
        """Test code generation handler."""
        progress_cb = MagicMock()

        result = await handle_code_generation_task(
            "task-1",
            {
                "language": "python",
                "description": "Test function",
                "requirements": ["fastapi", "pytest"],
            },
            progress_cb,
        )

        assert result["language"] == "python"
        assert "Test function" in result["code"]
        assert "fastapi" in result["code"]
        assert "pytest" in result["code"]
        assert "def main()" in result["code"]

    @pytest.mark.asyncio
    async def test_text_processing_uppercase(self):
        """Test text processing uppercase."""
        progress_cb = MagicMock()

        result = await handle_text_processing_task(
            "task-1",
            {"text": "hello world", "operation": "uppercase"},
            progress_cb,
        )

        assert result["result"] == "HELLO WORLD"
        assert result["operation"] == "uppercase"

    @pytest.mark.asyncio
    async def test_text_processing_lowercase(self):
        """Test text processing lowercase."""
        progress_cb = MagicMock()

        result = await handle_text_processing_task(
            "task-1",
            {"text": "HELLO WORLD", "operation": "lowercase"},
            progress_cb,
        )

        assert result["result"] == "hello world"

    @pytest.mark.asyncio
    async def test_text_processing_reverse(self):
        """Test text processing reverse."""
        progress_cb = MagicMock()

        result = await handle_text_processing_task(
            "task-1",
            {"text": "hello", "operation": "reverse"},
            progress_cb,
        )

        assert result["result"] == "olleh"

    @pytest.mark.asyncio
    async def test_text_processing_word_count(self):
        """Test text processing word count."""
        progress_cb = MagicMock()

        result = await handle_text_processing_task(
            "task-1",
            {"text": "one two three four", "operation": "word_count"},
            progress_cb,
        )

        assert result["result"]["word_count"] == 4
        assert result["result"]["char_count"] == len("one two three four")

    @pytest.mark.asyncio
    async def test_text_processing_summarize(self):
        """Test text processing summarize."""
        progress_cb = MagicMock()

        long_text = " ".join([f"word{i}" for i in range(100)])

        result = await handle_text_processing_task(
            "task-1",
            {"text": long_text, "operation": "summarize"},
            progress_cb,
        )

        # Should truncate to 50 words
        assert "..." in result["result"]
        assert len(result["result"].split()) <= 51


# ============== create_default_worker Tests ==============

class TestCreateDefaultWorker:
    """Tests for create_default_worker factory function."""

    def test_create_default_worker(self):
        """Test creating default worker."""
        config = WorkerAgentConfig(worker_id="default-worker")
        worker = create_default_worker(config)

        assert worker is not None
        assert worker.config.worker_id == "default-worker"

        # Check default handlers are registered
        assert "shell" in worker._task_handlers
        assert "file_operation" in worker._task_handlers
        assert "web_search" in worker._task_handlers
        assert "code_generation" in worker._task_handlers
        assert "text_processing" in worker._task_handlers
