"""Enhanced health check API routes with comprehensive component monitoring."""

from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import datetime
from typing import Any

import psutil
from fastapi import APIRouter

from deskflow.api.schemas.models import ComponentHealth, HealthResponse
from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


def _get_state() -> Any:
    """Get app state at runtime."""
    from deskflow.app import get_app_state

    return get_app_state()


async def _check_memory_health(state: Any) -> ComponentHealth:
    """Check memory system health."""
    try:
        memory = state.memory
        if not memory:
            return ComponentHealth(status="error", details={"error": "Memory not initialized"})

        # Get memory count
        count = await memory.count()

        # Check database file size
        db_path = state.config.get_db_path()
        if db_path.exists():
            db_size_mb = db_path.stat().st_size / (1024 * 1024)
        else:
            db_size_mb = 0

        # Check cache hit rate if available
        cache_stats = getattr(memory, "cache_stats", None)
        cache_info = {}
        if cache_stats:
            cache_info = {
                "hits": getattr(cache_stats, "hits", 0),
                "misses": getattr(cache_stats, "misses", 0),
            }

        return ComponentHealth(
            status="ok",
            details={
                "count": count,
                "database_size_mb": round(db_size_mb, 2),
                "cache": cache_info,
            },
        )
    except Exception as e:
        return ComponentHealth(status="error", details={"error": str(e)})


async def _check_tools_health(state: Any) -> ComponentHealth:
    """Check tools system health."""
    try:
        tools = state.tools
        if not tools:
            return ComponentHealth(status="error", details={"error": "Tools not initialized"})

        # Get registered tools (list_tools is synchronous)
        tool_list = tools.list_tools() if hasattr(tools, "list_tools") else []
        tool_names = [t.name if hasattr(t, "name") else str(t) for t in tool_list]

        # Test tool responsiveness (ping test)
        responsive_tools = []
        unresponsive_tools = []

        for tool_name in tool_names[:5]:  # Test first 5 tools
            try:
                # Try to get tool info (non-destructive operation)
                if hasattr(tools, "get_tool"):
                    tool = await tools.get_tool(tool_name)
                    if tool:
                        responsive_tools.append(tool_name)
                    else:
                        unresponsive_tools.append(tool_name)
                else:
                    responsive_tools.append(tool_name)
            except Exception:
                unresponsive_tools.append(tool_name)

        details = {
            "total_count": len(tool_names),
            "responsive": len(responsive_tools),
            "unresponsive": len(unresponsive_tools),
            "tools": tool_names,
        }

        if unresponsive_tools:
            details["unresponsive_list"] = unresponsive_tools

        status = "ok" if not unresponsive_tools else "degraded"
        return ComponentHealth(status=status, details=details)
    except Exception as e:
        return ComponentHealth(status="error", details={"error": str(e)})


async def _check_llm_health(state: Any) -> ComponentHealth:
    """Check LLM connection health."""
    try:
        llm = state.llm_client
        if not llm:
            return ComponentHealth(
                status="error",
                details={"error": "LLM not initialized"},
            )

        provider = getattr(llm, "provider_name", "unknown")
        model = getattr(llm, "model_name", "unknown")

        # Check if we have API key configured
        # LLMClient stores adapters in _primary and _adapters list
        # BaseLLMAdapter stores api_key in _api_key attribute
        has_api_key = False
        if hasattr(llm, "_primary"):
            has_api_key = bool(getattr(llm._primary, "_api_key", None))

        details = {
            "provider": provider,
            "model": model,
            "api_key_configured": has_api_key,
        }

        # Quick connectivity test (optional, with timeout)
        try:
            start = time.time()
            # Try a minimal API call if available
            if hasattr(llm, "test_connection"):
                result = await asyncio.wait_for(
                    llm.test_connection(),
                    timeout=5.0,
                )
                latency_ms = (time.time() - start) * 1000
                details["latency_ms"] = round(latency_ms, 2)
                details["connectivity"] = "ok" if result else "error"
            else:
                details["connectivity"] = "unknown"
        except asyncio.TimeoutError:
            details["connectivity"] = "timeout"
        except Exception as e:
            details["connectivity"] = f"error: {str(e)}"

        return ComponentHealth(status="ok", details=details)

    except Exception as e:
        return ComponentHealth(status="error", details={"error": str(e)})


def _check_system_health() -> dict[str, Any]:
    """Check system resource health."""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # Memory usage
        mem = psutil.virtual_memory()
        mem_percent = mem.percent
        mem_available_gb = mem.available / (1024 ** 3)

        # Disk usage
        disk = psutil.disk_usage("/")
        disk_percent = disk.percent
        disk_free_gb = disk.free / (1024 ** 3)

        # Determine status
        issues = []
        if cpu_percent > 90:
            issues.append("High CPU usage")
        if mem_percent > 90:
            issues.append("High memory usage")
        if disk_percent > 90:
            issues.append("Low disk space")

        return {
            "cpu_percent": cpu_percent,
            "memory_percent": mem_percent,
            "memory_available_gb": round(mem_available_gb, 2),
            "disk_percent": disk_percent,
            "disk_free_gb": round(disk_free_gb, 2),
            "issues": issues,
            "status": "ok" if not issues else "warning",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _check_process_health() -> dict[str, Any]:
    """Check current process health."""
    try:
        process = psutil.Process()

        # Process CPU and memory
        cpu_percent = process.cpu_percent(interval=0.1)
        mem_info = process.memory_info()
        mem_mb = mem_info.rss / (1024 * 1024)

        # Open file handles
        num_fds = process.num_fds() if hasattr(process, "num_fds") else 0

        # Thread count
        num_threads = process.num_threads()

        # Process uptime
        create_time = datetime.fromtimestamp(process.create_time())
        uptime = datetime.now() - create_time

        return {
            "cpu_percent": cpu_percent,
            "memory_mb": round(mem_mb, 2),
            "open_files": num_fds,
            "threads": num_threads,
            "uptime_hours": round(uptime.total_seconds() / 3600, 2),
            "status": "ok",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/health", response_model=HealthResponse)
async def health_check(detailed: bool = False) -> HealthResponse:
    """Health check endpoint with optional detailed diagnostics.

    Args:
        detailed: If True, include system and process health metrics.

    Returns:
        HealthResponse with component status and optional detailed metrics.
    """
    state = _get_state()
    components: dict[str, ComponentHealth] = {}

    # Check all components in parallel
    memory_health, tools_health, llm_health = await asyncio.gather(
        _check_memory_health(state),
        _check_tools_health(state),
        _check_llm_health(state),
        return_exceptions=False,
    )

    components["memory"] = memory_health
    components["tools"] = tools_health
    components["llm"] = llm_health

    # Agent status (always ok if we got here)
    components["agent"] = ComponentHealth(status="ok")

    # Add system health if detailed
    if detailed:
        components["system"] = ComponentHealth(
            status="ok",
            details=_check_system_health(),
        )
        components["process"] = ComponentHealth(
            status="ok",
            details=_check_process_health(),
        )

    # Determine overall status
    statuses = [c.status for c in components.values()]
    if all(s == "ok" for s in statuses):
        overall = "ok"
    elif any(s == "error" for s in statuses):
        overall = "error"
    else:
        overall = "degraded"

    return HealthResponse(
        status=overall,
        version=state.config.version,
        components=components,
    )


@router.get("/health/detailed")
async def detailed_health_check() -> dict[str, Any]:
    """Comprehensive health check with all diagnostics.

    Returns:
        Detailed health report including all components, system metrics, and recommendations.
    """
    state = _get_state()
    report = {
        "timestamp": datetime.now().isoformat(),
        "version": state.config.version,
        "components": {},
        "system": {},
        "process": {},
        "recommendations": [],
    }

    # Component health
    memory_health, tools_health, llm_health = await asyncio.gather(
        _check_memory_health(state),
        _check_tools_health(state),
        _check_llm_health(state),
        return_exceptions=False,
    )

    report["components"] = {
        "agent": {"status": "ok"},
        "memory": memory_health.model_dump(),
        "tools": tools_health.model_dump(),
        "llm": llm_health.model_dump(),
    }

    # System health
    report["system"] = _check_system_health()
    report["process"] = _check_process_health()

    # Generate recommendations
    recommendations = []

    # Memory recommendations
    if memory_health.status == "error":
        recommendations.append("Memory system needs attention - check database connection")
    elif memory_health.details.get("count", 0) > 10000:
        recommendations.append("Consider running memory consolidation to optimize storage")

    # Tools recommendations
    if tools_health.details.get("unresponsive", 0) > 0:
        recommendations.append("Some tools are unresponsive - check tool configurations")

    # LLM recommendations
    if not llm_health.details.get("api_key_configured"):
        recommendations.append("LLM API key not configured - set up API credentials")
    elif llm_health.details.get("connectivity") == "error":
        recommendations.append("LLM connectivity issues - check network and API endpoint")

    # System recommendations
    system_health = report["system"]
    if system_health.get("cpu_percent", 0) > 80:
        recommendations.append("High CPU usage - consider scaling or optimizing workloads")
    if system_health.get("memory_percent", 0) > 80:
        recommendations.append("High memory usage - consider increasing available memory")
    if system_health.get("disk_percent", 0) > 80:
        recommendations.append("Low disk space - clean up logs and temporary files")

    report["recommendations"] = recommendations

    # Overall status
    error_count = sum(
        1 for c in report["components"].values()
        if c.get("status") == "error"
    )
    warning_count = sum(
        1 for c in report["components"].values()
        if c.get("status") == "degraded"
    )

    report["summary"] = {
        "status": "error" if error_count > 0 else ("warning" if warning_count > 0 else "ok"),
        "error_count": error_count,
        "warning_count": warning_count,
        "recommendation_count": len(recommendations),
    }

    return report


@router.get("/status")
async def status() -> dict[str, Any]:
    """Detailed agent status."""
    state = _get_state()
    memory_count = 0
    with contextlib.suppress(Exception):
        memory_count = await state.memory.count()

    agent_status = state.monitor.get_status(
        memory_count=memory_count,
        active_tools=state.tools.count if state.tools else 0,
        available_tools=state.tools.count if state.tools else 0,
        llm_provider=state.llm_client.provider_name if state.llm_client else "",
        llm_model=state.llm_client.model_name if state.llm_client else "",
    )
    return agent_status.model_dump()  # type: ignore[no-any-return]
