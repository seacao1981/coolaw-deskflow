"""Distributed tracing API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException

from deskflow.observability.logging import get_logger
from deskflow.observability.tracing import (
    get_tracing_manager,
    Span,
    SpanStatus,
    SpanKind,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/tracing", tags=["tracing"])


def _get_state() -> Any:
    """Get app state at runtime."""
    from deskflow.app import get_app_state
    return get_app_state()


@router.get("/config")
async def get_tracing_config():
    """Get current tracing configuration."""
    manager = get_tracing_manager()
    config = manager._config

    return {
        "enabled": config.enabled,
        "service_name": config.service_name,
        "exporter": config.exporter,
        "sample_rate": config.sample_rate,
        "max_attributes": config.max_attributes,
        "max_events": config.max_events,
    }


@router.post("/span/start")
async def start_span(
    name: str,
    parent_trace_id: str | None = None,
    parent_span_id: str | None = None,
    kind: str = "internal",
    x_trace_id: str | None = Header(None, alias="X-Trace-ID"),
    x_span_id: str | None = Header(None, alias="X-Span-ID"),
):
    """Start a new span.

    Args:
        name: Span name
        parent_trace_id: Optional parent trace ID
        parent_span_id: Optional parent span ID
        kind: Span kind (internal, server, client, producer, consumer)
        x_trace_id: Trace ID from headers
        x_span_id: Parent span ID from headers

    Returns:
        Created span information
    """
    manager = get_tracing_manager()

    # Check for trace context in headers
    if x_trace_id:
        # Create span from extracted context
        span = Span(
            name=name,
            trace_id=x_trace_id,
            span_id=x_span_id or manager._active_spans[0].span_id if manager._active_spans else None,
            parent_span_id=x_span_id,
            kind=SpanKind(kind) if kind in SpanKind.__members__ else SpanKind.INTERNAL,
        )
        manager._active_spans[span.span_id] = span
    else:
        # Start new trace if no parent
        if parent_trace_id is None:
            span = manager.start_span(name, kind=SpanKind(kind))
        else:
            # Create child span
            parent = manager._active_spans.get(parent_span_id) if parent_span_id else None
            span = manager.start_span(name, parent=parent, kind=SpanKind(kind))

    return {
        "success": True,
        "span": {
            "trace_id": span.trace_id,
            "span_id": span.span_id,
            "parent_span_id": span.parent_span_id,
            "name": span.name,
            "kind": span.kind.value,
            "start_time": span.start_time.isoformat() if span.start_time else None,
        },
    }


@router.post("/span/end")
async def end_span(
    span_id: str,
    status: str = "ok",
    attributes: dict[str, Any] | None = None,
):
    """End a span.

    Args:
        span_id: ID of the span to end
        status: Span status (unset, ok, error)
        attributes: Optional attributes to add

    Returns:
        End result
    """
    manager = get_tracing_manager()

    span = manager._active_spans.get(span_id)
    if not span:
        # Try to find in recently completed
        raise HTTPException(status_code=404, detail=f"Span '{span_id}' not found")

    # Add attributes if provided
    if attributes:
        for key, value in attributes.items():
            span.set_attribute(key, value)

    # End the span
    manager.end_span(span, SpanStatus(status))

    return {
        "success": True,
        "span_id": span_id,
        "status": status,
        "end_time": span.end_time.isoformat() if span.end_time else None,
        "duration_ms": span._calculate_duration_ms(),
    }


@router.post("/span/event")
async def add_span_event(
    span_id: str,
    event_name: str,
    attributes: dict[str, Any] | None = None,
):
    """Add an event to a span.

    Args:
        span_id: ID of the span
        event_name: Name of the event
        attributes: Optional event attributes

    Returns:
        Event addition result
    """
    manager = get_tracing_manager()

    span = manager._active_spans.get(span_id)
    if not span:
        raise HTTPException(status_code=404, detail=f"Span '{span_id}' not found")

    span.add_event(event_name, attributes or {})

    return {
        "success": True,
        "span_id": span_id,
        "event_name": event_name,
    }


@router.post("/span/exception")
async def record_span_exception(
    span_id: str,
    exception_type: str,
    exception_message: str,
):
    """Record an exception in a span.

    Args:
        span_id: ID of the span
        exception_type: Exception class name
        exception_message: Exception message

    Returns:
        Exception recording result
    """
    manager = get_tracing_manager()

    span = manager._active_spans.get(span_id)
    if not span:
        raise HTTPException(status_code=404, detail=f"Span '{span_id}' not found")

    span.record_exception(Exception(f"{exception_type}: {exception_message}"))

    return {
        "success": True,
        "span_id": span_id,
        "exception_type": exception_type,
    }


@router.get("/active-traces")
async def get_active_traces():
    """Get list of currently active traces."""
    manager = get_tracing_manager()

    traces = []
    for trace_id, trace in manager._active_traces.items():
        traces.append({
            "trace_id": trace_id,
            "span_count": len(trace.spans),
            "start_time": trace.start_time.isoformat(),
            "duration_ms": trace.duration_ms,
        })

    return {
        "active_traces": traces,
        "total": len(traces),
    }


@router.get("/trace/{trace_id}")
async def get_trace(trace_id: str):
    """Get trace details by ID.

    Note: This returns traces from active traces only.
    For production, integrate with Jaeger/Zipkin API.
    """
    manager = get_tracing_manager()

    trace = manager._active_traces.get(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")

    return {
        "success": True,
        "trace": trace.to_dict(),
    }


@router.get("/propagation-headers")
async def get_propagation_headers(span_id: str):
    """Get trace propagation headers for a span.

    Use these headers to propagate trace context to downstream services.
    """
    manager = get_tracing_manager()

    span = manager._active_spans.get(span_id)
    if not span:
        raise HTTPException(status_code=404, detail=f"Span '{span_id}' not found")

    headers = manager.inject_context(span)

    return {
        "success": True,
        "span_id": span_id,
        "headers": headers,
    }
