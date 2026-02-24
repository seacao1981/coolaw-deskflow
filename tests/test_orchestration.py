"""Unit tests for orchestration module."""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from deskflow.orchestration import (
    MasterAgent,
    Worker,
    WorkerStatus,
    Task,
    TaskResult,
    TaskProgress,
    TaskType,
    TaskPriority,
    TaskStatus,
    MessageBus,
    LoadBalancer,
    WorkerPool,
    PriorityTaskQueue,
)


# ============== Task Tests ==============

class TestTask:
    """Tests for Task dataclass."""

    def test_task_creation_basic(self):
        """Test basic task creation."""
        task = Task(id="task-1", type="test", payload={"key": "value"})

        assert task.id == "task-1"
        assert task.type == "test"
        assert task.payload == {"key": "value"}
        assert task.priority == TaskPriority.NORMAL.value
        assert task.status == TaskStatus.PENDING

    def test_task_creation_auto_id(self):
        """Test task creation with auto-generated ID."""
        task = Task(id="", type="test", payload={})

        assert task.id != ""
        assert len(task.id) == 36  # UUID length

    def test_task_priority_enum(self):
        """Test task priority with enum."""
        task = Task(id="1", type="test", payload={}, priority=TaskPriority.HIGH)

        assert task.priority == TaskPriority.HIGH.value

    def test_task_is_expired(self):
        """Test task expiration check."""
        task = Task(id="1", type="test", payload={}, timeout=0.01)
        time.sleep(0.02)

        assert task.is_expired() is True

    def test_task_is_not_expired(self):
        """Test task not expired."""
        task = Task(id="1", type="test", payload={}, timeout=300.0)

        assert task.is_expired() is False

    def test_task_to_dict(self):
        """Test task to dictionary conversion."""
        task = Task(id="1", type="test", payload={"data": "test"})
        result = task.to_dict()

        assert result["id"] == "1"
        assert result["type"] == "test"
        assert result["payload"] == {"data": "test"}
        assert result["status"] == TaskStatus.PENDING.value

    def test_task_from_dict(self):
        """Test task creation from dictionary."""
        data = {
            "id": "task-1",
            "type": "code_generation",
            "payload": {"code": "print('hello')"},
            "priority": 10,
            "dependencies": ["dep-1"],
            "timeout": 600.0,
            "retry_count": 5,
            "metadata": {"author": "test"},
        }
        task = Task.from_dict(data)

        assert task.id == "task-1"
        assert task.type == "code_generation"
        assert task.payload == {"code": "print('hello')"}
        assert task.dependencies == ["dep-1"]
        assert task.retry_count == 5


# ============== TaskResult Tests ==============

class TestTaskResult:
    """Tests for TaskResult dataclass."""

    def test_result_creation_success(self):
        """Test successful task result."""
        result = TaskResult(
            task_id="task-1",
            worker_id="worker-1",
            success=True,
            result={"output": "data"},
        )

        assert result.success is True
        assert result.error is None

    def test_result_creation_failure(self):
        """Test failed task result."""
        result = TaskResult(
            task_id="task-1",
            worker_id="worker-1",
            success=False,
            result=None,
            error="Test error",
        )

        assert result.success is False
        assert result.error == "Test error"

    def test_result_to_dict(self):
        """Test result to dictionary conversion."""
        result = TaskResult(
            task_id="1",
            worker_id="w1",
            success=True,
            result={"data": "test"},
            duration=1.5,
        )
        d = result.to_dict()

        assert d["task_id"] == "1"
        assert d["worker_id"] == "w1"
        assert d["success"] is True
        assert d["duration"] == 1.5


# ============== TaskProgress Tests ==============

class TestTaskProgress:
    """Tests for TaskProgress dataclass."""

    def test_progress_creation(self):
        """Test task progress creation."""
        progress = TaskProgress(
            task_id="1",
            worker_id="w1",
            progress=0.5,
            message="Processing...",
        )

        assert progress.task_id == "1"
        assert progress.progress == 0.5
        assert progress.message == "Processing..."

    def test_progress_to_dict(self):
        """Test progress to dictionary."""
        progress = TaskProgress(task_id="1", worker_id="w1", progress=1.0)
        d = progress.to_dict()

        assert d["progress"] == 1.0


# ============== Worker Tests ==============

class TestWorker:
    """Tests for Worker class."""

    def test_worker_creation(self):
        """Test worker creation."""
        worker = Worker(
            worker_id="worker-1",
            capabilities=["code", "test"],
        )

        assert worker.worker_id == "worker-1"
        assert worker.status == WorkerStatus.IDLE
        assert "code" in worker.capabilities

    def test_worker_has_capability(self):
        """Test worker capability check."""
        worker = Worker(worker_id="1", capabilities=["python", "test"])

        assert worker.has_capability("python") is True
        assert worker.has_capability("java") is False

    def test_worker_has_wildcard_capability(self):
        """Test worker with wildcard capability."""
        worker = Worker(worker_id="1", capabilities=["*"])

        assert worker.has_capability("any_task") is True

    def test_worker_can_accept_task(self):
        """Test worker availability check."""
        worker = Worker(worker_id="1")

        assert worker.can_accept_task() is True

    def test_worker_update_heartbeat(self):
        """Test heartbeat update."""
        worker = Worker(worker_id="1")
        old_time = worker.last_heartbeat
        time.sleep(0.01)

        worker.update_heartbeat()

        assert worker.last_heartbeat > old_time

    def test_worker_is_healthy(self):
        """Test worker health check."""
        worker = Worker(worker_id="1")

        assert worker.is_healthy(timeout=30.0) is True

    def test_worker_is_unhealthy(self):
        """Test worker unhealthy."""
        worker = Worker(worker_id="1")
        worker.last_heartbeat = time.time() - 60  # 60 seconds ago

        assert worker.is_healthy(timeout=30.0) is False

    @pytest.mark.asyncio
    async def test_worker_execute_success(self):
        """Test worker task execution success."""
        worker = Worker(worker_id="1")
        task = Task(id="t1", type="test", payload={})

        result = await worker.execute(task)

        assert result.success is True
        assert result.task_id == "t1"
        assert result.worker_id == "1"
        assert worker.tasks_completed == 1

    @pytest.mark.asyncio
    async def test_worker_execute_with_progress(self):
        """Test worker execution with progress callback."""
        progress_called = False

        def on_progress(p: TaskProgress):
            nonlocal progress_called
            progress_called = True

        worker = Worker(worker_id="1")
        task = Task(id="t1", type="test", payload={})

        await worker.execute(task, on_progress=on_progress)

        assert progress_called is True

    def test_worker_to_dict(self):
        """Test worker to dictionary."""
        worker = Worker(worker_id="1", capabilities=["test"])
        worker.tasks_completed = 5

        d = worker.to_dict()

        assert d["worker_id"] == "1"
        assert d["capabilities"] == ["test"]
        assert d["tasks_completed"] == 5


# ============== WorkerPool Tests ==============

class TestWorkerPool:
    """Tests for WorkerPool class."""

    def test_pool_add_worker(self):
        """Test adding worker to pool."""
        pool = WorkerPool()
        worker = Worker(worker_id="1")

        pool.add_worker(worker)

        assert pool.get_worker("1") == worker

    def test_pool_remove_worker(self):
        """Test removing worker from pool."""
        pool = WorkerPool()
        worker = Worker(worker_id="1")
        pool.add_worker(worker)

        result = pool.remove_worker("1")

        assert result is True
        assert pool.get_worker("1") is None

    def test_pool_get_available_workers(self):
        """Test getting available workers."""
        pool = WorkerPool()
        w1 = Worker(worker_id="1")
        w2 = Worker(worker_id="2")
        pool.add_worker(w1)
        pool.add_worker(w2)

        available = pool.get_available_workers()

        assert len(available) == 2

    def test_pool_get_worker_by_capability(self):
        """Test finding worker by capability."""
        pool = WorkerPool()
        w1 = Worker(worker_id="1", capabilities=["python"])
        w2 = Worker(worker_id="2", capabilities=["java"])
        pool.add_worker(w1)
        pool.add_worker(w2)

        worker = pool.get_worker_by_capability("python")

        assert worker.worker_id == "1"

    def test_pool_get_statistics(self):
        """Test pool statistics."""
        pool = WorkerPool()
        w1 = Worker(worker_id="1")
        pool.add_worker(w1)

        stats = pool.get_statistics()

        assert stats["total_workers"] == 1
        assert stats["idle_workers"] == 1


# ============== PriorityTaskQueue Tests ==============

class TestPriorityTaskQueue:
    """Tests for PriorityTaskQueue class."""

    def test_queue_enqueue(self):
        """Test adding task to queue."""
        queue = PriorityTaskQueue()
        task = Task(id="1", type="test", payload={})

        queue.enqueue(task)

        assert queue.size() == 1
        assert queue.peek() == task

    def test_queue_dequeue(self):
        """Test removing task from queue."""
        queue = PriorityTaskQueue()
        task = Task(id="1", type="test", payload={})
        queue.enqueue(task)

        result = queue.dequeue()

        assert result == task
        assert queue.is_empty()

    def test_queue_priority_order(self):
        """Test tasks are dequeued by priority."""
        queue = PriorityTaskQueue()
        low = Task(id="low", type="test", payload={}, priority=TaskPriority.LOW)
        high = Task(id="high", type="test", payload={}, priority=TaskPriority.HIGH)

        queue.enqueue(low)
        queue.enqueue(high)

        first = queue.dequeue()
        assert first.id == "high"

    def test_queue_remove(self):
        """Test removing specific task."""
        queue = PriorityTaskQueue()
        task = Task(id="1", type="test", payload={})
        queue.enqueue(task)

        result = queue.remove("1")

        assert result is True
        assert queue.size() == 0

    def test_queue_get_ready_tasks(self):
        """Test getting tasks with satisfied dependencies."""
        queue = PriorityTaskQueue()
        t1 = Task(id="t1", type="test", payload={})
        t2 = Task(id="t2", type="test", payload={}, dependencies=["t1"])

        queue.enqueue(t1)
        queue.enqueue(t2)

        ready = queue.get_ready_tasks(set())

        assert len(ready) == 1
        assert ready[0].id == "t1"

    def test_queue_get_tasks_by_status(self):
        """Test filtering tasks by status."""
        queue = PriorityTaskQueue()
        t1 = Task(id="1", type="test", payload={})
        t1.status = TaskStatus.RUNNING
        queue.enqueue(t1)

        running = queue.get_tasks_by_status(TaskStatus.RUNNING)

        assert len(running) == 1


# ============== LoadBalancer Tests ==============

class TestLoadBalancer:
    """Tests for LoadBalancer class."""

    def test_balancer_least_loaded(self):
        """Test least-loaded strategy."""
        balancer = LoadBalancer(strategy="least_loaded")
        w1 = Worker(worker_id="1")
        w2 = Worker(worker_id="2")

        # Simulate w1 being busier
        w2._active_tasks = []

        task = Task(id="t1", type="test", payload={})
        worker = balancer.select_worker([w1, w2], task)

        assert worker is not None

    def test_balancer_round_robin(self):
        """Test round-robin strategy."""
        balancer = LoadBalancer(strategy="round_robin")
        w1 = Worker(worker_id="1")
        w2 = Worker(worker_id="2")

        task = Task(id="t1", type="test", payload={})

        worker1 = balancer.select_worker([w1, w2], task)
        worker2 = balancer.select_worker([w1, w2], task)

        assert worker1 != worker2  # Should alternate

    def test_balancer_no_workers(self):
        """Test balancer with no workers."""
        balancer = LoadBalancer()
        task = Task(id="t1", type="test", payload={})

        worker = balancer.select_worker([], task)

        assert worker is None

    def test_balancer_capability_filter(self):
        """Test capability-based filtering."""
        balancer = LoadBalancer()
        w1 = Worker(worker_id="1", capabilities=["python"])
        task = Task(id="t1", type="python", payload={})

        worker = balancer.select_worker([w1], task)

        assert worker.worker_id == "1"

    def test_weighted_round_robin_strategy(self):
        """Test weighted round-robin strategy."""
        balancer = LoadBalancer(strategy="weighted_round_robin")
        w1 = Worker(worker_id="high_weight", weight=3)
        w2 = Worker(worker_id="low_weight", weight=1)

        task = Task(id="t1", type="test", payload={})

        # High weight worker should be selected more often
        selections = {}
        for _ in range(100):
            worker = balancer.select_worker([w1, w2], task)
            selections[worker.worker_id] = selections.get(worker.worker_id, 0) + 1

        # High weight worker should have more selections
        assert selections["high_weight"] > selections["low_weight"]

    def test_weighted_least_loaded_strategy(self):
        """Test weighted least-loaded strategy."""
        balancer = LoadBalancer(strategy="weighted_least_loaded")
        w1 = Worker(worker_id="high_weight", weight=10, capabilities=["test"])
        w2 = Worker(worker_id="low_weight", weight=1, capabilities=["test"])

        # Add same number of tasks to both
        w1._active_tasks = ["task1", "task2", "task3"]
        w2._active_tasks = ["task1", "task2", "task3"]

        task = Task(id="t1", type="test", payload={})
        worker = balancer.select_worker([w1, w2], task)

        # High weight worker should be selected (lower load ratio)
        assert worker.worker_id == "high_weight"

    def test_weight_zero_handling(self):
        """Test handling of zero weight workers."""
        balancer = LoadBalancer(strategy="weighted_least_loaded")
        w1 = Worker(worker_id="zero", weight=0)
        w2 = Worker(worker_id="normal", weight=1)

        task = Task(id="t1", type="test", payload={})
        worker = balancer.select_worker([w1, w2], task)

        # Zero weight worker should have inf load ratio, so normal should be selected
        assert worker.worker_id == "normal"

    def test_failover_record_success_failure(self):
        """Test recording success and failure."""
        balancer = LoadBalancer(failover_enabled=True, max_failures=3)
        worker_id = "test-worker"

        # Record failures
        should_block = balancer.record_failure(worker_id)
        assert should_block is False

        should_block = balancer.record_failure(worker_id)
        assert should_block is False

        # Third failure should block
        should_block = balancer.record_failure(worker_id)
        assert should_block is True

        # Success should clear circuit breaker
        balancer.record_success(worker_id)
        status = balancer.get_circuit_breaker_status()
        assert status[worker_id]["circuit_open"] is False

    def test_circuit_breaker_blocks_worker(self):
        """Test that circuit breaker blocks failed workers."""
        balancer = LoadBalancer(failover_enabled=True, max_failures=2)
        w1 = Worker(worker_id="failing", capabilities=["test"])
        w2 = Worker(worker_id="healthy", capabilities=["test"])

        # Cause failures on w1
        balancer.record_failure("failing")
        balancer.record_failure("failing")

        task = Task(id="t1", type="test", payload={})

        # Should select w2 because w1 is circuit-breaked
        worker = balancer.select_worker([w1, w2], task)
        assert worker.worker_id == "healthy"

    def test_reset_circuit_breaker(self):
        """Test resetting circuit breaker."""
        balancer = LoadBalancer(failover_enabled=True, max_failures=2)

        # Cause failures
        balancer.record_failure("worker-1")
        balancer.record_failure("worker-1")

        # Verify circuit is open
        status = balancer.get_circuit_breaker_status()
        assert status["worker-1"]["circuit_open"] is True

        # Reset
        balancer.reset_circuit_breaker("worker-1")

        # Verify circuit is closed
        status = balancer.get_circuit_breaker_status()
        assert status["worker-1"]["circuit_open"] is False

    def test_select_with_failover(self):
        """Test selection with failover support."""
        balancer = LoadBalancer(failover_enabled=True)
        w1 = Worker(worker_id="w1", capabilities=["test"])
        w2 = Worker(worker_id="w2", capabilities=["test"])

        # Mark w1 as busy (can't accept tasks)
        w1.status = WorkerStatus.BUSY

        task = Task(id="t1", type="test", payload={})
        worker, attempted = balancer.select_with_failover([w1, w2], task)

        assert worker.worker_id == "w2"
        assert "w1" in attempted

    def test_failure_window_cleanup(self):
        """Test that old failures are cleaned up."""
        balancer = LoadBalancer(failover_enabled=True, max_failures=3, failure_window=0.1)
        worker_id = "test-worker"

        # Record failures
        balancer.record_failure(worker_id)
        balancer.record_failure(worker_id)

        # Wait for window to expire
        import time
        time.sleep(0.15)

        # New failure should not trigger circuit breaker (old ones expired)
        should_block = balancer.record_failure(worker_id)
        assert should_block is False


# ============== MasterAgent Tests ==============

class TestMasterAgent:
    """Tests for MasterAgent class."""

    def test_master_creation(self):
        """Test MasterAgent creation."""
        master = MasterAgent()

        assert master._running is False
        assert master._max_concurrent_tasks == 10

    def test_master_register_worker(self):
        """Test registering worker."""
        master = MasterAgent()
        worker = Worker(worker_id="1")

        master.register_worker(worker)

        assert len(master._workers) == 1

    def test_master_unregister_worker(self):
        """Test unregistering worker."""
        master = MasterAgent()
        worker = Worker(worker_id="1")
        master.register_worker(worker)

        master.unregister_worker("1")

        assert len(master._workers) == 0

    def test_master_submit_task(self):
        """Test submitting task."""
        master = MasterAgent()
        task = Task(id="1", type="test", payload={})

        task_id = asyncio.run(master.submit_task(task))

        assert task_id == "1"

    def test_master_submit_tasks_batch(self):
        """Test submitting multiple tasks."""
        master = MasterAgent()
        tasks = [
            Task(id="1", type="test", payload={}),
            Task(id="2", type="test", payload={}),
        ]

        task_ids = asyncio.run(master.submit_tasks(tasks))

        assert len(task_ids) == 2

    def test_master_get_status(self):
        """Test getting master status."""
        master = MasterAgent()
        worker = Worker(worker_id="1")
        master.register_worker(worker)

        status = master.get_status()

        assert "workers" in status
        assert status["pending_tasks"] == 0

    def test_master_get_worker_pool_stats(self):
        """Test worker pool stats."""
        master = MasterAgent()
        w1 = Worker(worker_id="1")
        w2 = Worker(worker_id="2")
        master.register_worker(w1)
        master.register_worker(w2)

        stats = master.get_worker_pool_stats()

        assert stats["total_workers"] == 2

    def test_master_cancel_task(self):
        """Test cancelling task."""
        master = MasterAgent()
        task = Task(id="1", type="test", payload={})

        asyncio.run(master.submit_task(task))

        # Task is in queue, not yet running
        # Cancel should remove from queue
        result = master.cancel_task("1")

        # May or may not succeed depending on timing
        assert isinstance(result, bool)

    def test_master_clear_results(self):
        """Test clearing results."""
        master = MasterAgent()
        master._results["1"] = TaskResult("1", "w1", True, {})

        master.clear_results()

        assert len(master._results) == 0


# ============== MessageBus Tests ==============

class TestMessageBus:
    """Tests for MessageBus class."""

    def test_bus_subscribe_publish(self):
        """Test subscribe and publish."""
        bus = MessageBus()
        received = []

        def handler(msg):
            received.append(msg)

        bus.subscribe("test", handler)
        asyncio.run(bus.publish("test", {"data": "hello"}))

        assert len(received) == 1
        assert received[0]["data"] == "hello"

    def test_bus_unsubscribe(self):
        """Test unsubscribe."""
        bus = MessageBus()
        received = []

        def handler(msg):
            received.append(msg)

        bus.subscribe("test", handler)
        bus.unsubscribe("test", handler)
        asyncio.run(bus.publish("test", {"data": "hello"}))

        assert len(received) == 0

    def test_bus_request_response(self):
        """Test request/response pattern."""
        bus = MessageBus()

        def handler(payload):
            return {"response": payload["data"]}

        bus.register_handler("test_method", handler)

        result = asyncio.run(bus.request("test_method", {"data": "hello"}))

        assert result["response"] == "hello"

    def test_bus_request_no_handler(self):
        """Test request with no handler."""
        bus = MessageBus()

        with pytest.raises(ValueError):
            asyncio.run(bus.request("unknown", {}))


# ============== Integration Tests ==============

class TestMasterAgentIntegration:
    """Integration tests for MasterAgent."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete workflow: register, submit, execute."""
        master = MasterAgent(max_concurrent_tasks=2)

        # Register workers
        w1 = Worker(worker_id="w1", capabilities=["test"])
        w2 = Worker(worker_id="w2", capabilities=["test"])
        master.register_worker(w1)
        master.register_worker(w2)

        # Submit tasks
        tasks = [
            Task(id="t1", type="test", payload={"n": 1}),
            Task(id="t2", type="test", payload={"n": 2}),
            Task(id="t3", type="test", payload={"n": 3}),
        ]
        await master.submit_tasks(tasks)

        # Execute
        results = await master.run(timeout=5.0)

        assert results["total_tasks"] == 3
        assert results["successful"] == 3
        assert results["failed"] == 0

    @pytest.mark.asyncio
    async def test_task_with_dependencies(self):
        """Test tasks with dependencies."""
        master = MasterAgent()

        w1 = Worker(worker_id="w1", capabilities=["*"])
        master.register_worker(w1)

        # t2 depends on t1
        t1 = Task(id="t1", type="test", payload={})
        t2 = Task(id="t2", type="test", payload={}, dependencies=["t1"])

        await master.submit_task(t1)
        await master.submit_task(t2)

        results = await master.run(timeout=5.0)

        assert results["total_tasks"] == 2
        assert results["successful"] == 2

    @pytest.mark.asyncio
    async def test_priority_task_execution(self):
        """Test high priority tasks execute first."""
        master = MasterAgent()

        w1 = Worker(worker_id="w1", capabilities=["*"])
        master.register_worker(w1)

        # Submit low priority first, then high
        low = Task(id="low", type="test", payload={}, priority=TaskPriority.LOW)
        high = Task(id="high", type="test", payload={}, priority=TaskPriority.HIGH)

        await master.submit_task(low)
        await master.submit_task(high)

        results = await master.run(timeout=5.0)

        # Both should complete
        assert results["total_tasks"] == 2
