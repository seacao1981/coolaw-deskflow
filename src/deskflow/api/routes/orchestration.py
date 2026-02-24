"""Orchestration API routes for Master Agent task dispatching."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any

from deskflow.orchestration import (
    MasterAgent,
    Worker,
    Task,
    TaskType,
    TaskPriority,
    TaskStatus,
    WorkerStatus,
    PriorityTaskQueue,
    WorkerRegistry,
    WorkerRegistryConfig,
    ServiceDiscovery,
)
from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/orchestration", tags=["orchestration"])

# Global master agent instance
_master_agent: MasterAgent | None = None
_task_queue: PriorityTaskQueue | None = None
_worker_registry: WorkerRegistry | None = None
_service_discovery: ServiceDiscovery | None = None


def get_master_agent() -> MasterAgent:
    """Get the global master agent instance."""
    global _master_agent
    if _master_agent is None:
        _master_agent = MasterAgent()
    return _master_agent


def get_task_queue() -> PriorityTaskQueue:
    """Get the global task queue instance."""
    global _task_queue
    if _task_queue is None:
        _task_queue = PriorityTaskQueue()
    return _task_queue


def get_worker_registry() -> WorkerRegistry:
    """Get the global worker registry instance."""
    global _worker_registry
    if _worker_registry is None:
        _worker_registry = WorkerRegistry()
    return _worker_registry


def get_service_discovery() -> ServiceDiscovery:
    """Get the global service discovery instance."""
    global _service_discovery
    if _service_discovery is None:
        _service_discovery = ServiceDiscovery(get_worker_registry())
    return _service_discovery


class WorkerRegisterRequest(BaseModel):
    """Request to register a worker."""

    worker_id: str = Field(..., description="Unique worker identifier")
    capabilities: list[str] = Field(default_factory=list, description="List of task types this worker can handle")
    max_concurrent_tasks: int = Field(default=1, description="Maximum concurrent tasks")


class WorkerRegisterResponse(BaseModel):
    """Response after registering a worker."""

    success: bool
    worker_id: str
    message: str


class TaskSubmitRequest(BaseModel):
    """Request to submit a task."""

    task_id: str | None = Field(None, description="Optional task ID (auto-generated if not provided)")
    type: str = Field(..., description="Task type")
    payload: dict[str, Any] = Field(..., description="Task input data")
    priority: int = Field(default=5, description="Priority level (0-15)")
    dependencies: list[str] = Field(default_factory=list, description="Dependent task IDs")
    timeout: float = Field(default=300.0, description="Timeout in seconds")
    retry_count: int = Field(default=3, description="Retry attempts on failure")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class TaskSubmitResponse(BaseModel):
    """Response after submitting a task."""

    success: bool
    task_id: str
    message: str


class TaskBatchSubmitRequest(BaseModel):
    """Request to submit multiple tasks."""

    tasks: list[TaskSubmitRequest] = Field(..., description="List of tasks to submit")


class TaskBatchSubmitResponse(BaseModel):
    """Response after submitting multiple tasks."""

    success: bool
    task_ids: list[str]
    count: int


class TaskCancelRequest(BaseModel):
    """Request to cancel a task."""

    task_id: str = Field(..., description="Task ID to cancel")


class TaskCancelResponse(BaseModel):
    """Response after cancelling a task."""

    success: bool
    task_id: str
    message: str


class MasterAgentStatusResponse(BaseModel):
    """Master agent status response."""

    workers: dict[str, Any] = Field(default_factory=dict)
    pending_tasks: int = 0
    active_tasks: int = 0
    completed_tasks: int = 0
    running: bool = False
    load_balancer_strategy: str = ""
    max_concurrent_tasks: int = 0


class WorkerPoolStatsResponse(BaseModel):
    """Worker pool statistics response."""

    total_workers: int = 0
    idle_workers: int = 0
    busy_workers: int = 0
    offline_workers: int = 0
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0


class TaskResultResponse(BaseModel):
    """Task result response."""

    task_id: str = ""
    worker_id: str = ""
    success: bool = False
    result: Any = None
    error: str | None = None
    duration: float = 0.0
    retries_used: int = 0


class QueueStatsResponse(BaseModel):
    """Task queue statistics response."""

    pending_tasks: int = 0
    tasks_by_status: dict[str, int] = Field(default_factory=dict)
    tasks_by_type: dict[str, int] = Field(default_factory=dict)


@router.on_event("startup")
async def startup_event() -> None:
    """Initialize master agent on startup."""
    get_master_agent()
    get_task_queue()
    logger.info("orchestration_module_initialized")


@router.get("/status", response_model=MasterAgentStatusResponse)
async def get_status() -> MasterAgentStatusResponse:
    """Get master agent status."""
    master = get_master_agent()
    status = master.get_status()
    return MasterAgentStatusResponse(**status)


@router.get("/workers/stats", response_model=WorkerPoolStatsResponse)
async def get_worker_stats() -> WorkerPoolStatsResponse:
    """Get worker pool statistics."""
    master = get_master_agent()
    stats = master.get_worker_pool_stats()
    return WorkerPoolStatsResponse(**stats)


@router.get("/workers/list")
async def list_workers() -> list[dict[str, Any]]:
    """List all registered workers."""
    master = get_master_agent()
    status = master.get_status()
    return list(status["workers"].values())


@router.post("/workers/register", response_model=WorkerRegisterResponse)
async def register_worker(request: WorkerRegisterRequest) -> WorkerRegisterResponse:
    """Register a new worker."""
    master = get_master_agent()

    worker = Worker(
        worker_id=request.worker_id,
        capabilities=request.capabilities,
        max_concurrent_tasks=request.max_concurrent_tasks,
    )
    master.register_worker(worker)

    return WorkerRegisterResponse(
        success=True,
        worker_id=request.worker_id,
        message=f"Worker {request.worker_id} registered successfully",
    )


@router.post("/workers/unregister")
async def unregister_worker(worker_id: str) -> dict[str, Any]:
    """Unregister a worker."""
    master = get_master_agent()
    master.unregister_worker(worker_id)

    return {
        "success": True,
        "message": f"Worker {worker_id} unregistered successfully",
    }


@router.post("/tasks/submit", response_model=TaskSubmitResponse)
async def submit_task(request: TaskSubmitRequest) -> TaskSubmitResponse:
    """Submit a single task."""
    master = get_master_agent()

    task = Task(
        id=request.task_id or "",
        type=request.type,
        payload=request.payload,
        priority=request.priority,
        dependencies=request.dependencies,
        timeout=request.timeout,
        retry_count=request.retry_count,
        metadata=request.metadata,
    )

    task_id = await master.submit_task(task)

    return TaskSubmitResponse(
        success=True,
        task_id=task_id,
        message=f"Task {task_id} submitted successfully",
    )


@router.post("/tasks/submit/batch", response_model=TaskBatchSubmitResponse)
async def submit_tasks_batch(request: TaskBatchSubmitRequest) -> TaskBatchSubmitResponse:
    """Submit multiple tasks in batch."""
    master = get_master_agent()

    tasks = []
    for req in request.tasks:
        tasks.append(Task(
            id=req.task_id or "",
            type=req.type,
            payload=req.payload,
            priority=req.priority,
            dependencies=req.dependencies,
            timeout=req.timeout,
            retry_count=req.retry_count,
            metadata=req.metadata,
        ))

    task_ids = await master.submit_tasks(tasks)

    return TaskBatchSubmitResponse(
        success=True,
        task_ids=task_ids,
        count=len(task_ids),
    )


@router.post("/tasks/cancel", response_model=TaskCancelResponse)
async def cancel_task(request: TaskCancelRequest) -> TaskCancelResponse:
    """Cancel a task."""
    master = get_master_agent()
    success = master.cancel_task(request.task_id)

    return TaskCancelResponse(
        success=success,
        task_id=request.task_id,
        message="Task cancelled successfully" if success else "Task not found",
    )


@router.get("/tasks/result/{task_id}", response_model=TaskResultResponse)
async def get_task_result(task_id: str) -> TaskResultResponse:
    """Get the result of a completed task."""
    master = get_master_agent()
    result = master.get_task_result(task_id)

    if result is None:
        raise HTTPException(status_code=404, detail=f"Task result not found: {task_id}")

    return TaskResultResponse(
        task_id=result.task_id,
        worker_id=result.worker_id,
        success=result.success,
        result=result.result,
        error=result.error,
        duration=result.duration,
        retries_used=result.retries_used,
    )


@router.get("/tasks/results")
async def get_all_results() -> dict[str, Any]:
    """Get all task results."""
    master = get_master_agent()
    results = master.get_all_results()

    return {
        "count": len(results),
        "results": {
            task_id: result.to_dict()
            for task_id, result in results.items()
        },
    }


@router.delete("/tasks/results/clear")
async def clear_results() -> dict[str, Any]:
    """Clear all task results."""
    master = get_master_agent()
    master.clear_results()

    return {
        "success": True,
        "message": "All task results cleared",
    }


@router.get("/queue/stats", response_model=QueueStatsResponse)
async def get_queue_stats() -> QueueStatsResponse:
    """Get task queue statistics."""
    master = get_master_agent()
    queue = get_task_queue()

    pending = queue.size()
    tasks = queue.get_pending_tasks()

    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}

    for task in tasks:
        # Count by status
        status_key = task.status.value
        by_status[status_key] = by_status.get(status_key, 0) + 1

        # Count by type
        type_key = task.type
        by_type[type_key] = by_type.get(type_key, 0) + 1

    return QueueStatsResponse(
        pending_tasks=pending,
        tasks_by_status=by_status,
        tasks_by_type=by_type,
    )


@router.get("/queue/tasks")
async def get_queue_tasks(
    status: str | None = None,
    task_type: str | None = None,
) -> list[dict[str, Any]]:
    """Get tasks from the queue with optional filters."""
    queue = get_task_queue()
    tasks = queue.get_pending_tasks()

    if status:
        try:
            task_status = TaskStatus(status)
            tasks = [t for t in tasks if t.status == task_status]
        except ValueError:
            pass

    if task_type:
        tasks = [t for t in tasks if t.type == task_type]

    return [t.to_dict() for t in tasks]


@router.post("/execute")
async def execute_tasks(timeout: float = 60.0) -> dict[str, Any]:
    """Execute all pending tasks."""
    master = get_master_agent()

    # Transfer tasks from global queue to master
    queue = get_task_queue()
    tasks_to_transfer = []

    while not queue.is_empty():
        task = queue.dequeue()
        if task:
            tasks_to_transfer.append(task)

    # Submit to master
    if tasks_to_transfer:
        await master.submit_tasks(tasks_to_transfer)

    # Execute
    results = await master.run(timeout=timeout)

    return results


@router.get("/supported-types")
async def get_supported_task_types() -> dict[str, Any]:
    """Get supported task types."""
    return {
        "task_types": [t.value for t in TaskType],
        "priorities": {
            "low": TaskPriority.LOW.value,
            "normal": TaskPriority.NORMAL.value,
            "high": TaskPriority.HIGH.value,
            "critical": TaskPriority.CRITICAL.value,
        },
    }


# ============== Worker Registry API ==============

class WorkerRegistryConfigResponse(BaseModel):
    """Worker registry configuration response."""

    heartbeat_timeout: float
    health_check_interval: float
    auto_remove_unhealthy: bool
    auto_remove_delay: float
    max_workers: int
    enable_discovery: bool


class WorkerInfoResponse(BaseModel):
    """Worker information response."""

    worker_id: str
    capabilities: list[str]
    address: str
    metadata: dict[str, Any]
    registered_at: float
    last_heartbeat: float
    status: str
    health_status: str
    is_healthy: bool


class WorkerRegisterV2Request(BaseModel):
    """Request to register a worker (v2 with registry)."""

    worker_id: str = Field(..., description="Unique worker identifier")
    capabilities: list[str] = Field(default_factory=list, description="Task types worker can handle")
    address: str = Field(default="", description="Worker network address")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class WorkerRegisterV2Response(BaseModel):
    """Response after registering a worker (v2)."""

    success: bool
    worker_id: str
    address: str
    capabilities: list[str]
    message: str


class WorkerHeartbeatRequest(BaseModel):
    """Request to update worker heartbeat."""

    worker_id: str = Field(..., description="Worker ID to update")


class WorkerHeartbeatResponse(BaseModel):
    """Response after updating heartbeat."""

    success: bool
    worker_id: str
    last_heartbeat: float
    is_healthy: bool


class WorkerDiscoverRequest(BaseModel):
    """Request to discover workers."""

    capability: str = Field(..., description="Required capability")
    healthy_only: bool = Field(default=True, description="Only return healthy workers")


class WorkerDiscoverResponse(BaseModel):
    """Response after discovering workers."""

    count: int
    workers: list[WorkerInfoResponse]


class WorkerRegistryStatsResponse(BaseModel):
    """Worker registry statistics response."""

    total_workers: int
    healthy_workers: int
    unhealthy_workers: int
    idle_workers: int
    max_workers: int | str
    heartbeat_timeout: float
    health_check_interval: float


@router.on_event("startup")
async def startup_event() -> None:
    """Initialize master agent on startup."""
    get_master_agent()
    get_task_queue()
    get_worker_registry()
    get_service_discovery()
    logger.info("orchestration_module_initialized")


@router.post("/registry/start")
async def start_registry() -> dict[str, Any]:
    """Start the worker registry health check loop."""
    registry = get_worker_registry()
    await registry.start()

    return {
        "success": True,
        "message": "Worker registry started",
    }


@router.post("/registry/stop")
async def stop_registry() -> dict[str, Any]:
    """Stop the worker registry health check loop."""
    registry = get_worker_registry()
    await registry.stop()

    return {
        "success": True,
        "message": "Worker registry stopped",
    }


@router.post("/registry/workers/register", response_model=WorkerRegisterV2Response)
async def register_worker_v2(request: WorkerRegisterV2Request) -> WorkerRegisterV2Response:
    """Register a worker with the registry."""
    registry = get_worker_registry()

    worker_info = await registry.register_worker(
        worker_id=request.worker_id,
        capabilities=request.capabilities,
        address=request.address,
        metadata=request.metadata,
    )

    # Also register with MasterAgent for task execution
    master = get_master_agent()
    worker = Worker(
        worker_id=request.worker_id,
        capabilities=request.capabilities,
    )
    master.register_worker(worker)

    return WorkerRegisterV2Response(
        success=True,
        worker_id=request.worker_id,
        address=request.address,
        capabilities=request.capabilities,
        message=f"Worker {request.worker_id} registered successfully",
    )


@router.post("/registry/workers/unregister")
async def unregister_worker_v2(worker_id: str) -> dict[str, Any]:
    """Unregister a worker from the registry."""
    registry = get_worker_registry()
    master = get_master_agent()

    registry_result = await registry.unregister_worker(worker_id)
    master.unregister_worker(worker_id)

    return {
        "success": registry_result,
        "message": f"Worker {worker_id} unregistered successfully",
    }


@router.post("/registry/workers/heartbeat", response_model=WorkerHeartbeatResponse)
async def update_heartbeat(request: WorkerHeartbeatRequest) -> WorkerHeartbeatResponse:
    """Update worker heartbeat."""
    registry = get_worker_registry()

    result = await registry.update_heartbeat(request.worker_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"Worker not found: {request.worker_id}")

    worker = registry.get_worker(request.worker_id)

    return WorkerHeartbeatResponse(
        success=True,
        worker_id=request.worker_id,
        last_heartbeat=worker.last_heartbeat,
        is_healthy=worker.is_healthy(),
    )


@router.get("/registry/workers/{worker_id}", response_model=WorkerInfoResponse)
async def get_worker(worker_id: str) -> WorkerInfoResponse:
    """Get worker information."""
    registry = get_worker_registry()
    worker = registry.get_worker(worker_id)

    if worker is None:
        raise HTTPException(status_code=404, detail=f"Worker not found: {worker_id}")

    return WorkerInfoResponse(**worker.to_dict())


@router.get("/registry/workers", response_model=list[WorkerInfoResponse])
async def list_registry_workers(healthy_only: bool = False) -> list[WorkerInfoResponse]:
    """List all registered workers."""
    registry = get_worker_registry()

    if healthy_only:
        workers = registry.get_healthy_workers()
    else:
        workers = registry.get_all_workers()

    return [WorkerInfoResponse(**w.to_dict()) for w in workers]


@router.post("/registry/discover", response_model=WorkerDiscoverResponse)
async def discover_workers(request: WorkerDiscoverRequest) -> WorkerDiscoverResponse:
    """Discover workers by capability."""
    registry = get_worker_registry()

    workers = registry.discover_workers(
        request.capability,
        healthy_only=request.healthy_only,
    )

    return WorkerDiscoverResponse(
        count=len(workers),
        workers=[WorkerInfoResponse(**w.to_dict()) for w in workers],
    )


@router.get("/registry/stats", response_model=WorkerRegistryStatsResponse)
async def get_registry_stats() -> WorkerRegistryStatsResponse:
    """Get worker registry statistics."""
    registry = get_worker_registry()
    stats = registry.get_statistics()

    return WorkerRegistryStatsResponse(**stats)


@router.get("/registry/config", response_model=WorkerRegistryConfigResponse)
async def get_registry_config() -> WorkerRegistryConfigResponse:
    """Get worker registry configuration."""
    registry = get_worker_registry()
    config = registry._config

    return WorkerRegistryConfigResponse(
        heartbeat_timeout=config.heartbeat_timeout,
        health_check_interval=config.health_check_interval,
        auto_remove_unhealthy=config.auto_remove_unhealthy,
        auto_remove_delay=config.auto_remove_delay,
        max_workers=config.max_workers if config.max_workers > 0 else 0,
        enable_discovery=config.enable_discovery,
    )


@router.get("/service-discovery/find")
async def find_worker(
    capability: str,
    strategy: str = "healthy",
) -> dict[str, Any]:
    """Find a worker by capability using service discovery."""
    discovery = get_service_discovery()

    worker = discovery.find_by_capability(capability, strategy=strategy)

    if worker is None:
        return {
            "success": False,
            "message": f"No worker found with capability: {capability}",
        }

    return {
        "success": True,
        "worker": worker.to_dict(),
    }


@router.get("/service-discovery/find-all")
async def find_all_workers(
    capabilities: list[str],
    require_all: bool = False,
) -> dict[str, Any]:
    """Find all workers with specified capabilities."""
    discovery = get_service_discovery()

    workers = discovery.find_all_by_capabilities(capabilities, require_all=require_all)

    return {
        "success": True,
        "count": len(workers),
        "workers": [w.to_dict() for w in workers],
    }
