"""Log analyzer for automatic error pattern detection and insights.

Analyzes application logs to:
- Detect recurring error patterns
- Identify performance bottlenecks
- Extract actionable insights
- Generate improvement recommendations
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


class LogLevel(str, Enum):
    """Log level enumeration."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class PatternType(str, Enum):
    """Type of detected pattern."""

    ERROR_SPIKE = "error_spike"
    RECURRING_ERROR = "recurring_error"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    DEPENDENCY_FAILURE = "dependency_failure"
    UNUSUAL_BEHAVIOR = "unusual_behavior"


@dataclass
class LogEntry:
    """Parsed log entry."""

    timestamp: datetime
    level: LogLevel
    message: str
    event: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    raw: str = ""


@dataclass
class ErrorPattern:
    """Detected error pattern."""

    pattern_type: PatternType
    description: str
    error_type: str
    count: int
    first_seen: datetime
    last_seen: datetime
    sample_messages: list[str] = field(default_factory=list)
    affected_components: list[str] = field(default_factory=list)
    severity: str = "medium"  # low, medium, high, critical


@dataclass
class PerformanceInsight:
    """Performance-related insight."""

    metric: str
    trend: str  # improving, degrading, stable
    avg_value: float
    min_value: float
    max_value: float
    recommendation: str


@dataclass
class AnalysisReport:
    """Complete log analysis report."""

    analysis_period: tuple[datetime, datetime]
    total_entries: int
    error_patterns: list[ErrorPattern]
    performance_insights: list[PerformanceInsight]
    recommendations: list[str]
    summary: str


class LogParser:
    """Parse structured logs from various formats."""

    # Regex patterns for common log formats
    STRUCTLOG_PATTERN = re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z?)\s+'
        r'(?P<level>\w+)\s+'
        r'(?P<event>\[\w+\])?\s*'
        r'(?P<message>.*)$'
    )

    # JSON log pattern
    JSON_LOG_PATTERN = re.compile(r'^\{.*\}$')

    def __init__(self) -> None:
        self._parse_errors = 0

    def parse_line(self, line: str) -> LogEntry | None:
        """Parse a single log line.

        Args:
            line: Raw log line.

        Returns:
            Parsed LogEntry or None if parsing failed.
        """
        line = line.strip()
        if not line:
            return None

        # Try JSON format first
        if line.startswith("{"):
            return self._parse_json_log(line)

        # Try structlog format
        return self._parse_structlog_line(line)

    def _parse_json_log(self, line: str) -> LogEntry | None:
        """Parse JSON formatted log."""
        try:
            data = json.loads(line)

            # Extract timestamp
            timestamp_str = data.get("timestamp") or data.get("time") or data.get("@timestamp")
            timestamp = self._parse_timestamp(timestamp_str) if timestamp_str else datetime.now()

            # Extract level
            level_str = data.get("level", "info").lower()
            level = LogLevel(level_str) if level_str in [l.value for l in LogLevel] else LogLevel.INFO

            # Extract message
            message = data.get("message") or data.get("msg") or data.get("text") or ""

            # Extract event
            event = data.get("event")

            # Remaining fields are context
            context = {k: v for k, v in data.items()
                      if k not in ("timestamp", "time", "@timestamp", "level", "message", "msg", "text", "event")}

            return LogEntry(
                timestamp=timestamp,
                level=level,
                message=message,
                event=event,
                context=context,
                raw=line,
            )
        except (json.JSONDecodeError, ValueError) as e:
            self._parse_errors += 1
            logger.debug("json_log_parse_error", error=str(e))
            return None

    def _parse_structlog_line(self, line: str) -> LogEntry | None:
        """Parse structlog formatted log."""
        try:
            # Try to parse as key=value format
            parts = {}
            current_key = None
            current_value = ""
            in_string = False
            string_char = None

            i = 0
            while i < len(line):
                char = line[i]

                if char in ('"', "'") and (i == 0 or line[i-1] != "\\"):
                    if not in_string:
                        in_string = True
                        string_char = char
                    elif char == string_char:
                        in_string = False
                        if current_key:
                            parts[current_key] = current_value
                            current_key = None
                            current_value = ""
                elif char == " " and not in_string:
                    if current_key and current_value:
                        parts[current_key] = current_value.strip('"\'')
                        current_key = None
                        current_value = ""
                elif char == "=" and not in_string and current_key is None:
                    current_key = current_value
                    current_value = ""
                else:
                    current_value += char

                i += 1

            # Handle last key-value pair
            if current_key and current_value:
                parts[current_key] = current_value.strip('"\'')

            # Extract standard fields
            timestamp_str = parts.get("timestamp") or parts.get("time")
            timestamp = self._parse_timestamp(timestamp_str) if timestamp_str else datetime.now()

            level_str = parts.get("level", "info").lower()
            level = LogLevel(level_str) if level_str in [l.value for l in LogLevel] else LogLevel.INFO

            message = parts.get("message", parts.get("event", ""))
            event = parts.get("event")

            # Context is remaining fields
            context = {k: v for k, v in parts.items()
                      if k not in ("timestamp", "time", "level", "message", "event")}

            return LogEntry(
                timestamp=timestamp,
                level=level,
                message=message,
                event=event,
                context=context,
                raw=line,
            )
        except Exception as e:
            self._parse_errors += 1
            logger.debug("structlog_parse_error", error=str(e))
            return None

    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp string to datetime."""
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue

        # Fallback to current time
        return datetime.now()

    @property
    def parse_errors(self) -> int:
        """Get number of parse errors."""
        return self._parse_errors


class LogAnalyzer:
    """Analyze application logs for patterns and insights.

    Features:
    - Parse structured logs (JSON, structlog)
    - Detect error patterns and spikes
    - Identify performance trends
    - Generate actionable recommendations
    - Export analysis reports
    """

    # Error patterns to track
    ERROR_PATTERNS = [
        (r"error", "general_error"),
        (r"exception", "exception"),
        (r"timeout", "timeout"),
        (r"rate.?limit", "rate_limit"),
        (r"connection.*fail", "connection_failure"),
        (r"memory", "memory_issue"),
        (r"disk.*full", "disk_issue"),
        (r"permission.*denied", "permission_error"),
        (r"authentication", "auth_error"),
        (r"not.*found", "not_found"),
    ]

    # Performance patterns
    PERFORMANCE_EVENTS = [
        "tool_execution",
        "memory_query",
        "llm_request",
        "api_request",
    ]

    def __init__(
        self,
        log_dir: Path | None = None,
        max_entries: int = 10000,
    ) -> None:
        """Initialize log analyzer.

        Args:
            log_dir: Directory containing log files.
            max_entries: Maximum entries to analyze.
        """
        self._log_dir = log_dir or Path.cwd() / "logs"
        self._max_entries = max_entries
        self._parser = LogParser()
        self._entries: list[LogEntry] = []

    def load_logs(self, log_file: Path | None = None) -> int:
        """Load logs from file or directory.

        Args:
            log_file: Specific log file (defaults to latest in log_dir).

        Returns:
            Number of entries loaded.
        """
        self._entries = []

        if log_file is None:
            # Find latest log file
            log_files = sorted(self._log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime)
            if not log_files:
                logger.warning("no_log_files_found", path=str(self._log_dir))
                return 0
            log_file = log_files[-1]

        logger.info("loading_logs", path=str(log_file))

        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                if len(self._entries) >= self._max_entries:
                    break

                entry = self._parser.parse_line(line)
                if entry:
                    self._entries.append(entry)

        logger.info("logs_loaded", count=len(self._entries), errors=self._parser.parse_errors)
        return len(self._entries)

    def analyze(self, time_range: tuple[timedelta, timedelta] | None = None) -> AnalysisReport:
        """Analyze loaded logs.

        Args:
            time_range: Optional time range (recent, range).

        Returns:
            AnalysisReport with findings.
        """
        if not self._entries:
            return AnalysisReport(
                analysis_period=(datetime.now(), datetime.now()),
                total_entries=0,
                error_patterns=[],
                performance_insights=[],
                recommendations=["No logs to analyze"],
                summary="No data available",
            )

        # Filter by time range if specified
        entries = self._filter_by_time_range(entries=self._entries, time_range=time_range)

        # Determine analysis period
        timestamps = [e.timestamp for e in entries]
        start_time = min(timestamps) if timestamps else datetime.now()
        end_time = max(timestamps) if timestamps else datetime.now()

        # Analyze error patterns
        error_patterns = self._analyze_errors(entries)

        # Analyze performance
        performance_insights = self._analyze_performance(entries)

        # Generate recommendations
        recommendations = self._generate_recommendations(error_patterns, performance_insights)

        # Generate summary
        summary = self._generate_summary(entries, error_patterns, performance_insights)

        return AnalysisReport(
            analysis_period=(start_time, end_time),
            total_entries=len(entries),
            error_patterns=error_patterns,
            performance_insights=performance_insights,
            recommendations=recommendations,
            summary=summary,
        )

    def _filter_by_time_range(
        self,
        entries: list[LogEntry],
        time_range: tuple[timedelta, timedelta] | None,
    ) -> list[LogEntry]:
        """Filter entries by time range."""
        if not time_range:
            return entries

        now = datetime.now()
        start = now - time_range[0]
        end = now - time_range[1]

        return [e for e in entries if start <= e.timestamp <= end]

    def _analyze_errors(self, entries: list[LogEntry]) -> list[ErrorPattern]:
        """Analyze error patterns."""
        error_entries = [e for e in entries if e.level in (LogLevel.ERROR, LogLevel.CRITICAL)]

        if not error_entries:
            return []

        # Group by error type
        error_groups: dict[str, list[LogEntry]] = {}
        for entry in error_entries:
            # Try to identify error type from event or message
            error_type = entry.event or self._classify_error(entry.message)
            if error_type not in error_groups:
                error_groups[error_type] = []
            error_groups[error_type].append(entry)

        patterns = []
        for error_type, group in error_groups.items():
            timestamps = [e.timestamp for e in group]
            messages = [e.message for e in group]

            # Determine severity
            severity = self._determine_severity(len(group), len(entries))

            pattern = ErrorPattern(
                pattern_type=PatternType.RECURRING_ERROR,
                description=f"Recurring {error_type} errors",
                error_type=error_type,
                count=len(group),
                first_seen=min(timestamps),
                last_seen=max(timestamps),
                sample_messages=messages[:5],  # First 5 samples
                affected_components=list(set(e.context.get("component", "unknown") for e in group)),
                severity=severity,
            )
            patterns.append(pattern)

        # Sort by count (most frequent first)
        patterns.sort(key=lambda p: p.count, reverse=True)

        return patterns

    def _classify_error(self, message: str) -> str:
        """Classify error message into category."""
        message_lower = message.lower()
        for pattern, category in self.ERROR_PATTERNS:
            if re.search(pattern, message_lower):
                return category
        return "unknown_error"

    def _determine_severity(self, error_count: int, total_count: int) -> str:
        """Determine error severity based on frequency."""
        if total_count == 0:
            return "low"

        ratio = error_count / total_count

        if ratio > 0.1 or error_count > 100:
            return "critical"
        elif ratio > 0.05 or error_count > 50:
            return "high"
        elif ratio > 0.01 or error_count > 10:
            return "medium"
        else:
            return "low"

    def _analyze_performance(self, entries: list[LogEntry]) -> list[PerformanceInsight]:
        """Analyze performance metrics."""
        insights = []

        # Track duration metrics from log context
        duration_metrics: dict[str, list[float]] = {}

        for entry in entries:
            # Look for duration_ms in context
            duration = entry.context.get("duration_ms")
            event = entry.event or ""

            if duration is not None and isinstance(duration, (int, float)):
                if event not in duration_metrics:
                    duration_metrics[event] = []
                duration_metrics[event].append(float(duration))

        # Generate insights for each metric
        for metric, values in duration_metrics.items():
            if len(values) < 3:
                continue

            avg_val = sum(values) / len(values)
            min_val = min(values)
            max_val = max(values)

            # Determine trend (simple: compare first half vs second half)
            mid = len(values) // 2
            first_half_avg = sum(values[:mid]) / mid if mid > 0 else avg_val
            second_half_avg = sum(values[mid:]) / len(values[mid:]) if values[mid:] else avg_val

            if second_half_avg > first_half_avg * 1.2:
                trend = "degrading"
                recommendation = f"Investigate {metric} performance degradation - avg increased from {first_half_avg:.1f}ms to {second_half_avg:.1f}ms"
            elif second_half_avg < first_half_avg * 0.8:
                trend = "improving"
                recommendation = f"{metric} performance improving - keep monitoring"
            else:
                trend = "stable"
                recommendation = f"{metric} performance stable at {avg_val:.1f}ms average"

            insights.append(PerformanceInsight(
                metric=metric,
                trend=trend,
                avg_value=avg_val,
                min_value=min_val,
                max_value=max_val,
                recommendation=recommendation,
            ))

        return insights

    def _generate_recommendations(
        self,
        error_patterns: list[ErrorPattern],
        performance_insights: list[PerformanceInsight],
    ) -> list[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # Error-based recommendations
        for pattern in error_patterns:
            if pattern.severity in ("critical", "high"):
                recommendations.append(
                    f"URGENT: Address {pattern.error_type} errors - occurred {pattern.count} times"
                )
                if pattern.error_type == "rate_limit":
                    recommendations.append("Consider implementing request throttling or caching")
                elif pattern.error_type == "timeout":
                    recommendations.append("Review timeout settings and network dependencies")
                elif pattern.error_type == "connection_failure":
                    recommendations.append("Implement retry logic with exponential backoff")
                elif pattern.error_type == "memory_issue":
                    recommendations.append("Review memory usage and implement cleanup strategies")

        # Performance-based recommendations
        for insight in performance_insights:
            if insight.trend == "degrading":
                recommendations.append(insight.recommendation)

        return recommendations

    def _generate_summary(
        self,
        entries: list[LogEntry],
        error_patterns: list[ErrorPattern],
        performance_insights: list[PerformanceInsight],
    ) -> str:
        """Generate executive summary."""
        error_count = sum(1 for e in entries if e.level in (LogLevel.ERROR, LogLevel.CRITICAL))
        warning_count = sum(1 for e in entries if e.level == LogLevel.WARNING)

        summary_parts = [
            f"Analyzed {len(entries)} log entries.",
            f"Found {error_count} errors and {warning_count} warnings.",
        ]

        if error_patterns:
            critical_count = sum(1 for p in error_patterns if p.severity == "critical")
            high_count = sum(1 for p in error_patterns if p.severity == "high")
            summary_parts.append(
                f"Detected {len(error_patterns)} error patterns "
                f"({critical_count} critical, {high_count} high severity)."
            )

        if performance_insights:
            degrading = sum(1 for i in performance_insights if i.trend == "degrading")
            if degrading > 0:
                summary_parts.append(f"Warning: {degrading} performance metrics showing degradation.")

        return " ".join(summary_parts)

    def export_report(self, report: AnalysisReport, output_path: Path) -> None:
        """Export analysis report to JSON file.

        Args:
            report: Analysis report to export.
            output_path: Output file path.
        """
        report_data = {
            "analysis_period": {
                "start": report.analysis_period[0].isoformat(),
                "end": report.analysis_period[1].isoformat(),
            },
            "total_entries": report.total_entries,
            "error_patterns": [
                {
                    "pattern_type": p.pattern_type.value,
                    "description": p.description,
                    "error_type": p.error_type,
                    "count": p.count,
                    "first_seen": p.first_seen.isoformat(),
                    "last_seen": p.last_seen.isoformat(),
                    "severity": p.severity,
                    "sample_messages": p.sample_messages,
                    "affected_components": p.affected_components,
                }
                for p in report.error_patterns
            ],
            "performance_insights": [
                {
                    "metric": i.metric,
                    "trend": i.trend,
                    "avg_value": i.avg_value,
                    "min_value": i.min_value,
                    "max_value": i.max_value,
                    "recommendation": i.recommendation,
                }
                for i in report.performance_insights
            ],
            "recommendations": report.recommendations,
            "summary": report.summary,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        logger.info("report_exported", path=str(output_path))
