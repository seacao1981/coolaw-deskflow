"""Unit tests for orchestration registry module."""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from deskflow.orchestration import (
    WorkerRegistry,
    WorkerRegistryConfig,
    WorkerInfo,
    WorkerHealthStatus,
    ServiceDiscovery,
    WorkerStatus,
)


# ============== WorkerInfo Tests ==============

class TestWorkerInfo:
    """Tests for WorkerInfo dataclass."""

    def test_worker_info_creation(self):
        """Test basic worker info creation."""
        info = WorkerInfo(
            worker_id="worker-1",
            capabilities=["python", "code"],
            address="http://localhost:8001",
        )

        assert info.worker_id == "worker-1"
        assert info.capabilities == ["python", "code"]
        assert info.address == "http://localhost:8001"
        assert info.health_status == WorkerHealthStatus.UNKNOWN
        assert info.status == WorkerStatus.IDLE

    def test_worker_info_update_heartbeat(self):
        """Test heartbeat update."""
        info = WorkerInfo(worker_id="1", capabilities=["test"])
        old_time = info.last_heartbeat

        time.sleep(0.01)
        info.update_heartbeat()

        assert info.last_heartbeat > old_time
        assert info.health_status == WorkerHealthStatus.HEALTHY

    def test_worker_info_is_healthy(self):
        """Test health check."""
        info = WorkerInfo(worker_id="1", capabilities=["test"])

        assert info.is_healthy(timeout=30.0) is True

    def test_worker_info_is_unhealthy(self):
        """Test unhealthy check."""
        info = WorkerInfo(worker_id="1", capabilities=["test"])
        info.last_heartbeat = time.time() - 60  # 60 seconds ago

        assert info.is_healthy(timeout=30.0) is False

    def test_worker_info_to_dict(self):
        """Test conversion to dictionary."""
        info = WorkerInfo(
            worker_id="worker-1",
            capabilities=["python"],
            address="http://localhost:8001",
            metadata={"version": "1.0"},
        )

        d = info.to_dict()

        assert d["worker_id"] == "worker-1"
        assert d["capabilities"] == ["python"]
        assert d["address"] == "http://localhost:8001"
        assert d["metadata"]["version"] == "1.0"

    def test_worker_info_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "worker_id": "worker-1",
            "capabilities": ["python", "code"],
            "address": "http://localhost:8001",
            "metadata": {"version": "1.0"},
            "status": "busy",
            "health_status": "healthy",
        }

        info = WorkerInfo.from_dict(data)

        assert info.worker_id == "worker-1"
        assert info.capabilities == ["python", "code"]
        assert info.status == WorkerStatus.BUSY
        assert info.health_status == WorkerHealthStatus.HEALTHY


# ============== WorkerRegistryConfig Tests ==============

class TestWorkerRegistryConfig:
    """Tests for WorkerRegistryConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = WorkerRegistryConfig()

        assert config.heartbeat_timeout == 30.0
        assert config.health_check_interval == 10.0
        assert config.auto_remove_unhealthy is True
        assert config.auto_remove_delay == 60.0
        assert config.max_workers == 0
        assert config.enable_discovery is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = WorkerRegistryConfig(
            heartbeat_timeout=60.0,
            health_check_interval=5.0,
            auto_remove_unhealthy=False,
            max_workers=10,
        )

        assert config.heartbeat_timeout == 60.0
        assert config.health_check_interval == 5.0
        assert config.auto_remove_unhealthy is False
        assert config.max_workers == 10


# ============== WorkerRegistry Tests ==============

class TestWorkerRegistry:
    """Tests for WorkerRegistry class."""

    def test_registry_creation(self):
        """Test registry creation."""
        registry = WorkerRegistry()

        assert registry._running is False
        assert registry._workers == {}

    def test_registry_creation_with_config(self):
        """Test registry with custom config."""
        config = WorkerRegistryConfig(max_workers=5)
        registry = WorkerRegistry(config)

        assert registry._config.max_workers == 5

    @pytest.mark.asyncio
    async def test_registry_start_stop(self):
        """Test registry start and stop."""
        registry = WorkerRegistry()

        await registry.start()
        assert registry._running is True

        await registry.stop()
        assert registry._running is False

    @pytest.mark.asyncio
    async def test_register_worker(self):
        """Test worker registration."""
        registry = WorkerRegistry()

        worker = await registry.register_worker(
            worker_id="worker-1",
            capabilities=["python", "code"],
            address="http://localhost:8001",
            metadata={"version": "1.0"},
        )

        assert worker.worker_id == "worker-1"
        assert worker.capabilities == ["python", "code"]
        assert registry.get_worker("worker-1") is not None

    @pytest.mark.asyncio
    async def test_register_worker_empty_id(self):
        """Test worker registration with empty ID."""
        registry = WorkerRegistry()

        with pytest.raises(ValueError, match="worker_id cannot be empty"):
            await registry.register_worker(
                worker_id="",
                capabilities=["python"],
            )

    @pytest.mark.asyncio
    async def test_register_worker_max_limit(self):
        """Test worker registration with max limit."""
        config = WorkerRegistryConfig(max_workers=2)
        registry = WorkerRegistry(config)

        await registry.register_worker("w1", ["python"])
        await registry.register_worker("w2", ["python"])

        with pytest.raises(RuntimeError, match="Maximum worker limit"):
            await registry.register_worker("w3", ["python"])

    @pytest.mark.asyncio
    async def test_unregister_worker(self):
        """Test worker unregistration."""
        registry = WorkerRegistry()
        await registry.register_worker("worker-1", ["python"])

        result = await registry.unregister_worker("worker-1")

        assert result is True
        assert registry.get_worker("worker-1") is None

    @pytest.mark.asyncio
    async def test_unregister_worker_not_found(self):
        """Test unregistering non-existent worker."""
        registry = WorkerRegistry()

        result = await registry.unregister_worker("unknown-worker")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_heartbeat(self):
        """Test heartbeat update."""
        registry = WorkerRegistry()
        await registry.register_worker("worker-1", ["python"])

        result = await registry.update_heartbeat("worker-1")

        assert result is True

    @pytest.mark.asyncio
    async def test_update_heartbeat_not_found(self):
        """Test heartbeat update for non-existent worker."""
        registry = WorkerRegistry()

        result = await registry.update_heartbeat("unknown-worker")

        assert result is False

    def test_get_healthy_workers(self):
        """Test getting healthy workers."""
        registry = WorkerRegistry()
        registry._workers = {
            "w1": WorkerInfo("w1", ["python"], last_heartbeat=time.time()),
            "w2": WorkerInfo("w2", ["python"], last_heartbeat=time.time() - 100),
        }

        healthy = registry.get_healthy_workers()

        assert len(healthy) == 1
        assert healthy[0].worker_id == "w1"

    def test_discover_workers(self):
        """Test discovering workers by capability."""
        registry = WorkerRegistry()
        registry._workers = {
            "w1": WorkerInfo("w1", ["python", "code"]),
            "w2": WorkerInfo("w2", ["java"]),
            "w3": WorkerInfo("w3", ["*"]),  # Wildcard
        }

        workers = registry.discover_workers("python", healthy_only=False)

        assert len(workers) == 2  # w1 and w3 (wildcard)
        worker_ids = [w.worker_id for w in workers]
        assert "w1" in worker_ids
        assert "w3" in worker_ids

    def test_discover_workers_healthy_only(self):
        """Test discovering only healthy workers."""
        registry = WorkerRegistry()
        registry._workers = {
            "w1": WorkerInfo("w1", ["python"], last_heartbeat=time.time()),
            "w2": WorkerInfo("w2", ["python"], last_heartbeat=time.time() - 100),
        }

        workers = registry.discover_workers("python", healthy_only=True)

        assert len(workers) == 1
        assert workers[0].worker_id == "w1"

    def test_get_all_workers(self):
        """Test getting all workers."""
        registry = WorkerRegistry()
        registry._workers = {
            "w1": WorkerInfo("w1", ["python"]),
            "w2": WorkerInfo("w2", ["java"]),
        }

        workers = registry.get_all_workers()

        assert len(workers) == 2

    def test_get_statistics(self):
        """Test registry statistics."""
        registry = WorkerRegistry()
        registry._workers = {
            "w1": WorkerInfo("w1", ["python"], last_heartbeat=time.time()),
            "w2": WorkerInfo("w2", ["java"], last_heartbeat=time.time() - 100),
        }
        registry._workers["w2"].status = WorkerStatus.BUSY

        stats = registry.get_statistics()

        assert stats["total_workers"] == 2
        assert stats["healthy_workers"] == 1
        assert stats["unhealthy_workers"] == 1
        assert stats["idle_workers"] == 1

    @pytest.mark.asyncio
    async def test_subscribe_register_event(self):
        """Test subscribe to register event."""
        registry = WorkerRegistry()
        received = []

        def on_register(worker_info):
            received.append(worker_info)

        registry.subscribe("register", on_register)

        await registry.register_worker("worker-1", ["python"])

        assert len(received) == 1
        assert received[0].worker_id == "worker-1"

    @pytest.mark.asyncio
    async def test_subscribe_unregister_event(self):
        """Test subscribe to unregister event."""
        registry = WorkerRegistry()
        received = []

        def on_unregister(worker_id):
            received.append(worker_id)

        registry.subscribe("unregister", on_unregister)

        await registry.register_worker("worker-1", ["python"])
        await registry.unregister_worker("worker-1")

        assert len(received) == 1
        assert received[0] == "worker-1"

    @pytest.mark.asyncio
    async def test_subscribe_unhealthy_event(self):
        """Test subscribe to unhealthy event."""
        config = WorkerRegistryConfig(
            heartbeat_timeout=0.05,
            health_check_interval=0.01,
            auto_remove_unhealthy=False,
        )
        registry = WorkerRegistry(config)

        received = []

        def on_unhealthy(worker_info):
            received.append(worker_info.worker_id)

        registry.subscribe("unhealthy", on_unhealthy)

        # Register worker
        await registry.register_worker("worker-1", ["python"])

        # Let it become unhealthy
        await asyncio.sleep(0.1)
        await registry.start()
        await asyncio.sleep(0.1)
        await registry.stop()

        assert "worker-1" in received

    def test_subscribe_unknown_event(self):
        """Test subscribe to unknown event."""
        registry = WorkerRegistry()

        with pytest.raises(ValueError, match="Unknown event type"):
            registry.subscribe("unknown", lambda x: None)

    @pytest.mark.asyncio
    async def test_reregister_worker(self):
        """Test re-registering existing worker."""
        registry = WorkerRegistry()

        await registry.register_worker("worker-1", ["python"])
        worker2 = await registry.register_worker("worker-1", ["python", "code"])

        assert worker2.capabilities == ["python", "code"]


# ============== ServiceDiscovery Tests ==============

class TestServiceDiscovery:
    """Tests for ServiceDiscovery class."""

    def test_service_discovery_creation(self):
        """Test service discovery creation."""
        registry = WorkerRegistry()
        discovery = ServiceDiscovery(registry)

        assert discovery._registry is registry

    def test_find_by_capability_no_workers(self):
        """Test finding worker when no workers available."""
        registry = WorkerRegistry()
        discovery = ServiceDiscovery(registry)

        worker = discovery.find_by_capability("python")

        assert worker is None

    def test_find_by_capability_single_worker(self):
        """Test finding worker by capability."""
        registry = WorkerRegistry()
        registry._workers = {
            "w1": WorkerInfo("w1", ["python", "code"], last_heartbeat=time.time()),
            "w2": WorkerInfo("w2", ["java"], last_heartbeat=time.time()),
        }
        discovery = ServiceDiscovery(registry)

        worker = discovery.find_by_capability("python")

        assert worker is not None
        assert worker.worker_id == "w1"

    def test_find_by_capability_wildcard(self):
        """Test finding wildcard worker."""
        registry = WorkerRegistry()
        registry._workers = {
            "w1": WorkerInfo("w1", ["*"], last_heartbeat=time.time()),
        }
        discovery = ServiceDiscovery(registry)

        worker = discovery.find_by_capability("any_capability")

        assert worker is not None
        assert worker.worker_id == "w1"

    def test_find_by_capability_least_loaded(self):
        """Test least-loaded strategy."""
        registry = WorkerRegistry()
        w1 = WorkerInfo("w1", ["python"], last_heartbeat=time.time())
        w2 = WorkerInfo("w2", ["python"], last_heartbeat=time.time())
        w2.status = WorkerStatus.BUSY

        registry._workers = {"w1": w1, "w2": w2}
        discovery = ServiceDiscovery(registry)

        worker = discovery.find_by_capability("python", strategy="least_loaded")

        assert worker is not None
        assert worker.worker_id == "w1"  # IDLE worker preferred

    def test_find_all_by_capabilities_require_all(self):
        """Test finding workers with all capabilities."""
        registry = WorkerRegistry()
        registry._workers = {
            "w1": WorkerInfo("w1", ["python", "code"], last_heartbeat=time.time()),
            "w2": WorkerInfo("w2", ["python"], last_heartbeat=time.time()),
            "w3": WorkerInfo("w3", ["code"], last_heartbeat=time.time()),
        }
        discovery = ServiceDiscovery(registry)

        workers = discovery.find_all_by_capabilities(
            ["python", "code"],
            require_all=True,
        )

        assert len(workers) == 1
        assert workers[0].worker_id == "w1"

    def test_find_all_by_capabilities_require_any(self):
        """Test finding workers with any capability."""
        registry = WorkerRegistry()
        registry._workers = {
            "w1": WorkerInfo("w1", ["python", "code"], last_heartbeat=time.time()),
            "w2": WorkerInfo("w2", ["java"], last_heartbeat=time.time()),
            "w3": WorkerInfo("w3", ["go"], last_heartbeat=time.time()),
        }
        discovery = ServiceDiscovery(registry)

        workers = discovery.find_all_by_capabilities(
            ["python", "java"],
            require_all=False,
        )

        assert len(workers) == 2
        worker_ids = [w.worker_id for w in workers]
        assert "w1" in worker_ids
        assert "w2" in worker_ids

    def test_get_available_count(self):
        """Test getting available worker count."""
        registry = WorkerRegistry()
        registry._workers = {
            "w1": WorkerInfo("w1", ["python"], last_heartbeat=time.time()),
            "w2": WorkerInfo("w2", ["python"], last_heartbeat=time.time()),
            "w3": WorkerInfo("w3", ["python"], last_heartbeat=time.time() - 100),
        }
        discovery = ServiceDiscovery(registry)

        count = discovery.get_available_count("python")

        assert count == 2  # Only healthy workers


# ============== Health Check Loop Tests ==============

class TestHealthCheckLoop:
    """Tests for health check loop."""

    @pytest.mark.asyncio
    async def test_health_check_auto_detect_unhealthy(self):
        """Test auto detection of unhealthy workers."""
        config = WorkerRegistryConfig(
            heartbeat_timeout=0.05,
            health_check_interval=0.02,
            auto_remove_unhealthy=False,
        )
        registry = WorkerRegistry(config)

        await registry.register_worker("worker-1", ["python"])

        # Let heartbeat expire
        await asyncio.sleep(0.1)

        # Start health check
        await registry.start()
        await asyncio.sleep(0.1)
        await registry.stop()

        worker = registry.get_worker("worker-1")
        assert worker is not None
        assert worker.health_status == WorkerHealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_health_check_auto_remove(self):
        """Test auto removal of unhealthy workers."""
        config = WorkerRegistryConfig(
            heartbeat_timeout=0.05,
            health_check_interval=0.02,
            auto_remove_unhealthy=True,
            auto_remove_delay=0.1,
        )
        registry = WorkerRegistry(config)

        await registry.register_worker("worker-1", ["python"])

        # Let heartbeat expire and delay pass
        await asyncio.sleep(0.2)

        # Start health check
        await registry.start()
        await asyncio.sleep(0.2)
        await registry.stop()

        # Worker should be removed
        worker = registry.get_worker("worker-1")
        assert worker is None


# ============== Integration Tests ==============

class TestWorkerRegistryIntegration:
    """Integration tests for WorkerRegistry."""

    @pytest.mark.asyncio
    async def test_full_worker_lifecycle(self):
        """Test complete worker lifecycle."""
        registry = WorkerRegistry()
        await registry.start()

        # Register
        worker = await registry.register_worker(
            "worker-1",
            ["python", "code"],
            "http://localhost:8001",
        )
        assert worker.worker_id == "worker-1"

        # Update heartbeat
        await registry.update_heartbeat("worker-1")

        # Discover
        workers = registry.discover_workers("python")
        assert len(workers) == 1

        # Get statistics
        stats = registry.get_statistics()
        assert stats["total_workers"] == 1

        # Unregister
        result = await registry.unregister_worker("worker-1")
        assert result is True

        await registry.stop()

    @pytest.mark.asyncio
    async def test_multiple_workers_with_capabilities(self):
        """Test multiple workers with different capabilities."""
        registry = WorkerRegistry()

        # Register workers with different capabilities
        await registry.register_worker("py-worker", ["python", "code"])
        await registry.register_worker("java-worker", ["java", "code"])
        await registry.register_worker("full-worker", ["python", "java", "go"])

        # Find python workers
        py_workers = registry.discover_workers("python", healthy_only=False)
        assert len(py_workers) == 2

        # Find java workers
        java_workers = registry.discover_workers("java", healthy_only=False)
        assert len(java_workers) == 2

        # Find go workers
        go_workers = registry.discover_workers("go", healthy_only=False)
        assert len(go_workers) == 1

    @pytest.mark.asyncio
    async def test_service_discovery_integration(self):
        """Test service discovery with registry."""
        registry = WorkerRegistry()
        discovery = ServiceDiscovery(registry)

        # Register workers
        await registry.register_worker("w1", ["python", "code"])
        await registry.register_worker("w2", ["python"])
        await registry.register_worker("w3", ["java"])

        # Find by capability
        worker = discovery.find_by_capability("python", strategy="least_loaded")
        assert worker is not None
        assert worker.capabilities == ["python", "code"] or worker.capabilities == ["python"]

        # Find all with multiple capabilities
        workers = discovery.find_all_by_capabilities(["python", "java"])
        assert len(workers) == 3
