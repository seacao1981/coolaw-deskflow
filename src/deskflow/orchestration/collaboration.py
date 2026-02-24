"""Multi-Agent collaboration system with Master/Worker architecture."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


class WorkerStatus(str, Enum):
    """Worker status."""

    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"


class TaskType(str, Enum):
    """Task type for categorization."""

    CODE_GENERATION = "code_generation"
    FILE_OPERATION = "file_operation"
    WEB_SEARCH = "web_search"
    DATA_ANALYSIS = "data_analysis"
    TEXT_PROCESSING = "text_processing"
    IMAGE_PROCESSING = "image_processing"
    VOICE_PROCESSING = "voice_process"
    CUSTOM = "custom"


class TaskPriority(int, Enum):
    """Task priority levels."""

    LOW = 0
    NORMAL = 5
    HIGH = 10
    CRITICAL = 15


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Task for worker to execute.

    Attributes:
        id: Unique task identifier
        type: Task type/category
        payload: Task input data
        priority: Priority level (higher = more urgent)
        dependencies: List of task IDs that must complete before this task
        timeout: Maximum execution time in seconds
        retry_count: Number of retry attempts on failure
        metadata: Additional task metadata
        created_at: Task creation timestamp
        status: Current task status
    """

    id: str
    type: str
    payload: dict[str, Any]
    priority: int = TaskPriority.NORMAL
    dependencies: list[str] = field(default_factory=list)
    timeout: float = 300.0  # 5 minutes default
    retry_count: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    status: TaskStatus = TaskStatus.PENDING

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())
        if isinstance(self.priority, TaskPriority):
            self.priority = self.priority.value

    def is_expired(self) -> bool:
        """Check if task has exceeded timeout."""
        elapsed = time.time() - self.created_at
        return elapsed > self.timeout

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "payload": self.payload,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """Create Task from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=data.get("type", TaskType.CUSTOM.value),
            payload=data.get("payload", {}),
            priority=data.get("priority", TaskPriority.NORMAL),
            dependencies=data.get("dependencies", []),
            timeout=data.get("timeout", 300.0),
            retry_count=data.get("retry_count", 3),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            status=TaskStatus(data.get("status", TaskStatus.PENDING.value)),
        )


@dataclass
class TaskResult:
    """Result of task execution.

    Attributes:
        task_id: ID of the executed task
        worker_id: ID of the worker that executed the task
        success: Whether the task succeeded
        result: Task output data
        error: Error message if failed
        duration: Execution time in seconds
        retries_used: Number of retry attempts used
    """

    task_id: str
    worker_id: str
    success: bool
    result: Any
    error: str | None = None
    duration: float = 0.0
    retries_used: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "worker_id": self.worker_id,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "duration": self.duration,
            "retries_used": self.retries_used,
        }


@dataclass
class TaskProgress:
    """Task progress update for real-time tracking."""

    task_id: str
    worker_id: str
    progress: float  # 0.0 to 1.0
    message: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "worker_id": self.worker_id,
            "progress": self.progress,
            "message": self.message,
            "timestamp": self.timestamp,
        }


class Worker:
    """Agent worker that executes tasks.

    Attributes:
        worker_id: Unique worker identifier
        capabilities: List of task types this worker can handle
        status: Current worker status
        current_task: Task currently being executed (if any)
        tasks_completed: Total number of completed tasks
        tasks_failed: Total number of failed tasks
        last_heartbeat: Last heartbeat timestamp
    """

    def __init__(
        self,
        worker_id: str,
        capabilities: list[str] | None = None,
        max_concurrent_tasks: int = 1,
        weight: int = 1,
    ) -> None:
        self.worker_id = worker_id
        self.capabilities = capabilities or []
        self.status = WorkerStatus.IDLE
        self._current_task: Task | None = None
        self._max_concurrent_tasks = max_concurrent_tasks
        self._active_tasks: list[Task] = []
        self.weight = weight  # For weighted load balancing

        # Statistics
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.last_heartbeat = time.time()

        # Callbacks
        self._on_progress: Callable[[TaskProgress], None] | None = None

    def update_heartbeat(self) -> None:
        """Update heartbeat timestamp."""
        self.last_heartbeat = time.time()

    def is_healthy(self, timeout: float = 30.0) -> bool:
        """Check if worker is healthy based on heartbeat."""
        return (time.time() - self.last_heartbeat) < timeout

    def can_accept_task(self) -> bool:
        """Check if worker can accept new tasks."""
        return (
            self.status == WorkerStatus.IDLE
            and len(self._active_tasks) < self._max_concurrent_tasks
        )

    def has_capability(self, task_type: str) -> bool:
        """Check if worker has the required capability."""
        return not task_type or task_type in self.capabilities or "*" in self.capabilities

    async def execute(
        self,
        task: Task,
        on_progress: Callable[[TaskProgress], None] | None = None,
    ) -> TaskResult:
        """Execute a task.

        Args:
            task: Task to execute
            on_progress: Optional callback for progress updates

        Returns:
            TaskResult with execution outcome
        """
        self.status = WorkerStatus.BUSY
        self._current_task = task
        self._active_tasks.append(task)
        start_time = time.time()

        try:
            # Placeholder - would execute actual task
            await asyncio.sleep(0.1)  # Simulate work

            # Report progress if callback provided
            if on_progress:
                on_progress(TaskProgress(
                    task_id=task.id,
                    worker_id=self.worker_id,
                    progress=1.0,
                    message="Task completed",
                ))

            result = TaskResult(
                task_id=task.id,
                worker_id=self.worker_id,
                success=True,
                result={"processed": True, "task_type": task.type},
                duration=time.time() - start_time,
                retries_used=0,
            )
            self.tasks_completed += 1
        except Exception as e:
            result = TaskResult(
                task_id=task.id,
                worker_id=self.worker_id,
                success=False,
                result=None,
                error=str(e),
                duration=time.time() - start_time,
                retries_used=task.retry_count,
            )
            self.tasks_failed += 1
        finally:
            self.status = WorkerStatus.IDLE
            self._current_task = None
            self._active_tasks.remove(task)
            self.update_heartbeat()

        return result

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "worker_id": self.worker_id,
            "capabilities": self.capabilities,
            "status": self.status.value,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "is_healthy": self.is_healthy(),
            "last_heartbeat": self.last_heartbeat,
            "active_tasks": len(self._active_tasks),
            "max_concurrent": self._max_concurrent_tasks,
            "weight": self.weight,
        }


class WorkerPool:
    """Pool of workers for task execution.

    Manages worker registration, discovery, and selection.
    """

    def __init__(self) -> None:
        self._workers: dict[str, Worker] = {}
        self._health_check_interval = 30.0  # seconds
        self._last_health_check = time.time()

    def add_worker(self, worker: Worker) -> None:
        """Add a worker to the pool."""
        self._workers[worker.worker_id] = worker
        logger.info("worker_added_to_pool", worker_id=worker.worker_id)

    def remove_worker(self, worker_id: str) -> bool:
        """Remove a worker from the pool."""
        if worker_id in self._workers:
            del self._workers[worker_id]
            logger.info("worker_removed_from_pool", worker_id=worker_id)
            return True
        return False

    def get_worker(self, worker_id: str) -> Worker | None:
        """Get a specific worker by ID."""
        return self._workers.get(worker_id)

    def get_available_workers(self) -> list[Worker]:
        """Get all available (idle and healthy) workers."""
        now = time.time()
        if now - self._last_health_check > self._health_check_interval:
            self._run_health_check()
            self._last_health_check = now

        return [
            w for w in self._workers.values()
            if w.can_accept_task() and w.is_healthy()
        ]

    def get_worker_by_capability(self, capability: str) -> Worker | None:
        """Get an available worker with specific capability."""
        available = self.get_available_workers()
        for worker in available:
            if worker.has_capability(capability):
                return worker
        return None

    def get_workers_by_capabilities(
        self,
        required_capabilities: list[str],
    ) -> list[Worker]:
        """Get all available workers with any of the required capabilities."""
        available = self.get_available_workers()
        return [
            w for w in available
            if any(w.has_capability(cap) for cap in required_capabilities)
        ]

    def get_all_workers(self) -> list[Worker]:
        """Get all registered workers."""
        return list(self._workers.values())

    def get_statistics(self) -> dict[str, Any]:
        """Get pool statistics."""
        total = len(self._workers)
        idle = sum(1 for w in self._workers.values() if w.status == WorkerStatus.IDLE)
        busy = sum(1 for w in self._workers.values() if w.status == WorkerStatus.BUSY)
        unhealthy = sum(1 for w in self._workers.values() if not w.is_healthy())

        return {
            "total_workers": total,
            "idle_workers": idle,
            "busy_workers": busy,
            "unhealthy_workers": unhealthy,
            "total_tasks_completed": sum(w.tasks_completed for w in self._workers.values()),
            "total_tasks_failed": sum(w.tasks_failed for w in self._workers.values()),
        }

    def _run_health_check(self) -> None:
        """Run health check on all workers."""
        for worker in self._workers.values():
            if not worker.is_healthy():
                worker.status = WorkerStatus.OFFLINE
                logger.warning("worker_unhealthy", worker_id=worker.worker_id)


class MasterAgent:
    """Master agent that coordinates workers.

    Features:
    - Task decomposition and distribution
    - Load balancing across workers
    - Result aggregation
    - Worker health monitoring
    - Progress tracking
    - Dependency resolution
    """

    def __init__(
        self,
        load_balancer_strategy: str = "least_loaded",
        max_concurrent_tasks: int = 10,
    ) -> None:
        self._workers: dict[str, Worker] = {}
        self._task_queue = PriorityTaskQueue()
        self._results: dict[str, TaskResult] = {}
        self._running = False
        self._load_balancer = LoadBalancer(strategy=load_balancer_strategy)
        self._max_concurrent_tasks = max_concurrent_tasks
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._progress_callbacks: list[Callable[[TaskProgress], None]] = []
        self._completed_task_ids: set[str] = set()

    def register_worker(self, worker: Worker) -> None:
        """Register a worker."""
        self._workers[worker.worker_id] = worker
        logger.info("worker_registered", worker_id=worker.worker_id)

    def unregister_worker(self, worker_id: str) -> None:
        """Unregister a worker."""
        if worker_id in self._workers:
            del self._workers[worker_id]
            logger.info("worker_unregistered", worker_id=worker_id)

    def subscribe_progress(self, callback: Callable[[TaskProgress], None]) -> None:
        """Subscribe to task progress updates."""
        self._progress_callbacks.append(callback)

    def unsubscribe_progress(self, callback: Callable[[TaskProgress], None]) -> None:
        """Unsubscribe from task progress updates."""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)

    def _notify_progress(self, progress: TaskProgress) -> None:
        """Notify all progress subscribers."""
        for callback in self._progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(progress))
                else:
                    callback(progress)
            except Exception as e:
                logger.error("progress_callback_error", error=str(e))

    async def submit_task(self, task: Task) -> str:
        """Submit a task for execution."""
        self._task_queue.enqueue(task)
        logger.info("task_submitted", task_id=task.id, type=task.type, priority=task.priority)
        return task.id

    async def submit_tasks(self, tasks: list[Task]) -> list[str]:
        """Submit multiple tasks."""
        ids = []
        for task in tasks:
            ids.append(await self.submit_task(task))
        logger.info("tasks_submitted", count=len(tasks))
        return ids

    async def run(self, timeout: float = 60.0) -> dict[str, Any]:
        """Run task distribution loop.

        Args:
            timeout: Maximum time to wait for all tasks

        Returns:
            Aggregated results
        """
        self._running = True
        start_time = time.time()

        while not self._task_queue.is_empty() and (time.time() - start_time) < timeout:
            # Check for completed tasks
            await self._check_completed_tasks()

            # Get ready tasks (dependencies satisfied)
            ready_tasks = self._task_queue.get_ready_tasks(self._completed_task_ids)

            if not ready_tasks:
                await asyncio.sleep(0.05)
                continue

            # Get available workers
            available_workers = [
                w for w in self._workers.values()
                if w.can_accept_task() and w.is_healthy()
            ]

            if not available_workers:
                await asyncio.sleep(0.05)
                continue

            # Distribute tasks to workers
            for task in ready_tasks:
                if len(self._active_tasks) >= self._max_concurrent_tasks:
                    break

                worker = self._load_balancer.select_worker(available_workers, task)
                if worker:
                    task.status = TaskStatus.RUNNING
                    asyncio_task = asyncio.create_task(
                        self._execute_task(task, worker)
                    )
                    self._active_tasks[task.id] = asyncio_task
                    self._task_queue.remove(task.id)
                    available_workers.remove(worker)

            await asyncio.sleep(0.01)

        # Wait for remaining tasks
        if self._active_tasks:
            await asyncio.gather(*self._active_tasks.values(), return_exceptions=True)

        self._running = False
        return self._aggregate_results()

    async def _execute_task(self, task: Task, worker: Worker) -> None:
        """Execute a task on a worker."""
        try:
            result = await worker.execute(
                task,
                on_progress=lambda p: self._notify_progress(p),
            )
            self._results[task.id] = result
            task.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED

            if result.success:
                self._completed_task_ids.add(task.id)
                logger.info("task_completed", task_id=task.id, worker_id=worker.worker_id)
            else:
                logger.error("task_failed", task_id=task.id, error=result.error)

        except Exception as e:
            result = TaskResult(
                task_id=task.id,
                worker_id=worker.worker_id,
                success=False,
                result=None,
                error=str(e),
            )
            self._results[task.id] = result
            task.status = TaskStatus.FAILED
            logger.error("task_execution_error", task_id=task.id, error=str(e))

        finally:
            if task.id in self._active_tasks:
                del self._active_tasks[task.id]

    async def _check_completed_tasks(self) -> None:
        """Check for completed async tasks."""
        completed = [
            task_id for task_id, async_task in self._active_tasks.items()
            if async_task.done()
        ]
        for task_id in completed:
            del self._active_tasks[task_id]

    def _aggregate_results(self) -> dict[str, Any]:
        """Aggregate all task results."""
        if not self._results:
            return {
                "total_tasks": 0,
                "successful": 0,
                "failed": 0,
                "pending": self._task_queue.size(),
                "results": {},
            }

        successful = sum(1 for r in self._results.values() if r.success)
        failed = len(self._results) - successful
        total_duration = sum(r.duration for r in self._results.values())

        return {
            "total_tasks": len(self._results),
            "successful": successful,
            "failed": failed,
            "pending": self._task_queue.size(),
            "active": len(self._active_tasks),
            "average_duration": total_duration / len(self._results) if self._results else 0,
            "results": {
                task_id: result.to_dict()
                for task_id, result in self._results.items()
            },
        }

    def get_status(self) -> dict[str, Any]:
        """Get master agent status."""
        return {
            "workers": {wid: w.to_dict() for wid, w in self._workers.items()},
            "pending_tasks": self._task_queue.size(),
            "active_tasks": len(self._active_tasks),
            "completed_tasks": len(self._results),
            "running": self._running,
            "load_balancer_strategy": self._load_balancer.strategy,
            "max_concurrent_tasks": self._max_concurrent_tasks,
        }

    def get_worker_pool_stats(self) -> dict[str, Any]:
        """Get worker pool statistics."""
        total = len(self._workers)
        idle = sum(1 for w in self._workers.values() if w.status == WorkerStatus.IDLE)
        busy = sum(1 for w in self._workers.values() if w.status == WorkerStatus.BUSY)
        offline = sum(1 for w in self._workers.values() if w.status == WorkerStatus.OFFLINE)

        return {
            "total_workers": total,
            "idle_workers": idle,
            "busy_workers": busy,
            "offline_workers": offline,
            "total_tasks_completed": sum(w.tasks_completed for w in self._workers.values()),
            "total_tasks_failed": sum(w.tasks_failed for w in self._workers.values()),
        }

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task."""
        # Cancel pending task
        if self._task_queue.remove(task_id):
            logger.info("task_cancelled", task_id=task_id)
            return True

        # Cancel running task
        if task_id in self._active_tasks:
            self._active_tasks[task_id].cancel()
            logger.info("task_cancelled_running", task_id=task_id)
            return True

        return False

    def get_task_result(self, task_id: str) -> TaskResult | None:
        """Get the result of a completed task."""
        return self._results.get(task_id)

    def get_all_results(self) -> dict[str, TaskResult]:
        """Get all task results."""
        return self._results.copy()

    def clear_results(self) -> None:
        """Clear all task results."""
        self._results.clear()
        self._completed_task_ids.clear()


class MessageBus:
    """Simple message bus for inter-agent communication.

    Supports PUB/SUB and REQ/REP patterns.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable]] = {}
        self._request_handlers: dict[str, Callable] = {}

    def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to a topic."""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(callback)
        logger.debug("subscribed_to_topic", topic=topic)

    def unsubscribe(self, topic: str, callback: Callable) -> None:
        """Unsubscribe from a topic."""
        if topic in self._subscribers:
            self._subscribers[topic] = [c for c in self._subscribers[topic] if c != callback]

    async def publish(self, topic: str, message: Any) -> None:
        """Publish a message to a topic."""
        if topic in self._subscribers:
            for callback in self._subscribers[topic]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(message)
                    else:
                        callback(message)
                except Exception as e:
                    logger.error("subscriber_error", topic=topic, error=str(e))

    def register_handler(self, method: str, handler: Callable) -> None:
        """Register a request handler."""
        self._request_handlers[method] = handler

    async def request(self, method: str, payload: Any) -> Any:
        """Send a request and wait for response."""
        if method not in self._request_handlers:
            raise ValueError(f"No handler registered for method: {method}")

        handler = self._request_handlers[method]
        if asyncio.iscoroutinefunction(handler):
            return await handler(payload)
        return handler(payload)


class LoadBalancer:
    """Load balancer for distributing tasks across workers.

    Strategies:
    - round_robin: Distribute tasks evenly across workers
    - weighted_round_robin: Distribute based on worker weights
    - least_loaded: Send to worker with fewest active tasks
    - weighted_least_loaded: Send based on weight-adjusted load
    - capability_based: Prioritize workers with matching capabilities
    - random: Random worker selection

    Failover:
    - Automatically switches to backup worker if primary fails
    - Tracks failure count per worker for circuit breaking
    """

    def __init__(
        self,
        strategy: str = "least_loaded",
        failover_enabled: bool = True,
        max_failures: int = 3,
        failure_window: float = 60.0,
    ) -> None:
        self.strategy = strategy
        self._round_robin_index = 0
        self._weighted_index: dict[str, int] = {}

        # Failover configuration
        self.failover_enabled = failover_enabled
        self.max_failures = max_failures
        self.failure_window = failure_window

        # Worker failure tracking
        self._failure_counts: dict[str, list[float]] = {}
        self._circuit_breaker: dict[str, bool] = {}  # True = open (blocked)

    def select_worker(
        self,
        workers: list[Worker],
        task: Task,
    ) -> Worker | None:
        """Select a worker for the task."""
        if not workers:
            return None

        # Filter by capabilities
        capable = [w for w in workers if w.has_capability(task.type)]

        if not capable:
            # Fall back to any available worker
            capable = [w for w in workers if w.can_accept_task()]

        if not capable:
            return None

        # Remove circuit-breaked workers
        if self.failover_enabled:
            capable = [w for w in capable if not self._is_circuit_open(w.worker_id)]

        if not capable:
            return None

        # Apply strategy
        if self.strategy == "round_robin":
            return self._round_robin_select(capable)
        elif self.strategy == "weighted_round_robin":
            return self._weighted_round_robin_select(capable)
        elif self.strategy == "least_loaded":
            return self._least_loaded(capable)
        elif self.strategy == "weighted_least_loaded":
            return self._weighted_least_loaded(capable)
        elif self.strategy == "random":
            import random
            return random.choice(capable)
        else:
            # Default: capability-based with least_loaded fallback
            return self._least_loaded(capable)

    def select_with_failover(
        self,
        workers: list[Worker],
        task: Task,
    ) -> tuple[Worker | None, list[str]]:
        """Select a worker with failover support.

        Returns:
            Tuple of (selected_worker, attempted_worker_ids)
        """
        if not workers:
            return None, []

        attempted = []
        available = workers.copy()

        while available:
            # Select next worker based on strategy
            worker = self.select_worker(available, task)

            if worker is None:
                break

            attempted.append(worker.worker_id)

            # Check if worker is available
            if worker.can_accept_task():
                return worker, attempted

            # Worker unavailable, remove from list and try next
            available.remove(worker)

        # All workers busy or unavailable
        return None, attempted

    def record_success(self, worker_id: str) -> None:
        """Record a successful task execution."""
        if worker_id in self._failure_counts:
            # Clear failure count on success
            self._failure_counts[worker_id] = []
        if worker_id in self._circuit_breaker:
            self._circuit_breaker[worker_id] = False

    def record_failure(self, worker_id: str) -> bool:
        """Record a failed task execution.

        Returns:
            True if worker should be circuit-breaked
        """
        if not self.failover_enabled:
            return False

        now = time.time()

        # Initialize failure tracking if needed
        if worker_id not in self._failure_counts:
            self._failure_counts[worker_id] = []

        # Add failure timestamp
        self._failure_counts[worker_id].append(now)

        # Remove old failures outside the window
        cutoff = now - self.failure_window
        self._failure_counts[worker_id] = [
            t for t in self._failure_counts[worker_id] if t > cutoff
        ]

        # Check if we should open circuit breaker
        if len(self._failure_counts[worker_id]) >= self.max_failures:
            self._circuit_breaker[worker_id] = True
            return True

        return False

    def reset_circuit_breaker(self, worker_id: str) -> None:
        """Reset circuit breaker for a worker."""
        self._circuit_breaker[worker_id] = False
        self._failure_counts[worker_id] = []

    def _is_circuit_open(self, worker_id: str) -> bool:
        """Check if circuit breaker is open for worker."""
        return self._circuit_breaker.get(worker_id, False)

    def get_circuit_breaker_status(self) -> dict[str, dict[str, Any]]:
        """Get circuit breaker status for all workers."""
        status = {}
        for worker_id in set(list(self._failure_counts.keys()) + list(self._circuit_breaker.keys())):
            status[worker_id] = {
                "circuit_open": self._circuit_breaker.get(worker_id, False),
                "failure_count": len(self._failure_counts.get(worker_id, [])),
                "max_failures": self.max_failures,
            }
        return status

    def _round_robin_select(self, workers: list[Worker]) -> Worker:
        """Select worker using round-robin."""
        self._round_robin_index = (self._round_robin_index + 1) % len(workers)
        return workers[self._round_robin_index]

    def _weighted_round_robin_select(self, workers: list[Worker]) -> Worker:
        """Select worker using weighted round-robin.

        Workers with higher weights receive more tasks proportionally.
        Uses virtual ticket approach: each worker gets tickets proportional to weight.
        """
        if not workers:
            return None

        # Initialize weighted index if needed
        for w in workers:
            if w.worker_id not in self._weighted_index:
                self._weighted_index[w.worker_id] = 0

        # Calculate total weight
        total_weight = sum(w.weight for w in workers)
        if total_weight <= 0:
            # Fallback to equal weights
            for w in workers:
                w.weight = 1
            total_weight = len(workers)

        # Use cumulative position approach
        # Each worker has a "position" that advances by total_weight each time selected
        # We select the worker whose position/weight ratio is smallest
        min_ratio = float("inf")
        selected = workers[0]

        for worker in workers:
            ratio = self._weighted_index[worker.worker_id] / max(worker.weight, 1)
            if ratio < min_ratio:
                min_ratio = ratio
                selected = worker

        # Advance selected worker's position by total_weight
        self._weighted_index[selected.worker_id] += total_weight

        return selected

    def _least_loaded(self, workers: list[Worker]) -> Worker:
        """Select worker with least active tasks."""
        return min(workers, key=lambda w: len(w._active_tasks))

    def _weighted_least_loaded(self, workers: list[Worker]) -> Worker:
        """Select worker with least load relative to its weight.

        Workers with higher weights can handle more concurrent tasks.
        Load ratio = active_tasks / weight
        """
        def load_ratio(worker: Worker) -> float:
            if worker.weight <= 0:
                return float("inf")
            return len(worker._active_tasks) / worker.weight

        return min(workers, key=load_ratio)


class PriorityTaskQueue:
    """Priority queue for tasks.

    Tasks are ordered by priority (higher first), then by creation time (older first).
    """

    def __init__(self) -> None:
        self._tasks: list[Task] = []
        self._task_index: dict[str, Task] = {}

    def enqueue(self, task: Task) -> None:
        """Add a task to the queue."""
        self._tasks.append(task)
        self._task_index[task.id] = task
        self._sort()
        logger.debug("task_enqueued", task_id=task.id, priority=task.priority)

    def dequeue(self) -> Task | None:
        """Remove and return the highest priority task."""
        if not self._tasks:
            return None
        task = self._tasks.pop(0)
        if task.id in self._task_index:
            del self._task_index[task.id]
        logger.debug("task_dequeued", task_id=task.id)
        return task

    def peek(self) -> Task | None:
        """Return the highest priority task without removing it."""
        return self._tasks[0] if self._tasks else None

    def remove(self, task_id: str) -> bool:
        """Remove a specific task from the queue."""
        if task_id in self._task_index:
            task = self._task_index.pop(task_id)
            self._tasks.remove(task)
            return True
        return False

    def get_pending_tasks(self) -> list[Task]:
        """Get all pending tasks."""
        return self._tasks.copy()

    def get_tasks_by_status(self, status: TaskStatus) -> list[Task]:
        """Get tasks filtered by status."""
        return [t for t in self._tasks if t.status == status]

    def get_tasks_by_type(self, task_type: str) -> list[Task]:
        """Get tasks filtered by type."""
        return [t for t in self._tasks if t.type == task_type]

    def get_ready_tasks(self, completed_task_ids: set[str]) -> list[Task]:
        """Get tasks whose dependencies are satisfied."""
        ready = []
        for task in self._tasks:
            if task.status == TaskStatus.PENDING:
                deps_satisfied = all(dep_id in completed_task_ids for dep_id in task.dependencies)
                if deps_satisfied:
                    ready.append(task)
        return ready

    def size(self) -> int:
        """Get queue size."""
        return len(self._tasks)

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._tasks) == 0

    def clear(self) -> None:
        """Clear all tasks from the queue."""
        self._tasks.clear()
        self._task_index.clear()

    def _sort(self) -> None:
        """Sort tasks by priority (desc) then creation time (asc)."""
        self._tasks.sort(key=lambda t: (-t.priority, t.created_at))
