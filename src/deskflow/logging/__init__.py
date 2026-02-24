"""Enhanced structured logging module.

Provides:
- JSON format output
- Session buffering (batch writes)
- Log rotation and cleanup
- File and console handlers
- Activity logger integration for real-time push notifications
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import structlog

from deskflow.observability.logging import get_logger as get_base_logger

logger = get_base_logger(__name__)

# Activity logger integration for real-time push
_activity_logger_enabled = False


def enable_activity_integration(enabled: bool = True) -> None:
    """Enable or disable activity logger integration.

    When enabled, log entries will be pushed to ActivityLogger
    for real-time WebSocket notifications.

    Args:
        enabled: Whether to enable integration
    """
    global _activity_logger_enabled
    _activity_logger_enabled = enabled


def _push_to_activity_logger(log_entry: dict[str, Any]) -> None:
    """Push log entry to activity logger for real-time notification.

    Args:
        log_entry: Log entry dictionary with level, message, context
    """
    if not _activity_logger_enabled:
        return

    try:
        from deskflow.observability.activity_logger import (
            ActivityStatus,
            ActivityType,
            get_activity_logger,
        )

        # Map log levels to activity status
        level = log_entry.get("level", "INFO")
        message = log_entry.get("message", "")
        context = log_entry.get("context", {})

        # Determine activity type based on logger name or context
        activity_type = ActivityType.SYSTEM_EVENT
        logger_name = log_entry.get("logger", "")

        if "tool" in logger_name.lower():
            activity_type = ActivityType.TOOL_EXECUTION
        elif "llm" in logger_name.lower():
            activity_type = ActivityType.LLM_CALL
        elif "memory" in logger_name.lower():
            activity_type = ActivityType.MEMORY_OPERATION
        elif "user" in logger_name.lower():
            activity_type = ActivityType.USER_ACTION

        # Determine status
        status = ActivityStatus.SUCCESS
        if level in ("ERROR", "CRITICAL"):
            status = ActivityStatus.FAILED
        elif level == "WARNING":
            status = ActivityStatus.PENDING

        # Log to activity logger (non-blocking)
        activity_logger = get_activity_logger()
        activity_logger.log(
            activity_type=activity_type,
            status=status,
            summary=message[:200],  # Truncate long messages
            duration_ms=context.get("duration_ms", 0.0),
            details=context,
        )
    except Exception:
        # Ignore errors in activity logging (don't interfere with main logging)
        pass


@dataclass
class LogBufferConfig:
    """Configuration for log buffering."""

    enabled: bool = True
    flush_interval: float = 5.0  # seconds
    max_buffer_size: int = 100  # logs before flush
    max_wait_time: float = 30.0  # max wait before forced flush


@dataclass
class LogCleanupConfig:
    """Configuration for log cleanup."""

    enabled: bool = True
    max_age_days: int = 7
    max_size_mb: int = 100
    cleanup_interval_hours: int = 24
    compression: bool = False  # compress old logs


class SessionBuffer:
    """Buffer for session-based log batching."""

    def __init__(self, config: LogBufferConfig | None = None):
        self._config = config or LogBufferConfig()
        self._buffer: deque[tuple[datetime, dict[str, Any]]] = deque()
        self._lock = threading.Lock()
        self._last_flush = time.time()
        self._session_id: str = ""

    def set_session(self, session_id: str) -> None:
        """Set current session ID."""
        self._session_id = session_id

    def add(self, log_entry: dict[str, Any]) -> None:
        """Add log entry to buffer."""
        if not self._config.enabled:
            return

        with self._lock:
            entry = (datetime.now(), log_entry)
            self._buffer.append(entry)

            # Check if we need to flush
            if len(self._buffer) >= self._config.max_buffer_size:
                self._flush_internal()

        # Push to activity logger if integration is enabled
        _push_to_activity_logger(log_entry)

    def _flush_internal(self) -> None:
        """Internal flush without lock (caller must hold lock)."""
        if not self._buffer:
            return

        # Write to file
        self._write_buffer()
        self._buffer.clear()
        self._last_flush = time.time()

    def flush(self) -> None:
        """Force flush buffer to file."""
        with self._lock:
            self._flush_internal()

    def _write_buffer(self) -> None:
        """Write buffered logs to file."""
        if not self._buffer:
            return

        log_dir = Path("data/logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        # Write to session file or daily file
        date_str = datetime.now().strftime("%Y%m%d")
        if self._session_id:
            log_file = log_dir / f"session_{self._session_id}_{date_str}.jsonl"
        else:
            log_file = log_dir / f"deskflow_{date_str}.jsonl"

        entries = list(self._buffer)
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                for timestamp, entry in entries:
                    entry["_timestamp"] = timestamp.isoformat()
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.warning("buffer_write_failed", error=str(e))

    def check_timed_flush(self) -> None:
        """Check if timed flush is needed."""
        if time.time() - self._last_flush > self._config.flush_interval:
            self.flush()


class LogCleaner:
    """Manages log cleanup and rotation."""

    def __init__(self, config: LogCleanupConfig | None = None):
        self._config = config or LogCleanupConfig()
        self._log_dir = Path("data/logs")
        self._cleanup_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start background cleanup thread."""
        if not self._config.enabled:
            return

        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="LogCleaner",
        )
        self._cleanup_thread.start()
        logger.info("log_cleaner_started")

    def stop(self) -> None:
        """Stop cleanup thread."""
        self._stop_event.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        logger.info("log_cleaner_stopped")

    def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while not self._stop_event.is_set():
            try:
                self._cleanup_old_logs()
                self._check_size_limit()
            except Exception as e:
                logger.error("cleanup_error", error=str(e))

            # Wait for next interval
            self._stop_event.wait(self._config.cleanup_interval_hours * 3600)

    def _cleanup_old_logs(self) -> None:
        """Remove logs older than max_age."""
        if not self._log_dir.exists():
            return

        cutoff = datetime.now() - timedelta(days=self._config.max_age_days)

        for log_file in self._log_dir.glob("*.jsonl"):
            try:
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff:
                    if self._config.compression:
                        # Compress instead of delete
                        import gzip

                        compressed = log_file.with_suffix(".jsonl.gz")
                        with open(log_file, "rb") as f_in, gzip.open(compressed, "wb") as f_out:
                            f_out.write(f_in.read())
                        log_file.unlink()
                        logger.info("log_compressed", file=str(log_file.name))
                    else:
                        log_file.unlink()
                        logger.info("log_deleted", file=str(log_file.name))
            except OSError as e:
                logger.warning("cleanup_file_failed", file=str(log_file.name), error=str(e))

    def _check_size_limit(self) -> None:
        """Check and enforce size limit."""
        if not self._log_dir.exists():
            return

        # Get total size
        total_size = sum(
            f.stat().st_size for f in self._log_dir.glob("*.jsonl*")
        ) / (1024 * 1024)  # MB

        if total_size > self._config.max_size_mb:
            logger.warning("log_size_exceeded", total_mb=round(total_size, 2))
            self._remove_oldest_logs(target_mb=self._config.max_size_mb * 0.8)

    def _remove_oldest_logs(self, target_mb: float) -> None:
        """Remove oldest logs until under target size."""
        logs = sorted(
            self._log_dir.glob("*.jsonl*"),
            key=lambda f: f.stat().st_mtime,
        )

        current_size = sum(f.stat().st_size for f in logs) / (1024 * 1024)

        for log_file in logs:
            if current_size <= target_mb:
                break

            try:
                log_file.unlink()
                current_size -= log_file.stat().st_size / (1024 * 1024)
                logger.info("log_deleted_size", file=str(log_file.name))
            except OSError:
                pass

    def get_stats(self) -> dict[str, Any]:
        """Get log storage statistics."""
        if not self._log_dir.exists():
            return {"total_size_mb": 0, "file_count": 0, "oldest_file": None}

        logs = list(self._log_dir.glob("*.jsonl*"))
        total_size = sum(f.stat().st_size for f in logs) / (1024 * 1024)

        oldest = None
        if logs:
            oldest_file = min(logs, key=lambda f: f.stat().st_mtime)
            oldest = {
                "name": oldest_file.name,
                "modified": datetime.fromtimestamp(oldest_file.stat().st_mtime).isoformat(),
            }

        return {
            "total_size_mb": round(total_size, 2),
            "file_count": len(logs),
            "oldest_file": oldest,
        }


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields
        if hasattr(record, "context"):
            log_data["context"] = record.context

        # Add exception info
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(log_data, ensure_ascii=False, default=str)


class EnhancedLogger:
    """Enhanced logger with buffering and cleanup."""

    def __init__(
        self,
        name: str | None = None,
        log_level: str = "INFO",
        buffer_config: LogBufferConfig | None = None,
        cleanup_config: LogCleanupConfig | None = None,
        json_output: bool = True,
    ):
        self._name = name
        self._log_level = log_level
        self._json_output = json_output
        self._buffer = SessionBuffer(buffer_config)
        self._cleaner = LogCleaner(cleanup_config)
        self._logger = structlog.get_logger(name)

    def set_session(self, session_id: str) -> None:
        """Set session ID for this logger."""
        self._buffer.set_session(session_id)

    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        """Internal log method."""
        # Log through structlog
        log_method = getattr(self._logger, level.lower(), self._logger.info)
        log_method(message, **kwargs)

        # Also buffer for batch write
        self._buffer.add({
            "level": level,
            "message": message,
            "logger": self._name or "root",
            "context": kwargs,
        })

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._log("DEBUG", message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self._log("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._log("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        self._log("ERROR", message, **kwargs)

    def exception(self, message: str, exc: Exception | None = None, **kwargs: Any) -> None:
        """Log exception."""
        if exc:
            kwargs["exception"] = str(exc)
        self._log("ERROR", message, **kwargs)

    def flush(self) -> None:
        """Flush buffer to file."""
        self._buffer.flush()

    def start(self) -> None:
        """Start logger (cleanup thread)."""
        self._cleaner.start()

    def stop(self) -> None:
        """Stop logger and flush buffer."""
        self._buffer.flush()
        self._cleaner.stop()


# Global instances
_buffer: SessionBuffer | None = None
_cleaner: LogCleaner | None = None


def setup_enhanced_logging(
    log_level: str = "INFO",
    json_output: bool = True,
    enable_buffer: bool = True,
    enable_cleanup: bool = True,
) -> None:
    """Setup enhanced logging with buffering and cleanup.

    Args:
        log_level: Minimum log level
        json_output: Output JSON format
        enable_buffer: Enable session buffering
        enable_cleanup: Enable log cleanup
    """
    global _buffer, _cleaner

    # Setup base structlog
    from deskflow.observability.logging import setup_logging
    setup_logging(log_level=log_level, json_output=json_output)

    if enable_buffer:
        _buffer = SessionBuffer()
        logger.info("log_buffer_enabled")

    if enable_cleanup:
        _cleaner = LogCleaner()
        _cleaner.start()
        logger.info("log_cleanup_enabled")


def get_session_buffer() -> SessionBuffer | None:
    """Get global session buffer."""
    return _buffer


def get_log_cleaner() -> LogCleaner | None:
    """Get global log cleaner."""
    return _cleaner


def set_current_session(session_id: str) -> None:
    """Set current session ID for buffering."""
    if _buffer:
        _buffer.set_session(session_id)


def flush_logs() -> None:
    """Flush all buffered logs."""
    if _buffer:
        _buffer.flush()
