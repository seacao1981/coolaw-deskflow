"""Activity logger for tracking system events.

Provides:
- LLM call logging
- Tool execution logging
- Memory operation logging
- Recent activity query
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Any, Literal
from enum import Enum

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


class ActivityType(str, Enum):
    """Type of activity."""

    LLM_CALL = "llm_call"
    TOOL_EXECUTION = "tool_execution"
    MEMORY_OPERATION = "memory_operation"
    SYSTEM_EVENT = "system_event"
    USER_ACTION = "user_action"


class ActivityStatus(str, Enum):
    """Status of activity."""

    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"


@dataclass
class ActivityRecord:
    """Single activity record."""

    id: str
    type: ActivityType
    status: ActivityStatus
    timestamp: datetime
    duration_ms: float = 0.0
    summary: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    conversation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "summary": self.summary,
            "details": self.details,
            "conversation_id": self.conversation_id,
        }


def _notify_new_activity(record: ActivityRecord) -> None:
    """Notify WebSocket clients about new activity."""
    try:
        from deskflow.api.routes.monitor import notify_activity_created
        notify_activity_created(record)
    except Exception:
        # Ignore notification errors (WebSocket may not be initialized)
        pass


class ActivityLogger:
    """Logger for system activities."""

    def __init__(self, working_dir: Path | None = None, max_records: int = 1000) -> None:
        self._working_dir = working_dir or Path.cwd() / "data" / "activities"
        self._working_dir.mkdir(parents=True, exist_ok=True)
        self._records: list[ActivityRecord] = []
        self._max_records = max_records
        self._today_count = 0
        self._today_date = date.today()

        # Load existing data
        self._load_data()

    def log(
        self,
        activity_type: ActivityType,
        status: ActivityStatus,
        summary: str,
        duration_ms: float = 0.0,
        details: dict[str, Any] | None = None,
        conversation_id: str | None = None,
    ) -> ActivityRecord:
        """Log an activity."""
        # Reset daily count if date changed
        today = date.today()
        if today != self._today_date:
            self._today_date = today
            self._today_count = 0

        record = ActivityRecord(
            id=f"act_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            type=activity_type,
            status=status,
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            summary=summary,
            details=details or {},
            conversation_id=conversation_id,
        )

        self._records.append(record)
        self._today_count += 1

        # Trim old records if exceeding max
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]

        logger.info(
            "activity_logged",
            type=activity_type.value,
            status=status.value,
            summary=summary,
        )

        # Notify WebSocket clients about new activity
        _notify_new_activity(record)

        return record

    def log_llm_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: float,
        status: ActivityStatus = ActivityStatus.SUCCESS,
        conversation_id: str | None = None,
    ) -> ActivityRecord:
        """Log an LLM call."""
        return self.log(
            activity_type=ActivityType.LLM_CALL,
            status=status,
            summary=f"LLM call to {model}",
            duration_ms=duration_ms,
            details={
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            conversation_id=conversation_id,
        )

    def log_tool_execution(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        duration_ms: float,
        status: ActivityStatus = ActivityStatus.SUCCESS,
        result: str | None = None,
        error: str | None = None,
    ) -> ActivityRecord:
        """Log a tool execution."""
        return self.log(
            activity_type=ActivityType.TOOL_EXECUTION,
            status=status,
            summary=f"Tool execution: {tool_name}",
            duration_ms=duration_ms,
            details={
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
                "error": error,
            },
        )

    def log_memory_operation(
        self,
        operation: str,
        count: int = 0,
        duration_ms: float = 0.0,
        status: ActivityStatus = ActivityStatus.SUCCESS,
    ) -> ActivityRecord:
        """Log a memory operation."""
        return self.log(
            activity_type=ActivityType.MEMORY_OPERATION,
            status=status,
            summary=f"Memory operation: {operation}",
            duration_ms=duration_ms,
            details={
                "operation": operation,
                "count": count,
            },
        )

    def get_recent_activities(
        self,
        limit: int = 20,
        activity_type: ActivityType | None = None,
        status: ActivityStatus | None = None,
    ) -> list[ActivityRecord]:
        """Get recent activities with optional filtering."""
        records = self._records

        # Apply filters
        if activity_type:
            records = [r for r in records if r.type == activity_type]
        if status:
            records = [r for r in records if r.status == status]

        # Return most recent first, limited
        return list(reversed(records[-limit:]))

    def get_today_count(self) -> int:
        """Get today's activity count."""
        today = date.today()
        if today != self._today_date:
            self._today_date = today
            self._today_count = 0
        return self._today_count

    def get_statistics(self) -> dict[str, Any]:
        """Get activity statistics."""
        total = len(self._records)

        # Count by type
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}

        for record in self._records:
            type_key = record.type.value
            status_key = record.status.value
            by_type[type_key] = by_type.get(type_key, 0) + 1
            by_status[status_key] = by_status.get(status_key, 0) + 1

        # Average duration by type
        duration_by_type: dict[str, float] = {}
        duration_count: dict[str, int] = {}

        for record in self._records:
            type_key = record.type.value
            if type_key not in duration_count:
                duration_count[type_key] = 0
                duration_by_type[type_key] = 0
            duration_by_type[type_key] += record.duration_ms
            duration_count[type_key] += 1

        for type_key in duration_by_type:
            if duration_count[type_key] > 0:
                duration_by_type[type_key] /= duration_count[type_key]

        return {
            "total_activities": total,
            "today_activities": self._today_count,
            "by_type": by_type,
            "by_status": by_status,
            "avg_duration_by_type": {
                k: round(v, 2) for k, v in duration_by_type.items()
            },
        }

    def save_data(self) -> Path:
        """Save activity data to file."""
        data_path = self._working_dir / "activities.json"

        data = {
            "total_records": len(self._records),
            "today_count": self._today_count,
            "today_date": self._today_date.isoformat(),
            "records": [r.to_dict() for r in self._records[-500:]],  # Last 500
        }

        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info("activity_data_saved", path=str(data_path))
        return data_path

    def _load_data(self) -> None:
        """Load activity data from file."""
        data_path = self._working_dir / "activities.json"

        if not data_path.exists():
            return

        try:
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._today_count = data.get("today_count", 0)
            today_str = date.today().isoformat()
            saved_date = data.get("today_date", "")

            # Reset count if date changed
            if saved_date != today_str:
                self._today_date = date.fromisoformat(today_str)
                self._today_count = 0
                self._records = []
            else:
                # Load records
                records = data.get("records", [])
                for r in records:
                    try:
                        record = ActivityRecord(
                            id=r["id"],
                            type=ActivityType(r["type"]),
                            status=ActivityStatus(r["status"]),
                            timestamp=datetime.fromisoformat(r["timestamp"]),
                            duration_ms=r.get("duration_ms", 0),
                            summary=r.get("summary", ""),
                            details=r.get("details", {}),
                            conversation_id=r.get("conversation_id"),
                        )
                        self._records.append(record)
                    except (KeyError, ValueError):
                        pass

            logger.info("activity_data_loaded", path=str(data_path))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("activity_data_load_failed", error=str(e))


# Global activity logger instance
_logger_instance: ActivityLogger | None = None


def get_activity_logger(working_dir: Path | None = None) -> ActivityLogger:
    """Get or create global activity logger."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = ActivityLogger(working_dir)
    return _logger_instance


def log_activity(*args, **kwargs) -> ActivityRecord:
    """Log activity using global logger."""
    logger_instance = get_activity_logger()
    return logger_instance.log(*args, **kwargs)


def get_recent_activities(*args, **kwargs) -> list[ActivityRecord]:
    """Get recent activities from global logger."""
    logger_instance = get_activity_logger()
    return logger_instance.get_recent_activities(*args, **kwargs)


def get_activity_statistics() -> dict[str, Any]:
    """Get activity statistics from global logger."""
    logger_instance = get_activity_logger()
    return logger_instance.get_statistics()
