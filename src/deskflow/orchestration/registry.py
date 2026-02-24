"""Worker registration and discovery module.

This module provides service discovery for Worker Agents with health checking,
automatic registration, and graceful deregistration.

Features:
- Worker registration with metadata
- Heartbeat-based health checking
- Automatic unhealthy worker removal
- Service discovery by capability
- Graceful worker deregistration
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from deskflow.observability.logging import get_logger

from .collaboration import Worker, WorkerStatus

logger = get_logger(__name__)


class WorkerHealthStatus(str, Enum):
    """Worker health status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    DISCONNECTED = "disconnected"


@dataclass
class WorkerInfo:
    """Worker registration information.

    Attributes:
        worker_id: Unique worker identifier
        capabilities: List of task types this worker can handle
        address: Worker network address (IP:port or URL)
        metadata: Additional worker metadata (version, tags, etc.)
        registered_at: Registration timestamp
        last_heartbeat: Last heartbeat timestamp
        status: Current worker status
        health_status: Health check status
    """

    worker_id: str
    capabilities: list[str]
    address: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    status: WorkerStatus = WorkerStatus.IDLE
    health_status: WorkerHealthStatus = WorkerHealthStatus.UNKNOWN

    def update_heartbeat(self) -> None:
        """Update heartbeat timestamp and health status."""
        self.last_heartbeat = time.time()
        self.health_status = WorkerHealthStatus.HEALTHY
        if self.status == WorkerStatus.OFFLINE:
            self.status = WorkerStatus.IDLE

    def is_healthy(self, timeout: float = 30.0) -> bool:
        """Check if worker is healthy based on heartbeat."""
        return (time.time() - self.last_heartbeat) < timeout

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "worker_id": self.worker_id,
            "capabilities": self.capabilities,
            "address": self.address,
            "metadata": self.metadata,
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
            "status": self.status.value,
            "health_status": self.health_status.value,
            "is_healthy": self.is_healthy(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkerInfo:
        """Create WorkerInfo from dictionary."""
        return cls(
            worker_id=data.get("worker_id", ""),
            capabilities=data.get("capabilities", []),
            address=data.get("address", ""),
            metadata=data.get("metadata", {}),
            registered_at=data.get("registered_at", time.time()),
            last_heartbeat=data.get("last_heartbeat", time.time()),
            status=WorkerStatus(data.get("status", WorkerStatus.IDLE.value)),
            health_status=WorkerHealthStatus(
                data.get("health_status", WorkerHealthStatus.UNKNOWN.value)
            ),
        )


@dataclass
class WorkerRegistryConfig:
    """Configuration for WorkerRegistry.

    Attributes:
        heartbeat_timeout: Seconds before worker is considered unhealthy
        health_check_interval: Interval between health checks
        auto_remove_unhealthy: Automatically remove unhealthy workers
        auto_remove_delay: Delay before removing unhealthy workers
        max_workers: Maximum number of workers (0 for unlimited)
        enable_discovery: Enable service discovery
    """

    heartbeat_timeout: float = 30.0
    health_check_interval: float = 10.0
    auto_remove_unhealthy: bool = True
    auto_remove_delay: float = 60.0
    max_workers: int = 0
    enable_discovery: bool = True


class WorkerRegistry:
    """Registry for Worker service discovery and health management.

    The WorkerRegistry manages worker registration, health checking, and
    service discovery. It provides:

    - Worker registration with capabilities and metadata
    - Heartbeat-based health monitoring
    - Automatic unhealthy worker detection and removal
    - Service discovery by capability
    - Worker lifecycle events (register, unregister, unhealthy)

    Example:
        ```python
        registry = WorkerRegistry()
        await registry.register_worker(
            worker_id="worker-1",
            capabilities=["python", "code"],
            address="http://localhost:8001"
        )

        # Get workers by capability
        workers = registry.discover_workers("python")

        # Check health
        healthy_workers = registry.get_healthy_workers()
        ```
    """

    def __init__(self, config: WorkerRegistryConfig | None = None) -> None:
        """Initialize the WorkerRegistry.

        Args:
            config: Registry configuration
        """
        self._config = config or WorkerRegistryConfig()
        self._workers: dict[str, WorkerInfo] = {}
        self._running = False
        self._health_check_task: asyncio.Task | None = None

        # Event callbacks
        self._on_register: list[Callable[[WorkerInfo], None]] = []
        self._on_unregister: list[Callable[[str], None]] = []
        self._on_unhealthy: list[Callable[[WorkerInfo], None]] = []

    async def start(self) -> None:
        """Start the registry health check loop."""
        if self._running:
            logger.warning("registry_already_running")
            return

        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("worker_registry_started")

    async def stop(self) -> None:
        """Stop the registry health check loop."""
        self._running = False

        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None

        logger.info("worker_registry_stopped")

    async def register_worker(
        self,
        worker_id: str,
        capabilities: list[str],
        address: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> WorkerInfo:
        """Register a worker.

        Args:
            worker_id: Unique worker identifier
            capabilities: List of task types the worker can handle
            address: Worker network address
            metadata: Additional worker metadata

        Returns:
            Registered WorkerInfo

        Raises:
            ValueError: If worker_id is empty
            RuntimeError: If max_workers limit exceeded
        """
        if not worker_id:
            raise ValueError("worker_id cannot be empty")

        # Check max workers limit
        if (
            self._config.max_workers > 0
            and len(self._workers) >= self._config.max_workers
        ):
            raise RuntimeError(
                f"Maximum worker limit ({self._config.max_workers}) reached"
            )

        # Create or update worker info
        is_update = worker_id in self._workers
        worker_info = WorkerInfo(
            worker_id=worker_id,
            capabilities=capabilities,
            address=address,
            metadata=metadata or {},
        )

        self._workers[worker_id] = worker_info

        if is_update:
            logger.info("worker_reregistered", worker_id=worker_id)
        else:
            logger.info("worker_registered", worker_id=worker_id, capabilities=capabilities)
            self._notify_register(worker_info)

        return worker_info

    async def unregister_worker(self, worker_id: str) -> bool:
        """Unregister a worker.

        Args:
            worker_id: Worker ID to unregister

        Returns:
            True if worker was unregistered, False if not found
        """
        if worker_id not in self._workers:
            logger.warning("worker_not_found_for_unregister", worker_id=worker_id)
            return False

        del self._workers[worker_id]
        logger.info("worker_unregistered", worker_id=worker_id)
        self._notify_unregister(worker_id)
        return True

    async def update_heartbeat(self, worker_id: str) -> bool:
        """Update worker heartbeat.

        Args:
            worker_id: Worker ID to update

        Returns:
            True if worker was updated, False if not found
        """
        if worker_id not in self._workers:
            logger.warning("worker_not_found_for_heartbeat", worker_id=worker_id)
            return False

        self._workers[worker_id].update_heartbeat()
        return True

    def get_worker(self, worker_id: str) -> WorkerInfo | None:
        """Get worker by ID.

        Args:
            worker_id: Worker ID to get

        Returns:
            WorkerInfo if found, None otherwise
        """
        return self._workers.get(worker_id)

    def get_healthy_workers(self) -> list[WorkerInfo]:
        """Get all healthy workers.

        Returns:
            List of healthy WorkerInfo objects
        """
        return [
            w for w in self._workers.values()
            if w.is_healthy(self._config.heartbeat_timeout)
        ]

    def discover_workers(
        self,
        capability: str,
        healthy_only: bool = True,
    ) -> list[WorkerInfo]:
        """Discover workers with specific capability.

        Args:
            capability: Required capability
            healthy_only: Only return healthy workers

        Returns:
            List of matching WorkerInfo objects
        """
        workers = self._workers.values()

        if healthy_only:
            workers = [
                w for w in workers
                if w.is_healthy(self._config.heartbeat_timeout)
            ]

        return [
            w for w in workers
            if capability in w.capabilities or "*" in w.capabilities
        ]

    def get_all_workers(self) -> list[WorkerInfo]:
        """Get all registered workers.

        Returns:
            List of all WorkerInfo objects
        """
        return list(self._workers.values())

    def get_statistics(self) -> dict[str, Any]:
        """Get registry statistics.

        Returns:
            Dictionary with statistics
        """
        total = len(self._workers)
        healthy = sum(1 for w in self._workers.values() if w.is_healthy())
        unhealthy = total - healthy
        idle = sum(1 for w in self._workers.values() if w.status == WorkerStatus.IDLE)

        return {
            "total_workers": total,
            "healthy_workers": healthy,
            "unhealthy_workers": unhealthy,
            "idle_workers": idle,
            "max_workers": self._config.max_workers if self._config.max_workers > 0 else "unlimited",
            "heartbeat_timeout": self._config.heartbeat_timeout,
            "health_check_interval": self._config.health_check_interval,
        }

    def subscribe(
        self,
        event: str,
        callback: Callable[..., None],
    ) -> None:
        """Subscribe to registry events.

        Args:
            event: Event type ('register', 'unregister', 'unhealthy')
            callback: Callback function

        Raises:
            ValueError: If event type is unknown
        """
        if event == "register":
            self._on_register.append(callback)
        elif event == "unregister":
            self._on_unregister.append(callback)
        elif event == "unhealthy":
            self._on_unhealthy.append(callback)
        else:
            raise ValueError(f"Unknown event type: {event}")

    def unsubscribe(
        self,
        event: str,
        callback: Callable[..., None],
    ) -> None:
        """Unsubscribe from registry events.

        Args:
            event: Event type ('register', 'unregister', 'unhealthy')
            callback: Callback function to remove
        """
        if event == "register":
            if callback in self._on_register:
                self._on_register.remove(callback)
        elif event == "unregister":
            if callback in self._on_unregister:
                self._on_unregister.remove(callback)
        elif event == "unhealthy":
            if callback in self._on_unhealthy:
                self._on_unhealthy.remove(callback)

    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self._running:
            try:
                await self._run_health_check()
                await asyncio.sleep(self._config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("health_check_error", error=str(e))
                await asyncio.sleep(self._config.health_check_interval)

    async def _run_health_check(self) -> None:
        """Run health check on all workers."""
        now = time.time()

        for worker in list(self._workers.values()):
            if not worker.is_healthy(self._config.heartbeat_timeout):
                # Worker is unhealthy
                if worker.health_status != WorkerHealthStatus.UNHEALTHY:
                    worker.health_status = WorkerHealthStatus.UNHEALTHY
                    logger.warning("worker_unhealthy", worker_id=worker.worker_id)
                    self._notify_unhealthy(worker)

                # Auto-remove if configured
                if self._config.auto_remove_unhealthy:
                    time_unhealthy = now - worker.last_heartbeat
                    if time_unhealthy > self._config.auto_remove_delay:
                        await self.unregister_worker(worker.worker_id)
                        logger.info(
                            "worker_auto_removed",
                            worker_id=worker.worker_id,
                            reason="unhealthy",
                        )

    def _notify_register(self, worker_info: WorkerInfo) -> None:
        """Notify register event subscribers."""
        for callback in self._on_register:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(worker_info))
                else:
                    callback(worker_info)
            except Exception as e:
                logger.error("notify_register_error", error=str(e))

    def _notify_unregister(self, worker_id: str) -> None:
        """Notify unregister event subscribers."""
        for callback in self._on_unregister:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(worker_id))
                else:
                    callback(worker_id)
            except Exception as e:
                logger.error("notify_unregister_error", error=str(e))

    def _notify_unhealthy(self, worker_info: WorkerInfo) -> None:
        """Notify unhealthy event subscribers."""
        for callback in self._on_unhealthy:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(worker_info))
                else:
                    callback(worker_info)
            except Exception as e:
                logger.error("notify_unhealthy_error", error=str(e))


class ServiceDiscovery:
    """Service discovery facade for Worker Registry.

    Provides a simplified interface for discovering workers by
    capability, load, or custom criteria.
    """

    def __init__(self, registry: WorkerRegistry) -> None:
        """Initialize with registry reference.

        Args:
            registry: WorkerRegistry instance
        """
        self._registry = registry

    def find_by_capability(
        self,
        capability: str,
        strategy: str = "healthy",
    ) -> WorkerInfo | None:
        """Find a worker with specific capability.

        Args:
            capability: Required capability
            strategy: Selection strategy ('healthy', 'least_loaded', 'random')

        Returns:
            WorkerInfo if found, None otherwise
        """
        workers = self._registry.discover_workers(capability, healthy_only=True)

        if not workers:
            return None

        if strategy == "least_loaded":
            # Select worker with lowest load (simplified: use IDLE status)
            idle_workers = [w for w in workers if w.status == WorkerStatus.IDLE]
            return idle_workers[0] if idle_workers else workers[0]

        # Default: return first healthy worker
        return workers[0]

    def find_all_by_capabilities(
        self,
        capabilities: list[str],
        require_all: bool = False,
    ) -> list[WorkerInfo]:
        """Find workers with specified capabilities.

        Args:
            capabilities: List of required capabilities
            require_all: If True, worker must have ALL capabilities

        Returns:
            List of matching WorkerInfo objects
        """
        workers = self._registry.get_healthy_workers()

        if require_all:
            return [
                w for w in workers
                if all(cap in w.capabilities or "*" in w.capabilities
                       for cap in capabilities)
            ]
        else:
            return [
                w for w in workers
                if any(cap in w.capabilities or "*" in w.capabilities
                       for cap in capabilities)
            ]

    def get_available_count(self, capability: str) -> int:
        """Get count of available workers with capability.

        Args:
            capability: Required capability

        Returns:
            Number of available workers
        """
        return len(self._registry.discover_workers(capability, healthy_only=True))
