"""Worker Agent - Standalone task executor for multi-agent system.

This module provides a standalone Worker Agent that can:
- Register with Master Agent
- Receive and execute tasks
- Report progress and heartbeats
- Submit results back to Master

Usage:
    python -m deskflow.orchestration.worker_agent --worker-id worker-1 --capabilities python,code
"""

from __future__ import annotations

import asyncio
import signal
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

import aiohttp

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


class WorkerAgentStatus(str, Enum):
    """Worker Agent status."""

    INITIALIZING = "initializing"
    CONNECTING = "connecting"
    REGISTERED = "registered"
    WORKING = "working"
    DISCONNECTED = "disconnected"
    SHUTDOWN = "shutdown"


@dataclass
class WorkerAgentConfig:
    """Configuration for Worker Agent.

    Attributes:
        worker_id: Unique worker identifier
        capabilities: List of task types this worker can handle
        max_concurrent_tasks: Maximum concurrent tasks
        master_url: Master Agent URL for registration
        heartbeat_interval: Heartbeat interval in seconds
        task_poll_interval: Task polling interval in seconds
        reconnect_delay: Delay before reconnecting after disconnection
        max_reconnect_attempts: Maximum reconnection attempts
    """

    worker_id: str
    capabilities: list[str] = field(default_factory=list)
    max_concurrent_tasks: int = 1
    master_url: str = "http://localhost:8000/api/orchestration"
    heartbeat_interval: float = 10.0
    task_poll_interval: float = 1.0
    reconnect_delay: float = 5.0
    max_reconnect_attempts: int = 3


@dataclass
class TaskContext:
    """Context for a running task.

    Attributes:
        task_id: Task ID
        task_type: Task type
        payload: Task payload
        start_time: Task start timestamp
        progress: Current progress (0.0 to 1.0)
    """

    task_id: str
    task_type: str
    payload: dict[str, Any]
    start_time: float = field(default_factory=time.time)
    progress: float = 0.0
    cancel_requested: bool = False


class WorkerAgent:
    """Standalone Worker Agent that executes tasks from Master Agent.

    The Worker Agent:
    1. Registers with Master Agent on startup
    2. Polls for tasks from Master Agent
    3. Executes tasks using registered handlers
    4. Reports progress and heartbeats
    5. Submits results back to Master

    Example:
        agent = WorkerAgent(
            worker_id="worker-1",
            capabilities=["python", "code"],
            master_url="http://localhost:8000/api/orchestration"
        )

        # Register task handler
        agent.register_handler("python", execute_python_code)

        # Start the agent
        await agent.run()
    """

    def __init__(self, config: WorkerAgentConfig) -> None:
        self.config = config
        self.status = WorkerAgentStatus.INITIALIZING
        self._session: aiohttp.ClientSession | None = None
        self._running = False
        self._active_tasks: dict[str, TaskContext] = {}
        self._task_handlers: dict[str, Callable] = {}
        self._reconnect_attempts = 0
        self._last_heartbeat = time.time()
        self._last_task_poll = time.time()
        self._total_tasks_executed = 0
        self._total_tasks_failed = 0
        self._shutdown_event = asyncio.Event()

    def register_handler(self, task_type: str, handler: Callable) -> None:
        """Register a task handler for a specific task type.

        Args:
            task_type: Type of task to handle
            handler: Async function that takes (task_id, payload) and returns result

        Example:
            async def python_handler(task_id: str, payload: dict) -> dict:
                code = payload.get("code", "")
                # Execute code...
                return {"success": True, "output": output}

            agent.register_handler("python", python_handler)
        """
        self._task_handlers[task_type] = handler
        logger.info("task_handler_registered", task_type=task_type)

    async def start(self) -> None:
        """Start the Worker Agent."""
        self.status = WorkerAgentStatus.CONNECTING
        self._running = True

        try:
            # Create HTTP session
            self._session = aiohttp.ClientSession()
            logger.info("http_session_created")

            # Register with Master Agent
            await self._register_with_master()

            # Start main loop
            await self._run_main_loop()

        except Exception as e:
            logger.error("worker_agent_start_error", error=str(e))
            self.status = WorkerAgentStatus.DISCONNECTED
            raise
        finally:
            if self._session:
                await self._session.close()

    async def stop(self) -> None:
        """Stop the Worker Agent gracefully."""
        logger.info("stopping_worker_agent")
        self._running = False
        self.status = WorkerAgentStatus.SHUTDOWN

        # Cancel active tasks
        for task_id, ctx in list(self._active_tasks.items()):
            ctx.cancel_requested = True
            logger.info("task_cancel_requested", task_id=task_id)

        # Wait for tasks to finish
        if self._active_tasks:
            await asyncio.sleep(0.5)

        # Close session
        if self._session:
            await self._session.close()
            self._session = None

        self._shutdown_event.set()
        logger.info("worker_agent_stopped")

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()

    async def _register_with_master(self) -> None:
        """Register with Master Agent."""
        if not self._session:
            raise RuntimeError("Session not initialized")

        url = f"{self.config.master_url}/workers/register"
        payload = {
            "worker_id": self.config.worker_id,
            "capabilities": self.config.capabilities,
            "max_concurrent_tasks": self.config.max_concurrent_tasks,
        }

        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status == 200:
                    self.status = WorkerAgentStatus.REGISTERED
                    self._reconnect_attempts = 0
                    logger.info(
                        "registered_with_master",
                        worker_id=self.config.worker_id,
                    )
                else:
                    error = await resp.text()
                    logger.error("registration_failed", status=resp.status, error=error)
                    raise RuntimeError(f"Registration failed: {error}")
        except aiohttp.ClientError as e:
            logger.error("registration_connection_error", error=str(e))
            raise

    async def _run_main_loop(self) -> None:
        """Main loop for polling tasks and sending heartbeats."""
        while self._running:
            try:
                current_time = time.time()

                # Send heartbeat
                if current_time - self._last_heartbeat >= self.config.heartbeat_interval:
                    await self._send_heartbeat()
                    self._last_heartbeat = current_time

                # Poll for tasks
                if current_time - self._last_task_poll >= self.config.task_poll_interval:
                    await self._poll_for_tasks()
                    self._last_task_poll = current_time

                # Check for cancelled tasks
                await self._check_cancelled_tasks()

                # Small sleep to prevent busy-waiting
                await asyncio.sleep(0.1)

            except aiohttp.ClientError as e:
                logger.error("connection_error", error=str(e))
                await self._handle_disconnection()

            except Exception as e:
                logger.error("main_loop_error", error=str(e))
                await asyncio.sleep(1.0)

    async def _send_heartbeat(self) -> None:
        """Send heartbeat to Master Agent."""
        if not self._session:
            return

        # Use worker status endpoint or dedicated heartbeat endpoint
        # For now, we'll just log the heartbeat
        self.status = WorkerAgentStatus.REGISTERED if not self._active_tasks else WorkerAgentStatus.WORKING
        logger.debug(
            "heartbeat_sent",
            worker_id=self.config.worker_id,
            active_tasks=len(self._active_tasks),
            total_executed=self._total_tasks_executed,
            total_failed=self._total_tasks_failed,
        )

    async def _poll_for_tasks(self) -> None:
        """Poll Master Agent for new tasks."""
        if not self._session:
            return

        # Check if we can accept more tasks
        available_slots = self.config.max_concurrent_tasks - len(self._active_tasks)
        if available_slots <= 0:
            return

        # Poll for tasks - check queue status
        url = f"{self.config.master_url}/queue/stats"

        try:
            async with self._session.get(url) as resp:
                if resp.status != 200:
                    return

                stats = await resp.json()
                pending = stats.get("pending_tasks", 0)

                if pending > 0:
                    # Try to claim a task by executing
                    await self._claim_and_execute_task()

        except aiohttp.ClientError:
            pass  # Will retry on next poll

    async def _claim_and_execute_task(self) -> None:
        """Claim and execute a task from the queue."""
        if not self._session:
            return

        # For now, we'll use the execute endpoint
        # In a real implementation, this would claim a specific task
        url = f"{self.config.master_url}/execute"

        try:
            # This is a simplified implementation
            # A real implementation would have a dedicated "claim task" endpoint
            async with self._session.post(url, params={"timeout": 0.1}) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info("task_execution_result", result=result)
        except aiohttp.ClientError:
            pass

    async def _execute_task(self, task_id: str, task_type: str, payload: dict[str, Any]) -> None:
        """Execute a task using the registered handler.

        Args:
            task_id: Task ID
            task_type: Type of task
            payload: Task payload
        """
        # Check if we have a handler for this task type
        handler = self._task_handlers.get(task_type) or self._task_handlers.get("*")

        if not handler:
            logger.warning("no_handler_for_task", task_id=task_id, task_type=task_type)
            await self._report_result(task_id, success=False, error=f"No handler for task type: {task_type}")
            return

        # Create task context
        ctx = TaskContext(
            task_id=task_id,
            task_type=task_type,
            payload=payload,
        )
        self._active_tasks[task_id] = ctx

        try:
            self.status = WorkerAgentStatus.WORKING
            logger.info("task_started", task_id=task_id, task_type=task_type)

            # Execute the task
            if asyncio.iscoroutinefunction(handler):
                result = await handler(task_id, payload, self._report_progress)
            else:
                result = handler(task_id, payload, self._report_progress)

            # Report success
            await self._report_result(task_id, success=True, result=result)
            self._total_tasks_executed += 1
            logger.info("task_completed", task_id=task_id)

        except asyncio.CancelledError:
            logger.info("task_cancelled", task_id=task_id)
            await self._report_result(task_id, success=False, error="Task cancelled")
            self._total_tasks_failed += 1

        except Exception as e:
            logger.error("task_execution_error", task_id=task_id, error=str(e))
            await self._report_result(task_id, success=False, error=str(e))
            self._total_tasks_failed += 1

        finally:
            del self._active_tasks[task_id]
            self.status = WorkerAgentStatus.REGISTERED if not self._active_tasks else WorkerAgentStatus.WORKING

    async def _report_progress(self, task_id: str, progress: float, message: str = "") -> None:
        """Report task progress to Master Agent.

        Args:
            task_id: Task ID
            progress: Progress value (0.0 to 1.0)
            message: Optional progress message
        """
        if not self._session:
            return

        url = f"{self.config.master_url}/tasks/progress"
        payload = {
            "task_id": task_id,
            "worker_id": self.config.worker_id,
            "progress": progress,
            "message": message,
        }

        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status == 200:
                    logger.debug("progress_reported", task_id=task_id, progress=progress)
        except aiohttp.ClientError:
            logger.debug("progress_report_failed", task_id=task_id)

    async def _report_result(self, task_id: str, success: bool, result: Any = None, error: str | None = None) -> None:
        """Report task result to Master Agent.

        Args:
            task_id: Task ID
            success: Whether the task succeeded
            result: Task result data
            error: Error message if failed
        """
        if not self._session:
            return

        # The result is typically reported through the Master's task execution
        # For standalone workers, we might need a dedicated endpoint
        logger.info(
            "task_result",
            task_id=task_id,
            success=success,
            error=error,
            result=result,
        )

    async def _check_cancelled_tasks(self) -> None:
        """Check for tasks that have been cancelled."""
        # In a real implementation, this would poll Master for cancellation requests
        pass

    async def _handle_disconnection(self) -> None:
        """Handle disconnection from Master Agent."""
        self.status = WorkerAgentStatus.DISCONNECTED
        self._reconnect_attempts += 1

        if self._reconnect_attempts >= self.config.max_reconnect_attempts:
            logger.error("max_reconnect_attempts_reached")
            self._running = False
            return

        logger.info(
            "reconnecting",
            attempt=self._reconnect_attempts,
            max_attempts=self.config.max_reconnect_attempts,
        )

        await asyncio.sleep(self.config.reconnect_delay)

        try:
            await self._register_with_master()
        except Exception:
            pass  # Will retry on next iteration


# Built-in task handlers for common task types

async def handle_shell_task(task_id: str, payload: dict[str, Any], report_progress: Callable) -> dict[str, Any]:
    """Handle shell command execution task.

    Args:
        task_id: Task ID
        payload: Task payload with 'command' key
        report_progress: Progress reporting callback

    Returns:
        Dict with 'stdout', 'stderr', 'returncode'
    """
    import subprocess

    command = payload.get("command", "")
    timeout = payload.get("timeout", 30.0)

    report_progress(task_id, 0.1, f"Executing: {command}")

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        report_progress(task_id, 1.0, "Command completed")

        return {
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "returncode": proc.returncode,
        }

    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"Command timed out after {timeout}s")


async def handle_file_task(task_id: str, payload: dict[str, Any], report_progress: Callable) -> dict[str, Any]:
    """Handle file operation task.

    Args:
        task_id: Task ID
        payload: Task payload with 'operation', 'path', and optional 'content'
        report_progress: Progress reporting callback

    Returns:
        Dict with operation result
    """
    import os

    operation = payload.get("operation", "read")
    path = payload.get("path", "")

    if not path:
        raise ValueError("File path is required")

    report_progress(task_id, 0.1, f"{operation} file: {path}")

    if operation == "read":
        with open(path, "r") as f:
            content = f.read()
        report_progress(task_id, 1.0, "File read completed")
        return {"content": content}

    elif operation == "write":
        content = payload.get("content", "")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        report_progress(task_id, 1.0, "File write completed")
        return {"written": len(content)}

    elif operation == "delete":
        os.remove(path)
        report_progress(task_id, 1.0, "File deleted")
        return {"deleted": True}

    elif operation == "exists":
        exists = os.path.exists(path)
        report_progress(task_id, 1.0, f"File exists: {exists}")
        return {"exists": exists}

    else:
        raise ValueError(f"Unknown file operation: {operation}")


async def handle_web_search_task(task_id: str, payload: dict[str, Any], report_progress: Callable) -> dict[str, Any]:
    """Handle web search task.

    Args:
        task_id: Task ID
        payload: Task payload with 'query' and optional 'num_results'
        report_progress: Progress reporting callback

    Returns:
        Dict with search results
    """
    query = payload.get("query", "")
    num_results = payload.get("num_results", 5)

    if not query:
        raise ValueError("Search query is required")

    report_progress(task_id, 0.1, f"Searching: {query}")

    # Placeholder - would use actual search API
    await asyncio.sleep(0.5)  # Simulate search

    report_progress(task_id, 1.0, f"Found {num_results} results")

    return {
        "query": query,
        "results": [
            {"title": f"Result {i+1}", "url": f"https://example.com/result{i+1}", "snippet": "Sample result"}
            for i in range(num_results)
        ],
    }


async def handle_code_generation_task(task_id: str, payload: dict[str, Any], report_progress: Callable) -> dict[str, Any]:
    """Handle code generation task.

    Args:
        task_id: Task ID
        payload: Task payload with 'language', 'description', and optional 'requirements'
        report_progress: Progress reporting callback

    Returns:
        Dict with generated code
    """
    language = payload.get("language", "python")
    description = payload.get("description", "")
    requirements = payload.get("requirements", [])

    report_progress(task_id, 0.1, f"Generating {language} code...")

    # Placeholder - would use LLM for actual code generation
    await asyncio.sleep(0.5)  # Simulate generation

    generated_code = f"""# Generated {language} code
# Description: {description}
# Requirements: {', '.join(requirements)}

def main():
    print("Hello from generated code!")

if __name__ == "__main__":
    main()
"""

    report_progress(task_id, 1.0, "Code generation completed")

    return {
        "language": language,
        "code": generated_code,
        "description": description,
    }


async def handle_text_processing_task(task_id: str, payload: dict[str, Any], report_progress: Callable) -> dict[str, Any]:
    """Handle text processing task.

    Args:
        task_id: Task ID
        payload: Task payload with 'text' and 'operation'
        report_progress: Progress reporting callback

    Returns:
        Dict with processed text
    """
    text = payload.get("text", "")
    operation = payload.get("operation", "uppercase")

    report_progress(task_id, 0.1, f"Processing text: {operation}")

    if operation == "uppercase":
        result = text.upper()
    elif operation == "lowercase":
        result = text.lower()
    elif operation == "reverse":
        result = text[::-1]
    elif operation == "word_count":
        result = {"word_count": len(text.split()), "char_count": len(text)}
    elif operation == "summarize":
        # Placeholder summarization
        words = text.split()
        result = " ".join(words[:50]) + ("..." if len(words) > 50 else "")
    else:
        result = text

    report_progress(task_id, 1.0, "Text processing completed")

    return {"result": result, "operation": operation}


def create_default_worker(config: WorkerAgentConfig) -> WorkerAgent:
    """Create a Worker Agent with default handlers registered.

    Args:
        config: Worker Agent configuration

    Returns:
        Worker Agent with built-in handlers registered
    """
    worker = WorkerAgent(config)

    # Register default handlers
    worker.register_handler("shell", handle_shell_task)
    worker.register_handler("file_operation", handle_file_task)
    worker.register_handler("web_search", handle_web_search_task)
    worker.register_handler("code_generation", handle_code_generation_task)
    worker.register_handler("text_processing", handle_text_processing_task)

    logger.info("default_handlers_registered")

    return worker


async def main() -> None:
    """Main entry point for Worker Agent."""
    import argparse

    parser = argparse.ArgumentParser(description="Worker Agent for multi-agent system")
    parser.add_argument("--worker-id", required=True, help="Unique worker identifier")
    parser.add_argument("--capabilities", default="*", help="Comma-separated list of capabilities")
    parser.add_argument("--master-url", default="http://localhost:8000/api/orchestration", help="Master Agent URL")
    parser.add_argument("--max-concurrent", type=int, default=1, help="Maximum concurrent tasks")
    parser.add_argument("--heartbeat-interval", type=float, default=10.0, help="Heartbeat interval in seconds")

    args = parser.parse_args()

    # Parse capabilities
    capabilities = [c.strip() for c in args.capabilities.split(",")] if args.capabilities else ["*"]

    # Create config
    config = WorkerAgentConfig(
        worker_id=args.worker_id,
        capabilities=capabilities,
        max_concurrent_tasks=args.max_concurrent,
        master_url=args.master_url,
        heartbeat_interval=args.heartbeat_interval,
    )

    # Create worker with default handlers
    worker = create_default_worker(config)

    # Setup signal handlers
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("shutdown_signal_received")
        asyncio.create_task(worker.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    # Start worker
    try:
        await worker.start()
    except Exception as e:
        logger.error("worker_error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
