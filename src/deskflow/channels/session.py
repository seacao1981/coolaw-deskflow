"""Session management for cross-platform context tracking.

Provides:
- Session ID generation (UUID)
- Session state storage (SQLite)
- Context management
- Auto-cleanup for expired sessions
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SessionData:
    """Session data structure."""

    session_id: str
    user_id: str
    channel_id: str
    created_at: datetime
    last_activity: datetime
    ttl_seconds: int = 3600  # Default 1 hour
    context: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if session is expired."""
        expiry = self.last_activity + timedelta(seconds=self.ttl_seconds)
        return datetime.utcnow() > expiry

    @property
    def remaining_ttl(self) -> int:
        """Return remaining TTL in seconds."""
        expiry = self.last_activity + timedelta(seconds=self.ttl_seconds)
        remaining = (expiry - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "channel_id": self.channel_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "ttl_seconds": self.ttl_seconds,
            "remaining_ttl": self.remaining_ttl,
            "is_expired": self.is_expired,
            "context": self.context,
            "metadata": self.metadata,
        }

    def add_to_context(self, message: str, role: str = "user") -> None:
        """Add a message to the session context."""
        self.context.append({
            "role": role,
            "content": message,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self.last_activity = datetime.utcnow()

    def clear_context(self) -> None:
        """Clear session context."""
        self.context.clear()
        self.last_activity = datetime.utcnow()


class SessionStore:
    """SQLite-based session storage."""

    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._lock = asyncio.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_activity TEXT NOT NULL,
                ttl_seconds INTEGER NOT NULL DEFAULT 3600,
                context TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}'
            )
        """)

        # Create indexes separately
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON sessions (user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel_id ON sessions (channel_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_last_activity ON sessions (last_activity)")

        conn.commit()
        conn.close()

    async def save(self, session: SessionData) -> None:
        """Save session to database."""
        async with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO sessions
                (session_id, user_id, channel_id, created_at, last_activity, ttl_seconds, context, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session.session_id,
                session.user_id,
                session.channel_id,
                session.created_at.isoformat(),
                session.last_activity.isoformat(),
                session.ttl_seconds,
                json.dumps(session.context, ensure_ascii=False),
                json.dumps(session.metadata, ensure_ascii=False),
            ))

            conn.commit()
            conn.close()

    async def get(self, session_id: str) -> SessionData | None:
        """Get session from database."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT session_id, user_id, channel_id, created_at, last_activity, ttl_seconds, context, metadata
            FROM sessions
            WHERE session_id = ?
        """, (session_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return SessionData(
            session_id=row[0],
            user_id=row[1],
            channel_id=row[2],
            created_at=datetime.fromisoformat(row[3]),
            last_activity=datetime.fromisoformat(row[4]),
            ttl_seconds=row[5],
            context=json.loads(row[6]),
            metadata=json.loads(row[7]),
        )

    async def delete(self, session_id: str) -> bool:
        """Delete session from database."""
        async with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            deleted = cursor.rowcount > 0

            conn.commit()
            conn.close()

            return deleted

    async def get_by_user(self, user_id: str, channel_id: str | None = None) -> list[SessionData]:
        """Get all sessions for a user."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        if channel_id:
            cursor.execute("""
                SELECT session_id, user_id, channel_id, created_at, last_activity, ttl_seconds, context, metadata
                FROM sessions
                WHERE user_id = ? AND channel_id = ?
                ORDER BY last_activity DESC
            """, (user_id, channel_id))
        else:
            cursor.execute("""
                SELECT session_id, user_id, channel_id, created_at, last_activity, ttl_seconds, context, metadata
                FROM sessions
                WHERE user_id = ?
                ORDER BY last_activity DESC
            """, (user_id,))

        rows = cursor.fetchall()
        conn.close()

        return [
            SessionData(
                session_id=row[0],
                user_id=row[1],
                channel_id=row[2],
                created_at=datetime.fromisoformat(row[3]),
                last_activity=datetime.fromisoformat(row[4]),
                ttl_seconds=row[5],
                context=json.loads(row[6]),
                metadata=json.loads(row[7]),
            )
            for row in rows
        ]

    async def get_expired(self, limit: int = 100) -> list[SessionData]:
        """Get expired sessions for cleanup."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        # Use CAST to ensure numeric comparison
        cursor.execute("""
            SELECT session_id, user_id, channel_id, created_at, last_activity, ttl_seconds, context, metadata
            FROM sessions
            WHERE (CAST(strftime('%s', last_activity) AS INTEGER) + ttl_seconds) < CAST(strftime('%s', 'now') AS INTEGER)
            ORDER BY last_activity ASC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [
            SessionData(
                session_id=row[0],
                user_id=row[1],
                channel_id=row[2],
                created_at=datetime.fromisoformat(row[3]),
                last_activity=datetime.fromisoformat(row[4]),
                ttl_seconds=row[5],
                context=json.loads(row[6]),
                metadata=json.loads(row[7]),
            )
            for row in rows
        ]

    async def delete_expired(self) -> int:
        """Delete expired sessions and return count."""
        async with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            # Use CAST to ensure numeric comparison
            cursor.execute("""
                DELETE FROM sessions
                WHERE (CAST(strftime('%s', last_activity) AS INTEGER) + ttl_seconds) < CAST(strftime('%s', 'now') AS INTEGER)
            """)

            deleted = cursor.rowcount
            conn.commit()
            conn.close()

            if deleted > 0:
                logger.info("expired_sessions_deleted", count=deleted)

            return deleted

    async def count(self) -> int:
        """Get total session count."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM sessions")
        count = cursor.fetchone()[0]

        conn.close()
        return count

    async def count_active(self) -> int:
        """Get count of non-expired sessions."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM sessions
            WHERE (CAST(strftime('%s', last_activity) AS INTEGER) + ttl_seconds) >= CAST(strftime('%s', 'now') AS INTEGER)
        """)

        count = cursor.fetchone()[0]
        conn.close()
        return count

    async def close(self) -> None:
        """Close database connection."""
        # SQLite connections are closed after each operation
        pass


class SessionManager:
    """Manage user sessions across channels."""

    def __init__(
        self,
        db_path: str | Path = "data/db/sessions.db",
        default_ttl: int = 3600,
        cleanup_interval: int = 300,  # 5 minutes
    ):
        self._store = SessionStore(db_path)
        self._default_ttl = default_ttl
        self._cleanup_interval = cleanup_interval
        self._cleanup_task: asyncio.Task | None = None
        self._running = False

        # In-memory cache for active sessions
        self._cache: dict[str, SessionData] = {}

    async def start(self) -> None:
        """Start session manager (begin cleanup loop)."""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("session_manager_started")

    async def stop(self) -> None:
        """Stop session manager."""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        await self._store.close()
        logger.info("session_manager_stopped")

    async def _cleanup_loop(self) -> None:
        """Background loop for cleaning up expired sessions."""
        while self._running:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self.cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("session_cleanup_error", error=str(e))

    async def create_session(
        self,
        user_id: str,
        channel_id: str,
        ttl_seconds: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a new session.

        Args:
            user_id: User identifier
            channel_id: Channel identifier (e.g., 'feishu', 'wework')
            ttl_seconds: Session TTL in seconds (default: 3600)
            metadata: Optional session metadata

        Returns:
            Session ID
        """
        session_id = uuid.uuid4().hex

        session = SessionData(
            session_id=session_id,
            user_id=user_id,
            channel_id=channel_id,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            ttl_seconds=ttl_seconds or self._default_ttl,
            metadata=metadata or {},
        )

        await self._store.save(session)
        self._cache[session_id] = session

        logger.info(
            "session_created",
            session_id=session_id[:8],
            user_id=user_id,
            channel_id=channel_id,
        )

        return session_id

    async def get_session(self, session_id: str) -> SessionData | None:
        """Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            SessionData if found and not expired, None otherwise
        """
        # Check cache first
        if session_id in self._cache:
            session = self._cache[session_id]
            if session.is_expired:
                del self._cache[session_id]
                return None
            # Refresh last activity
            session.last_activity = datetime.utcnow()
            return session

        # Load from database
        session = await self._store.get(session_id)

        if session is None:
            return None

        if session.is_expired:
            await self._store.delete(session_id)
            return None

        # Cache for next time
        self._cache[session_id] = session
        return session

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        if session_id in self._cache:
            del self._cache[session_id]

        return await self._store.delete(session_id)

    async def update_context(
        self,
        session_id: str,
        message: str,
        role: str = "user",
    ) -> bool:
        """Add a message to session context.

        Args:
            session_id: Session identifier
            message: Message content
            role: Message role ('user' or 'assistant')

        Returns:
            True if updated, False if session not found
        """
        session = await self.get_session(session_id)
        if session is None:
            return False

        session.add_to_context(message, role)
        await self._store.save(session)

        return True

    async def get_user_sessions(
        self,
        user_id: str,
        channel_id: str | None = None,
    ) -> list[SessionData]:
        """Get all sessions for a user.

        Args:
            user_id: User identifier
            channel_id: Optional channel filter

        Returns:
            List of SessionData
        """
        return await self._store.get_by_user(user_id, channel_id)

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions.

        Returns:
            Number of sessions deleted
        """
        # Clear expired from cache
        expired_ids = [sid for sid, s in self._cache.items() if s.is_expired]
        for sid in expired_ids:
            del self._cache[sid]

        return await self._store.delete_expired()

    async def get_stats(self) -> dict[str, Any]:
        """Get session statistics."""
        total = await self._store.count()
        active = await self._store.count_active()

        return {
            "total_sessions": total,
            "active_sessions": active,
            "expired_sessions": total - active,
            "cached_sessions": len(self._cache),
        }


# Global session manager instance
_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """Get or create global session manager."""
    global _manager
    if _manager is None:
        _manager = SessionManager()
    return _manager


async def start_session_manager(
    db_path: str | Path = "data/db/sessions.db",
    default_ttl: int = 3600,
    cleanup_interval: int = 300,
) -> SessionManager:
    """Start the global session manager."""
    global _manager
    _manager = SessionManager(db_path, default_ttl, cleanup_interval)
    await _manager.start()
    return _manager


async def stop_session_manager() -> None:
    """Stop the global session manager."""
    global _manager
    if _manager:
        await _manager.stop()
        _manager = None


async def create_session(
    user_id: str,
    channel_id: str,
    ttl_seconds: int | None = None,
) -> str:
    """Create a new session using global manager."""
    manager = get_session_manager()
    return await manager.create_session(user_id, channel_id, ttl_seconds)


async def get_session(session_id: str) -> SessionData | None:
    """Get session using global manager."""
    manager = get_session_manager()
    return await manager.get_session(session_id)


async def update_session_context(
    session_id: str,
    message: str,
    role: str = "user",
) -> bool:
    """Update session context using global manager."""
    manager = get_session_manager()
    return await manager.update_context(session_id, message, role)
