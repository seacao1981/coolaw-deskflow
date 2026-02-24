"""OpenTelemetry distributed tracing support.

Provides:
- Distributed trace context propagation
- Span creation and management
- Export to Jaeger/Zipkin backends
- Integration with FastAPI and LLM calls
"""

from __future__ import annotations

import contextlib
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


class SpanKind(Enum):
    """Type of span."""

    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(Enum):
    """Status of a span."""

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class Span:
    """Represents a single span in a trace."""

    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    kind: SpanKind = SpanKind.INTERNAL
    status: SpanStatus = SpanStatus.UNSET
    start_time: datetime | None = None
    end_time: datetime | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute."""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add an event to the span."""
        self.events.append({
            "name": name,
            "timestamp": datetime.now().isoformat(),
            "attributes": attributes or {},
        })

    def set_status(self, status: SpanStatus) -> None:
        """Set the span status."""
        self.status = status

    def record_exception(self, exception: Exception) -> None:
        """Record an exception in the span."""
        self.set_status(SpanStatus.ERROR)
        self.add_event("exception", {
            "type": type(exception).__name__,
            "message": str(exception),
        })

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "kind": self.kind.value,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "attributes": self.attributes,
            "events": self.events,
            "duration_ms": self._calculate_duration_ms(),
        }

    def _calculate_duration_ms(self) -> float | None:
        """Calculate span duration in milliseconds."""
        if not self.start_time or not self.end_time:
            return None
        return (self.end_time - self.start_time).total_seconds() * 1000


@dataclass
class Trace:
    """Represents a complete trace."""

    trace_id: str
    spans: list[Span] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None

    def add_span(self, span: Span) -> None:
        """Add a span to the trace."""
        self.spans.append(span)

    def finish(self) -> None:
        """Finish the trace."""
        self.end_time = datetime.now()

    @property
    def duration_ms(self) -> float | None:
        """Calculate trace duration in milliseconds."""
        if not self.end_time:
            return None
        return (self.end_time - self.start_time).total_seconds() * 1000

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trace_id": self.trace_id,
            "spans": [s.to_dict() for s in self.spans],
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
        }


class TracingExporter:
    """Base class for trace exporters."""

    def export(self, trace: Trace) -> bool:
        """Export a trace to the backend.

        Args:
            trace: Trace to export

        Returns:
            True if export succeeded, False otherwise
        """
        raise NotImplementedError


class ConsoleExporter(TracingExporter):
    """Export traces to console (for development)."""

    def export(self, trace: Trace) -> bool:
        """Print trace to console."""
        logger.info(
            "trace_exported_console",
            trace_id=trace.trace_id,
            span_count=len(trace.spans),
            duration_ms=trace.duration_ms,
        )
        for span in trace.spans:
            logger.info(
                "span_details",
                span_id=span.span_id,
                name=span.name,
                status=span.status.value,
                duration_ms=span._calculate_duration_ms(),
            )
        return True


class JaegerExporter(TracingExporter):
    """Export traces to Jaeger via HTTP.

    Note: Requires JAEGER_ENDPOINT environment variable or config.
    """

    def __init__(self, endpoint: str | None = None):
        import os
        self._endpoint = endpoint or os.getenv("JAEGER_ENDPOINT", "http://localhost:14268/api/traces")

    def export(self, trace: Trace) -> bool:
        """Export trace to Jaeger."""
        try:
            import json
            import urllib.request

            # Convert to Jaeger format
            jaeger_payload = self._convert_to_jaeger_format(trace)

            req = urllib.request.Request(
                self._endpoint,
                data=json.dumps(jaeger_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )

            with urllib.request.urlopen(req, timeout=5) as response:
                logger.info("trace_exported_jaeger", trace_id=trace.trace_id, status=response.status)
                return True

        except Exception as e:
            logger.warning("jaeger_export_failed", error=str(e))
            return False

    def _convert_to_jaeger_format(self, trace: Trace) -> dict[str, Any]:
        """Convert trace to Jaeger Thrift format."""
        # Simplified Jaeger format conversion
        return {
            "serviceName": "deskflow",
            "traceId": self._to_jaeger_trace_id(trace.trace_id),
            "spans": [self._convert_span(s) for s in trace.spans],
        }

    def _to_jaeger_trace_id(self, trace_id: str) -> str:
        """Convert trace ID to Jaeger format (64-bit hex)."""
        # Take last 16 chars for 64-bit representation
        return trace_id[-16:] if len(trace_id) > 16 else trace_id.zfill(16)

    def _convert_span(self, span: Span) -> dict[str, Any]:
        """Convert span to Jaeger format."""
        return {
            "operationName": span.name,
            "startTime": int(span.start_time.timestamp() * 1000) if span.start_time else 0,
            "duration": int(span._calculate_duration_ms() or 0) * 1000,  # microseconds
            "tags": [{"key": k, "value": str(v)} for k, v in span.attributes.items()],
            "logs": [self._convert_event(e) for e in span.events],
        }

    def _convert_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Convert event to Jaeger log format."""
        return {
            "timestamp": int(datetime.fromisoformat(event["timestamp"]).timestamp() * 1000),
            "fields": [{"key": k, "value": str(v)} for k, v in event.get("attributes", {}).items()],
        }


class ZipkinExporter(TracingExporter):
    """Export traces to Zipkin via HTTP."""

    def __init__(self, endpoint: str | None = None):
        import os
        self._endpoint = endpoint or os.getenv("ZIPKIN_ENDPOINT", "http://localhost:9411/api/v2/spans")

    def export(self, trace: Trace) -> bool:
        """Export trace to Zipkin."""
        try:
            import json
            import urllib.request

            zipkin_spans = [self._convert_to_zipkin_format(span, trace.trace_id) for span in trace.spans]

            req = urllib.request.Request(
                self._endpoint,
                data=json.dumps(zipkin_spans).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )

            with urllib.request.urlopen(req, timeout=5) as response:
                logger.info("trace_exported_zipkin", trace_id=trace.trace_id, status=response.status)
                return True

        except Exception as e:
            logger.warning("zipkin_export_failed", error=str(e))
            return False

    def _convert_to_zipkin_format(self, span: Span, trace_id: str) -> dict[str, Any]:
        """Convert span to Zipkin format."""
        return {
            "traceId": trace_id[-16:] if len(trace_id) > 16 else trace_id.zfill(16),
            "id": span.span_id[-16:] if len(span.span_id) > 16 else span.span_id.zfill(16),
            "parentId": span.parent_span_id[-16:] if span.parent_span_id else None,
            "name": span.name,
            "timestamp": int(span.start_time.timestamp() * 1000000) if span.start_time else 0,
            "duration": int(span._calculate_duration_ms() or 0) * 1000,
            "kind": self._map_span_kind(span.kind),
            "tags": {k: str(v) for k, v in span.attributes.items()},
        }

    def _map_span_kind(self, kind: SpanKind) -> str:
        """Map SpanKind to Zipkin kind."""
        mapping = {
            SpanKind.SERVER: "SERVER",
            SpanKind.CLIENT: "CLIENT",
            SpanKind.PRODUCER: "PRODUCER",
            SpanKind.CONSUMER: "CONSUMER",
        }
        return mapping.get(kind, "LOCAL")


class TracingConfig:
    """Tracing configuration."""

    def __init__(
        self,
        enabled: bool = True,
        service_name: str = "deskflow",
        export_format: str = "json",
        exporter: str = "console",
        sample_rate: float = 1.0,
        max_attributes: int = 128,
        max_events: int = 128,
    ):
        self.enabled = enabled
        self.service_name = service_name
        self.export_format = export_format
        self.exporter = exporter
        self.sample_rate = sample_rate
        self.max_attributes = max_attributes
        self.max_events = max_events


class TracingManager:
    """Manage distributed tracing."""

    def __init__(self, config: TracingConfig | None = None):
        self._config = config or TracingConfig()
        self._exporter = self._create_exporter()
        self._active_traces: dict[str, Trace] = {}
        self._active_spans: dict[str, Span] = {}

    def _create_exporter(self) -> TracingExporter:
        """Create exporter based on config."""
        if self._config.exporter == "jaeger":
            return JaegerExporter()
        elif self._config.exporter == "zipkin":
            return ZipkinExporter()
        else:
            return ConsoleExporter()

    def start_trace(self, name: str) -> Span:
        """Start a new trace and root span."""
        import uuid

        trace_id = uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]

        trace = Trace(trace_id=trace_id)
        span = Span(
            name=name,
            trace_id=trace_id,
            span_id=span_id,
            kind=SpanKind.SERVER,
            start_time=datetime.now(),
        )

        self._active_traces[trace_id] = trace
        self._active_spans[span_id] = span
        trace.add_span(span)

        logger.debug("trace_started", trace_id=trace_id, span_id=span_id, name=name)
        return span

    def start_span(
        self,
        name: str,
        parent: Span | None = None,
        kind: SpanKind = SpanKind.INTERNAL,
    ) -> Span:
        """Start a new child span."""
        import uuid

        if parent is None:
            # Find active span from context
            parent = self._get_active_span()

        trace_id = parent.trace_id if parent else uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]

        span = Span(
            name=name,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent.span_id if parent else None,
            kind=kind,
            start_time=datetime.now(),
        )

        self._active_spans[span_id] = span

        # Add to trace if exists
        if trace_id in self._active_traces:
            self._active_traces[trace_id].add_span(span)

        logger.debug("span_started", span_id=span_id, name=name, parent_span_id=span.parent_span_id)
        return span

    def end_span(self, span: Span, status: SpanStatus = SpanStatus.OK) -> None:
        """End a span."""
        span.end_time = datetime.now()
        span.set_status(status)

        if span.span_id in self._active_spans:
            del self._active_spans[span.span_id]

        # Check if trace is complete
        if span.trace_id in self._active_traces:
            trace = self._active_traces[span.trace_id]
            # Check if root span is complete
            root_span_completed = all(
                s.end_time is not None for s in trace.spans if s.parent_span_id is None
            )
            if root_span_completed:
                self._finish_trace(trace)

    def _finish_trace(self, trace: Trace) -> None:
        """Finish and export a trace."""
        trace.finish()

        logger.info(
            "trace_completed",
            trace_id=trace.trace_id,
            span_count=len(trace.spans),
            duration_ms=trace.duration_ms,
        )

        # Export
        self._exporter.export(trace)

        # Remove from active traces
        if trace.trace_id in self._active_traces:
            del self._active_traces[trace.trace_id]

    def _get_active_span(self) -> Span | None:
        """Get the most recently started active span."""
        if not self._active_spans:
            return None
        # Return the span with the latest start time (most recent)
        return max(self._active_spans.values(), key=lambda s: s.start_time or datetime.min)

    def get_current_trace(self) -> Trace | None:
        """Get the currently active trace."""
        active_span = self._get_active_span()
        if active_span and active_span.trace_id in self._active_traces:
            return self._active_traces[active_span.trace_id]
        return None

    def inject_context(self, span: Span) -> dict[str, str]:
        """Inject trace context into headers for propagation."""
        return {
            "traceparent": f"00-{span.trace_id}-{span.span_id}-01",
            "X-Trace-ID": span.trace_id,
            "X-Span-ID": span.span_id,
        }

    def extract_context(self, headers: dict[str, str]) -> Span | None:
        """Extract trace context from headers."""
        traceparent = headers.get("traceparent") or headers.get("X-Trace-ID")

        if not traceparent:
            return None

        # Parse W3C traceparent format: version-trace_id-parent_id-trace_flags
        if traceparent.startswith("00-"):
            parts = traceparent.split("-")
            if len(parts) >= 4:
                trace_id = parts[1]
                parent_span_id = parts[2]

                # Create span from extracted context
                span = Span(
                    name="extracted",
                    trace_id=trace_id,
                    span_id=parent_span_id,
                    start_time=datetime.now(),
                )
                return span

        return None

    @contextmanager
    def trace(self, name: str):
        """Context manager for tracing."""
        span = self.start_span(name)
        try:
            yield span
            self.end_span(span, SpanStatus.OK)
        except Exception as e:
            span.record_exception(e)
            self.end_span(span, SpanStatus.ERROR)
            raise


# Global tracing manager instance
_tracing_manager: TracingManager | None = None


def get_tracing_manager() -> TracingManager:
    """Get or create global tracing manager."""
    global _tracing_manager
    if _tracing_manager is None:
        _tracing_manager = TracingManager()
    return _tracing_manager


def setup_tracing(
    enabled: bool = True,
    exporter: str = "console",
    service_name: str = "deskflow",
) -> TracingManager:
    """Setup tracing configuration.

    Args:
        enabled: Enable/disable tracing
        exporter: Exporter type (console, jaeger, zipkin)
        service_name: Service name for tracing

    Returns:
        Configured TracingManager instance
    """
    global _tracing_manager

    config = TracingConfig(
        enabled=enabled,
        service_name=service_name,
        exporter=exporter,
    )

    _tracing_manager = TracingManager(config)

    logger.info(
        "tracing_setup_complete",
        enabled=enabled,
        exporter=exporter,
        service_name=service_name,
    )

    return _tracing_manager


@contextmanager
def trace(name: str):
    """Convenience context manager for creating traces."""
    manager = get_tracing_manager()
    span = manager.start_span(name)
    try:
        yield span
        manager.end_span(span, SpanStatus.OK)
    except Exception as e:
        span.record_exception(e)
        manager.end_span(span, SpanStatus.ERROR)
        raise
