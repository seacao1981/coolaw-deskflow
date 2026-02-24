"""SQLite storage backend for DeskFlow memory system.

Uses aiosqlite for async operations and FTS5 for full-text search.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import aiosqlite

from deskflow.core.models import MemoryEntry, Message, Role
from deskflow.errors import MemoryStorageError
from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

SCHEMA_VERSION = 1

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL DEFAULT 'episodic',
    importance REAL NOT NULL DEFAULT 0.5,
    embedding TEXT,
    tags TEXT NOT NULL DEFAULT '[]',
    source_conversation_id TEXT,
    created_at REAL NOT NULL,
    last_accessed REAL NOT NULL,
    access_count INTEGER NOT NULL DEFAULT 0,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_conversation ON memories(source_conversation_id);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content,
    tags,
    content='memories',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content, tags)
    VALUES (new.rowid, new.content, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, tags)
    VALUES ('delete', old.rowid, old.content, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, tags)
    VALUES ('delete', old.rowid, old.content, old.tags);
    INSERT INTO memories_fts(rowid, content, tags)
    VALUES (new.rowid, new.content, new.tags);
END;

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp REAL NOT NULL,
    tool_calls TEXT NOT NULL DEFAULT '[]',
    tool_call_id TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, timestamp);
"""


class MemoryStorage:
    """Async SQLite storage for memories with FTS5 full-text search."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open the database connection and create tables."""
        try:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            self._db = await aiosqlite.connect(self._db_path)
            self._db.row_factory = aiosqlite.Row
            await self._db.executescript(CREATE_TABLES_SQL)
            await self._db.execute(
                "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            await self._db.commit()
            logger.info("memory_storage_initialized", db_path=self._db_path)
        except Exception as e:
            raise MemoryStorageError(f"Failed to initialize database: {e}") from e

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    def _ensure_connected(self) -> aiosqlite.Connection:
        """Ensure database is connected."""
        if not self._db:
            raise MemoryStorageError("Database not initialized. Call initialize() first.")
        return self._db

    # ========== Conversation History Methods ==========

    async def save_conversation(
        self,
        conversation_id: str,
        messages: list[Message],
        title: str | None = None,
    ) -> None:
        """Save or update a conversation with all its messages.

        Args:
            conversation_id: The conversation ID
            messages: List of messages in the conversation
            title: Optional conversation title
        """
        db = self._ensure_connected()
        now = time.time()

        # Upsert conversation
        await db.execute(
            """INSERT INTO conversations (id, title, created_at, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
               title = COALESCE(?, title),
               updated_at = ?""",
            (conversation_id, title, now, now, title, now),
        )

        # Clear existing messages and re-insert
        await db.execute(
            "DELETE FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        )

        for msg in messages:
            await db.execute(
                """INSERT INTO messages
                   (id, conversation_id, role, content, timestamp, tool_calls, tool_call_id, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    msg.id,
                    conversation_id,
                    msg.role.value,
                    msg.content,
                    msg.timestamp,
                    json.dumps([tc.model_dump() for tc in msg.tool_calls]),
                    msg.tool_call_id,
                    json.dumps(msg.metadata),
                ),
            )

        await db.commit()
        logger.debug("conversation_saved", conversation_id=conversation_id, message_count=len(messages))

    async def load_conversation(self, conversation_id: str) -> list[Message] | None:
        """Load all messages from a conversation.

        Args:
            conversation_id: The conversation ID to load

        Returns:
            List of messages ordered by timestamp, or None if conversation not found
        """
        db = self._ensure_connected()

        # Check if conversation exists
        cursor = await db.execute(
            "SELECT id FROM conversations WHERE id = ?", (conversation_id,)
        )
        if not await cursor.fetchone():
            return None

        # Load messages
        cursor = await db.execute(
            """SELECT id, role, content, timestamp, tool_calls, tool_call_id, metadata
               FROM messages
               WHERE conversation_id = ?
               ORDER BY timestamp ASC""",
            (conversation_id,),
        )

        rows = await cursor.fetchall()
        messages: list[Message] = []

        for row in rows:
            tool_calls = []
            if row["tool_calls"]:
                from deskflow.core.models import ToolCall, ToolCallStatus
                tool_calls_data = json.loads(row["tool_calls"])
                for tc_data in tool_calls_data:
                    tool_calls.append(ToolCall(**tc_data))

            metadata = json.loads(row["metadata"]) if row["metadata"] else {}

            msg = Message(
                id=row["id"],
                role=Role(row["role"]),
                content=row["content"],
                timestamp=row["timestamp"],
                tool_calls=tool_calls,
                tool_call_id=row["tool_call_id"],
                metadata=metadata,
            )
            messages.append(msg)

        logger.debug("conversation_loaded", conversation_id=conversation_id, message_count=len(messages))
        return messages if messages else None

    async def get_conversation_ids(self, limit: int = 50) -> list[str]:
        """Get list of recent conversation IDs.

        Args:
            limit: Maximum number of IDs to return

        Returns:
            List of conversation IDs ordered by updated_at descending
        """
        db = self._ensure_connected()
        cursor = await db.execute(
            """SELECT id FROM conversations
               ORDER BY updated_at DESC
               LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [row["id"] for row in rows]

    # ========== Memory Methods ==========

    async def store_memory(self, entry: MemoryEntry) -> str:
        """Store a memory entry.

        Returns:
            The memory ID.
        """
        db = self._ensure_connected()
        try:
            await db.execute(
                """INSERT INTO memories
                   (id, content, memory_type, importance, embedding, tags,
                    source_conversation_id, created_at, last_accessed,
                    access_count, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.id,
                    entry.content,
                    entry.memory_type,
                    entry.importance,
                    json.dumps(entry.embedding) if entry.embedding else None,
                    json.dumps(entry.tags),
                    entry.source_conversation_id,
                    entry.created_at,
                    entry.last_accessed,
                    entry.access_count,
                    json.dumps(entry.metadata),
                ),
            )
            await db.commit()
            logger.debug("memory_stored", memory_id=entry.id, type=entry.memory_type)
            return entry.id
        except Exception as e:
            raise MemoryStorageError(f"Failed to store memory: {e}") from e

    async def get_by_id(self, memory_id: str) -> MemoryEntry | None:
        """Get a memory by ID."""
        db = self._ensure_connected()
        cursor = await db.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_entry(row)

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID. Returns True if deleted."""
        db = self._ensure_connected()
        cursor = await db.execute(
            "DELETE FROM memories WHERE id = ?", (memory_id,)
        )
        await db.commit()
        return cursor.rowcount > 0

    async def search_fts(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Full-text search using FTS5.

        Falls back to LIKE search if FTS returns no results (e.g., for Chinese queries).

        Args:
            query: Search query string.
            limit: Maximum results.

        Returns:
            Matching memory entries.
        """
        db = self._ensure_connected()
        # Escape special FTS5 characters
        safe_query = query.replace('"', '""')
        try:
            cursor = await db.execute(
                """SELECT m.*, rank
                   FROM memories_fts fts
                   JOIN memories m ON m.rowid = fts.rowid
                   WHERE memories_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (f'"{safe_query}"', limit),
            )
            rows = await cursor.fetchall()
            entries = [self._row_to_entry(row) for row in rows]

            # Fall back to LIKE search if FTS returns no results
            # This handles Chinese queries which FTS5 doesn't tokenize well
            if not entries:
                logger.debug("fts_no_results", query=query, reason="falling_back_to_like_search")
                return await self.search_like(query, limit)

            # Update access timestamps
            for entry in entries:
                await self._touch_memory(entry.id)
            return entries
        except Exception as e:
            logger.warning("fts_search_failed", query=query, error=str(e))
            # Fall back to LIKE search
            return await self.search_like(query, limit)

    async def search_like(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Fallback search using LIKE.

        For Chinese queries, splits into 2-character chunks for better matching.
        For English queries, splits by whitespace.
        Uses OR logic - any term can match.

        Args:
            query: Search query string.
            limit: Maximum results.

        Returns:
            Matching memory entries.
        """
        db = self._ensure_connected()

        # Split query into terms
        # For Chinese: split into 2-char chunks for better matching
        # For English: split by whitespace
        terms = []
        if any('\u4e00' <= c <= '\u9fff' for c in query):
            # Chinese query: split into 2-char chunks
            for i in range(0, len(query) - 1, 2):
                terms.append(query[i:i+2])
            # Also add the full query if it's short
            if len(query) <= 4 and query not in terms:
                terms.append(query)
        else:
            # English query: split by whitespace
            terms = query.split()

        if not terms:
            return []

        # Build SQL with OR conditions (any term can match)
        conditions = " OR ".join([f"content LIKE ?" for _ in terms])
        params = [f"%{term}%" for term in terms] + [limit]

        cursor = await db.execute(
            f"""SELECT * FROM memories
               WHERE {conditions}
               ORDER BY importance DESC, created_at DESC
               LIMIT ?""",
            params,
        )
        rows = await cursor.fetchall()
        return [self._row_to_entry(row) for row in rows]

    async def get_recent(self, limit: int = 20, since: float | None = None) -> list[MemoryEntry]:
        """Get the most recent memories.

        Args:
            limit: Maximum number of memories to retrieve
            since: Optional timestamp to filter memories (only return newer)

        Returns:
            List of recent memory entries
        """
        db = self._ensure_connected()
        if since:
            cursor = await db.execute(
                "SELECT * FROM memories WHERE created_at >= ? ORDER BY created_at DESC LIMIT ?",
                (since, limit),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [self._row_to_entry(row) for row in rows]

    async def count(self) -> int:
        """Return total memory count."""
        db = self._ensure_connected()
        cursor = await db.execute("SELECT COUNT(*) FROM memories")
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def _touch_memory(self, memory_id: str) -> None:
        """Update last_accessed timestamp and increment access count."""
        db = self._ensure_connected()
        await db.execute(
            """UPDATE memories
               SET last_accessed = ?, access_count = access_count + 1
               WHERE id = ?""",
            (time.time(), memory_id),
        )
        await db.commit()

    @staticmethod
    def _row_to_entry(row: Any) -> MemoryEntry:
        """Convert a database row to a MemoryEntry."""
        embedding = None
        if row["embedding"]:
            embedding = json.loads(row["embedding"])

        tags = json.loads(row["tags"]) if row["tags"] else []
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}

        return MemoryEntry(
            id=row["id"],
            content=row["content"],
            memory_type=row["memory_type"],
            importance=row["importance"],
            embedding=embedding,
            tags=tags,
            source_conversation_id=row["source_conversation_id"],
            created_at=row["created_at"],
            last_accessed=row["last_accessed"],
            access_count=row["access_count"],
            metadata=metadata,
        )
