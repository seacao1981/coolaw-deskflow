"""Prometheus metrics endpoint for monitoring."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse

from deskflow.observability.logging import get_logger

if TYPE_CHECKING:
    from deskflow.core.agent import Agent
    from deskflow.memory.manager import MemoryManager
    from deskflow.tools.registry import ToolRegistry

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["metrics"])

# Start time for uptime calculation
_start_time = time.time()

# Metrics counters
_request_counter: dict[str, int] = {}
_request_latency: dict[str, list[float]] = {}


def _get_state() -> object:
    """Get app state at runtime."""
    from deskflow.app import get_app_state
    return get_app_state()


def _format_metric(name: str, value: str | float, labels: dict[str, str] | None = None) -> str:
    """Format a Prometheus metric line."""
    label_str = ""
    if labels:
        label_parts = [f'{k}="{v}"' for k, v in labels.items()]
        label_str = "{" + ",".join(label_parts) + "}"

    return f"{name}{label_str} {value}"


def _gauge_to_str(name: str, value: float, labels: dict[str, str] | None = None) -> str:
    """Format a gauge metric."""
    return _format_metric(name, value, labels)


def _counter_to_str(name: str, value: int, labels: dict[str, str] | None = None) -> str:
    """Format a counter metric."""
    return _format_metric(name, value, labels)


@router.get("/metrics", response_class=PlainTextResponse)
async def get_prometheus_metrics():
    """Get Prometheus metrics for monitoring."""

    state = _get_state()

    metrics_lines: list[str] = []

    # === Process Metrics ===
    import psutil

    process = psutil.Process()

    # CPU
    cpu_percent = process.cpu_percent(interval=0.1)
    metrics_lines.append("# HELP deskflow_process_cpu_percent Process CPU usage percentage")
    metrics_lines.append("# TYPE deskflow_process_cpu_percent gauge")
    metrics_lines.append(_gauge_to_str("deskflow_process_cpu_percent", cpu_percent))

    # Memory
    mem_info = process.memory_info()
    mem_rss_mb = mem_info.rss / 1024 / 1024
    mem_vms_mb = mem_info.vms / 1024 / 1024

    metrics_lines.append("# HELP deskflow_process_memory_rss_bytes Process RSS memory in bytes")
    metrics_lines.append("# TYPE deskflow_process_memory_rss_bytes gauge")
    metrics_lines.append(_gauge_to_str("deskflow_process_memory_rss_bytes", mem_info.rss))

    metrics_lines.append("# HELP deskflow_process_memory_vms_bytes Process VM size in bytes")
    metrics_lines.append("# TYPE deskflow_process_memory_vms_bytes gauge")
    metrics_lines.append(_gauge_to_str("deskflow_process_memory_vms_bytes", mem_info.vms))

    # Uptime
    uptime_seconds = time.time() - _start_time
    metrics_lines.append("# HELP deskflow_uptime_seconds Application uptime in seconds")
    metrics_lines.append("# TYPE deskflow_uptime_seconds counter")
    metrics_lines.append(_counter_to_str("deskflow_uptime_seconds", uptime_seconds))

    # === System Metrics ===
    system_memory = psutil.virtual_memory()
    system_disk = psutil.disk_usage("/")

    metrics_lines.append("# HELP deskflow_system_memory_percent System memory usage percentage")
    metrics_lines.append("# TYPE deskflow_system_memory_percent gauge")
    metrics_lines.append(_gauge_to_str("deskflow_system_memory_percent", system_memory.percent))

    metrics_lines.append("# HELP deskflow_system_disk_percent System disk usage percentage")
    metrics_lines.append("# TYPE deskflow_system_disk_percent gauge")
    metrics_lines.append(_gauge_to_str("deskflow_system_disk_percent", system_disk.percent))

    # === Memory System Metrics ===
    if state.memory:
        try:
            memory_count = await state.memory.count()
            cache_stats = state.memory.cache_stats()
            hnsw_stats = state.memory._hnsw.get_stats() if state.memory._hnsw else {}

            metrics_lines.append("# HELP deskflow_memory_total Total number of stored memories")
            metrics_lines.append("# TYPE deskflow_memory_total gauge")
            metrics_lines.append(_gauge_to_str("deskflow_memory_total", memory_count))

            metrics_lines.append("# HELP deskflow_memory_cache_hits Memory cache hit count")
            metrics_lines.append("# TYPE deskflow_memory_cache_hits counter")
            metrics_lines.append(_counter_to_str("deskflow_memory_cache_hits", cache_stats.get("hits", 0)))

            metrics_lines.append("# HELP deskflow_memory_cache_misses Memory cache miss count")
            metrics_lines.append("# TYPE deskflow_memory_cache_misses counter")
            metrics_lines.append(_counter_to_str("deskflow_memory_cache_misses", cache_stats.get("misses", 0)))

            cache_hit_rate = cache_stats.get("hit_rate", 0.0)
            metrics_lines.append("# HELP deskflow_memory_cache_hit_rate Memory cache hit rate (0-100)")
            metrics_lines.append("# TYPE deskflow_memory_cache_hit_rate gauge")
            metrics_lines.append(_gauge_to_str("deskflow_memory_cache_hit_rate", cache_hit_rate))

            hnsw_total = hnsw_stats.get("total_items", 0)
            metrics_lines.append("# HELP deskflow_memory_hnsw_index_size HNSW index item count")
            metrics_lines.append("# TYPE deskflow_memory_hnsw_index_size gauge")
            metrics_lines.append(_gauge_to_str("deskflow_memory_hnsw_index_size", hnsw_total))

        except Exception as e:
            logger.warning("memory_metrics_failed", error=str(e))

    # === Tool System Metrics ===
    if state.tools:
        try:
            tool_count = state.tools.count

            metrics_lines.append("# HELP deskflow_tools_registered Number of registered tools")
            metrics_lines.append("# TYPE deskflow_tools_registered gauge")
            metrics_lines.append(_gauge_to_str("deskflow_tools_registered", tool_count))

        except Exception as e:
            logger.warning("tool_metrics_failed", error=str(e))

    # === LLM Metrics ===
    if state.llm_client:
        try:
            # Get token usage if available
            provider = state.llm_client.provider_name
            model = state.llm_client.model_name

            metrics_lines.append("# HELP deskflow_llm_info LLM provider information")
            metrics_lines.append("# TYPE deskflow_llm_info gauge")
            metrics_lines.append(
                _gauge_to_str(
                    "deskflow_llm_info",
                    1,
                    {"provider": provider, "model": model},
                )
            )

        except Exception as e:
            logger.warning("llm_metrics_failed", error=str(e))

    # === Request Metrics ===
    metrics_lines.append("# HELP deskflow_http_requests_total Total HTTP requests")
    metrics_lines.append("# TYPE deskflow_http_requests_total counter")
    for endpoint, count in _request_counter.items():
        metrics_lines.append(_counter_to_str("deskflow_http_requests_total", count, {"endpoint": endpoint}))

    # Join all lines
    metrics_output = "\n".join(metrics_lines)

    return Response(content=metrics_output, media_type="text/plain")


def record_request(endpoint: str, latency_ms: float) -> None:
    """Record a request for metrics collection.

    Args:
        endpoint: The endpoint path
        latency_ms: Request latency in milliseconds
    """
    _request_counter[endpoint] = _request_counter.get(endpoint, 0) + 1

    if endpoint not in _request_latency:
        _request_latency[endpoint] = []

    _request_latency[endpoint].append(latency_ms)

    # Keep only last 1000 measurements per endpoint
    if len(_request_latency[endpoint]) > 1000:
        _request_latency[endpoint] = _request_latency[endpoint][-1000:]


@router.get("/metrics/summary")
async def get_metrics_summary():
    """Get a human-readable summary of metrics."""
    state = _get_state()

    # Collect basic stats
    summary = {
        "uptime_seconds": round(time.time() - _start_time, 2),
        "memory": {},
        "tools": {},
        "llm": {},
    }

    # Memory stats
    if state.memory:
        try:
            memory_count = await state.memory.count()
            cache_stats = state.memory.cache_stats()
            summary["memory"] = {
                "total": memory_count,
                "cache_hit_rate": cache_stats.get("hit_rate", 0.0),
            }
        except Exception:
            pass

    # Tool stats
    if state.tools:
        try:
            summary["tools"] = {
                "count": state.tools.count,
            }
        except Exception:
            pass

    # LLM info
    if state.llm_client:
        summary["llm"] = {
            "provider": state.llm_client.provider_name,
            "model": state.llm_client.model_name,
        }

    return summary
