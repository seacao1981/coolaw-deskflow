"""Tests for distributed tracing module."""

import pytest
from datetime import datetime

from deskflow.observability.tracing import (
    Span,
    SpanKind,
    SpanStatus,
    Trace,
    TracingConfig,
    TracingManager,
    ConsoleExporter,
    trace,
    get_tracing_manager,
    setup_tracing,
)


class TestSpan:
    """Test Span class."""

    def test_span_creation(self):
        """Test basic span creation."""
        span = Span(
            name="test_span",
            trace_id="trace123",
            span_id="span456",
        )

        assert span.name == "test_span"
        assert span.trace_id == "trace123"
        assert span.span_id == "span456"
        assert span.kind == SpanKind.INTERNAL
        assert span.status == SpanStatus.UNSET
        assert span.start_time is None

    def test_span_set_attribute(self):
        """Test setting span attributes."""
        span = Span(
            name="test_span",
            trace_id="trace123",
            span_id="span456",
        )

        span.set_attribute("user.id", "user789")
        span.set_attribute("http.method", "GET")

        assert span.attributes["user.id"] == "user789"
        assert span.attributes["http.method"] == "GET"

    def test_span_add_event(self):
        """Test adding events to span."""
        span = Span(
            name="test_span",
            trace_id="trace123",
            span_id="span456",
        )

        span.add_event("request_received", {"path": "/api/test"})

        assert len(span.events) == 1
        assert span.events[0]["name"] == "request_received"
        assert span.events[0]["attributes"]["path"] == "/api/test"

    def test_span_set_status(self):
        """Test setting span status."""
        span = Span(
            name="test_span",
            trace_id="trace123",
            span_id="span456",
        )

        span.set_status(SpanStatus.OK)
        assert span.status == SpanStatus.OK

        span.set_status(SpanStatus.ERROR)
        assert span.status == SpanStatus.ERROR

    def test_span_record_exception(self):
        """Test recording exception in span."""
        span = Span(
            name="test_span",
            trace_id="trace123",
            span_id="span456",
        )

        error = ValueError("Test error message")
        span.record_exception(error)

        assert span.status == SpanStatus.ERROR
        assert len(span.events) == 1
        assert span.events[0]["name"] == "exception"

    def test_span_to_dict(self):
        """Test span to_dict method."""
        span = Span(
            name="test_span",
            trace_id="trace123",
            span_id="span456",
            start_time=datetime(2024, 1, 1, 12, 0, 0),
            end_time=datetime(2024, 1, 1, 12, 0, 1),
        )

        result = span.to_dict()

        assert result["name"] == "test_span"
        assert result["trace_id"] == "trace123"
        assert result["span_id"] == "span456"
        assert result["duration_ms"] == 1000.0


class TestTrace:
    """Test Trace class."""

    def test_trace_creation(self):
        """Test basic trace creation."""
        trace = Trace(trace_id="trace123")

        assert trace.trace_id == "trace123"
        assert len(trace.spans) == 0
        assert trace.end_time is None

    def test_trace_add_span(self):
        """Test adding span to trace."""
        trace = Trace(trace_id="trace123")
        span = Span(
            name="child_span",
            trace_id="trace123",
            span_id="span456",
        )

        trace.add_span(span)

        assert len(trace.spans) == 1
        assert trace.spans[0].name == "child_span"

    def test_trace_finish(self):
        """Test finishing a trace."""
        trace = Trace(trace_id="trace123")
        trace.finish()

        assert trace.end_time is not None

    def test_trace_to_dict(self):
        """Test trace to_dict method."""
        trace = Trace(trace_id="trace123")
        trace.finish()

        result = trace.to_dict()

        assert result["trace_id"] == "trace123"
        assert result["end_time"] is not None


class TestTracingManager:
    """Test TracingManager class."""

    def test_start_trace(self):
        """Test starting a new trace."""
        manager = TracingManager(TracingConfig(exporter="console"))
        span = manager.start_trace("test_trace")

        assert span is not None
        assert span.name == "test_trace"
        assert span.trace_id is not None
        assert span.span_id is not None

    def test_start_span_with_parent(self):
        """Test starting a child span."""
        manager = TracingManager(TracingConfig(exporter="console"))
        parent = manager.start_trace("parent_trace")
        child = manager.start_span("child_span", parent=parent)

        assert child is not None
        assert child.trace_id == parent.trace_id
        assert child.parent_span_id == parent.span_id

    def test_end_span(self):
        """Test ending a span."""
        manager = TracingManager(TracingConfig(exporter="console"))
        span = manager.start_trace("test_trace")

        manager.end_span(span, SpanStatus.OK)

        assert span.end_time is not None
        assert span.status == SpanStatus.OK

    def test_trace_context_manager(self):
        """Test trace context manager."""
        manager = TracingManager(TracingConfig(exporter="console"))

        with manager.trace("context_trace") as span:
            assert span.name == "context_trace"

        # Span should be ended after context
        assert span.end_time is not None

    def test_inject_context(self):
        """Test injecting trace context."""
        manager = TracingManager(TracingConfig(exporter="console"))
        span = manager.start_trace("test_trace")

        headers = manager.inject_context(span)

        assert "traceparent" in headers
        assert "X-Trace-ID" in headers
        assert "X-Span-ID" in headers


class TestConsoleExporter:
    """Test ConsoleExporter class."""

    def test_export(self, capfd):
        """Test console exporter."""
        exporter = ConsoleExporter()
        trace = Trace(trace_id="test_trace")
        trace.add_span(
            Span(
                name="test_span",
                trace_id="test_trace",
                span_id="span123",
                start_time=datetime.now(),
                end_time=datetime.now(),
            )
        )

        result = exporter.export(trace)

        assert result is True
        captured = capfd.readouterr()
        assert "trace_exported_console" in captured.out or "test_trace" in captured.out


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_get_tracing_manager(self):
        """Test get_tracing_manager returns singleton."""
        manager1 = get_tracing_manager()
        manager2 = get_tracing_manager()

        # Should return same instance
        assert manager1 is manager2

    def test_setup_tracing(self):
        """Test setup_tracing creates configured manager."""
        manager = setup_tracing(
            enabled=True,
            exporter="console",
            service_name="test_service",
        )

        assert manager._config.enabled is True
        assert manager._config.exporter == "console"
        assert manager._config.service_name == "test_service"

    def test_trace_decorator(self):
        """Test trace context manager."""
        with trace("test_operation") as span:
            assert span.name == "test_operation"
            # Simulate work
            pass

        # Span should be completed
        assert span.end_time is not None
        assert span.status == SpanStatus.OK

    def test_trace_decorator_with_exception(self):
        """Test trace context manager handles exceptions."""
        with pytest.raises(ValueError):
            with trace("failing_operation") as span:
                raise ValueError("Test error")

        # Span should record the exception
        assert span.status == SpanStatus.ERROR
        assert len(span.events) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
