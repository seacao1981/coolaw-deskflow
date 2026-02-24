"""Tests for session management module."""

import pytest
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone

from deskflow.channels.session import (
    SessionData,
    SessionStore,
    SessionManager,
    get_session_manager,
    start_session_manager,
    stop_session_manager,
    create_session,
    get_session,
    update_session_context,
)


# Helper to get current UTC time (replaces deprecated utcnow())
def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TestSessionData:
    """Test SessionData class."""

    def test_session_creation(self):
        """Test basic session creation."""
        session = SessionData(
            session_id="test_123",
            user_id="user_456",
            channel_id="feishu",
            created_at=utc_now(),
            last_activity=utc_now(),
        )

        assert session.session_id == "test_123"
        assert session.user_id == "user_456"
        assert session.channel_id == "feishu"
        assert session.ttl_seconds == 3600
        assert session.is_expired is False

    def test_session_is_expired(self):
        """Test session expiry check."""
        # Create session with 1 second TTL
        session = SessionData(
            session_id="test_123",
            user_id="user_456",
            channel_id="feishu",
            created_at=utc_now(),
            last_activity=utc_now() - timedelta(seconds=10),
            ttl_seconds=5,  # Expired 5 seconds ago
        )

        assert session.is_expired is True

    def test_session_remaining_ttl(self):
        """Test remaining TTL calculation."""
        # Create session with 1 hour TTL, just created
        session = SessionData(
            session_id="test_123",
            user_id="user_456",
            channel_id="feishu",
            created_at=utc_now(),
            last_activity=utc_now(),
            ttl_seconds=3600,
        )

        # Should have close to 3600 seconds remaining
        remaining = session.remaining_ttl
        assert 3590 <= remaining <= 3600

    def test_session_to_dict(self):
        """Test session to_dict method."""
        session = SessionData(
            session_id="test_123",
            user_id="user_456",
            channel_id="feishu",
            created_at=datetime(2024, 1, 1, 12, 0, 0),
            last_activity=datetime(2024, 1, 1, 12, 30, 0),
            ttl_seconds=3600,
        )

        result = session.to_dict()

        assert result["session_id"] == "test_123"
        assert result["user_id"] == "user_456"
        assert result["channel_id"] == "feishu"
        assert result["ttl_seconds"] == 3600
        assert "is_expired" in result
        assert "remaining_ttl" in result

    def test_add_to_context(self):
        """Test adding message to context."""
        session = SessionData(
            session_id="test_123",
            user_id="user_456",
            channel_id="feishu",
            created_at=utc_now(),
            last_activity=utc_now(),
        )

        session.add_to_context("Hello!", role="user")

        assert len(session.context) == 1
        assert session.context[0]["content"] == "Hello!"
        assert session.context[0]["role"] == "user"

    def test_clear_context(self):
        """Test clearing context."""
        session = SessionData(
            session_id="test_123",
            user_id="user_456",
            channel_id="feishu",
            created_at=utc_now(),
            last_activity=utc_now(),
        )

        session.add_to_context("Message 1")
        session.add_to_context("Message 2")
        session.clear_context()

        assert len(session.context) == 0


class TestSessionStore:
    """Test SessionStore class."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_store_creation(self, temp_db):
        """Test store initialization."""
        store = SessionStore(temp_db)
        # Should create table without error
        assert Path(temp_db).exists()

    @pytest.mark.asyncio
    async def test_save_and_get(self, temp_db):
        """Test saving and retrieving session."""
        store = SessionStore(temp_db)

        session = SessionData(
            session_id="test_save",
            user_id="user_123",
            channel_id="feishu",
            created_at=utc_now(),
            last_activity=utc_now(),
        )

        await store.save(session)
        retrieved = await store.get("test_save")

        assert retrieved is not None
        assert retrieved.session_id == "test_save"
        assert retrieved.user_id == "user_123"

    @pytest.mark.asyncio
    async def test_get_not_found(self, temp_db):
        """Test getting non-existent session."""
        store = SessionStore(temp_db)
        result = await store.get("non_existent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, temp_db):
        """Test deleting session."""
        store = SessionStore(temp_db)

        session = SessionData(
            session_id="test_delete",
            user_id="user_123",
            channel_id="feishu",
            created_at=utc_now(),
            last_activity=utc_now(),
        )

        await store.save(session)
        deleted = await store.delete("test_delete")

        assert deleted is True

        # Verify deleted
        result = await store.get("test_delete")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_user(self, temp_db):
        """Test getting sessions by user ID."""
        store = SessionStore(temp_db)

        # Create multiple sessions for same user
        for i in range(3):
            session = SessionData(
                session_id=f"session_{i}",
                user_id="user_123",
                channel_id="feishu",
                created_at=datetime.now(),
                last_activity=datetime.now(),
            )
            await store.save(session)

        sessions = await store.get_by_user("user_123")
        assert len(sessions) == 3

    @pytest.mark.asyncio
    async def test_count(self, temp_db):
        """Test session count."""
        store = SessionStore(temp_db)

        await store.save(SessionData(
            session_id="s1", user_id="u1", channel_id="c1",
            created_at=datetime.now(), last_activity=datetime.now(),
        ))

        count = await store.count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_delete_expired(self, temp_db):
        """Test deleting expired sessions."""
        # Use a unique db file for this test
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            unique_db = f.name

        try:
            store = SessionStore(unique_db)

            # Create expired session
            expired = SessionData(
                session_id="expired_1",
                user_id="user_expired",
                channel_id="feishu",
                created_at=utc_now() - timedelta(hours=2),
                last_activity=utc_now() - timedelta(hours=2),
                ttl_seconds=300,  # 5 minutes
            )
            await store.save(expired)

            # Create valid session
            valid = SessionData(
                session_id="valid_1",
                user_id="user_valid",
                channel_id="feishu",
                created_at=utc_now(),
                last_activity=utc_now(),
                ttl_seconds=3600,
            )
            await store.save(valid)

            # Verify both exist before deletion
            assert await store.get("expired_1") is not None
            assert await store.get("valid_1") is not None

            deleted = await store.delete_expired()

            assert deleted >= 1  # At least the expired one

            # Verify expired is deleted
            assert await store.get("expired_1") is None

            # Valid session should still exist
            remaining = await store.get("valid_1")
            assert remaining is not None, f"Valid session was deleted! DB: {unique_db}"
        finally:
            Path(unique_db).unlink(missing_ok=True)


class TestSessionManager:
    """Test SessionManager class."""

    @pytest.fixture
    def temp_manager(self):
        """Create temporary session manager."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        manager = SessionManager(db_path=db_path, default_ttl=3600, cleanup_interval=60)
        yield manager
        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_manager_creation(self, temp_manager):
        """Test manager creation."""
        assert temp_manager._default_ttl == 3600
        assert temp_manager._cleanup_interval == 60

    @pytest.mark.asyncio
    async def test_create_session(self, temp_manager):
        """Test creating session."""
        session_id = await temp_manager.create_session(
            user_id="user_123",
            channel_id="feishu",
        )

        assert session_id is not None
        assert len(session_id) == 32  # UUID hex

    @pytest.mark.asyncio
    async def test_get_session(self, temp_manager):
        """Test getting session."""
        session_id = await temp_manager.create_session(
            user_id="user_123",
            channel_id="feishu",
        )

        session = await temp_manager.get_session(session_id)

        assert session is not None
        assert session.user_id == "user_123"

    @pytest.mark.asyncio
    async def test_delete_session(self, temp_manager):
        """Test deleting session."""
        session_id = await temp_manager.create_session(
            user_id="user_123",
            channel_id="feishu",
        )

        deleted = await temp_manager.delete_session(session_id)
        assert deleted is True

        # Verify deleted
        session = await temp_manager.get_session(session_id)
        assert session is None

    @pytest.mark.asyncio
    async def test_update_context(self, temp_manager):
        """Test updating session context."""
        session_id = await temp_manager.create_session(
            user_id="user_123",
            channel_id="feishu",
        )

        success = await temp_manager.update_context(
            session_id, "Hello!", role="user"
        )
        assert success is True

        session = await temp_manager.get_session(session_id)
        assert len(session.context) == 1
        assert session.context[0]["content"] == "Hello!"

    @pytest.mark.asyncio
    async def test_get_user_sessions(self, temp_manager):
        """Test getting user sessions."""
        # Create multiple sessions
        for i in range(3):
            await temp_manager.create_session(
                user_id="user_123",
                channel_id="feishu",
            )

        sessions = await temp_manager.get_user_sessions("user_123")
        assert len(sessions) == 3

    @pytest.mark.asyncio
    async def test_get_stats(self, temp_manager):
        """Test getting session statistics."""
        await temp_manager.create_session(
            user_id="user_123",
            channel_id="feishu",
        )

        stats = await temp_manager.get_stats()

        assert "total_sessions" in stats
        assert "active_sessions" in stats
        assert "cached_sessions" in stats

    @pytest.mark.asyncio
    async def test_start_stop(self, temp_manager):
        """Test manager start and stop."""
        await temp_manager.start()
        assert temp_manager._running is True

        await temp_manager.stop()
        assert temp_manager._running is False


class TestGlobalFunctions:
    """Test global convenience functions."""

    def test_get_session_manager(self):
        """Test get_session_manager returns singleton."""
        manager1 = get_session_manager()
        manager2 = get_session_manager()

        # Should return same instance
        assert manager1 is manager2

    @pytest.mark.asyncio
    async def test_start_stop_session_manager(self):
        """Test start_session_manager and stop_session_manager."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            manager = await start_session_manager(db_path=db_path)
            assert manager._running is True

            await stop_session_manager()
        finally:
            Path(db_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_create_and_get_session(self):
        """Test create_session and get_session functions."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            await start_session_manager(db_path=db_path)

            session_id = await create_session(
                user_id="test_user",
                channel_id="test_channel",
            )

            session = await get_session(session_id)
            assert session is not None
            assert session.user_id == "test_user"

            await stop_session_manager()
        finally:
            Path(db_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_update_session_context(self):
        """Test update_session_context function."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            await start_session_manager(db_path=db_path)

            session_id = await create_session(
                user_id="test_user",
                channel_id="test_channel",
            )

            success = await update_session_context(
                session_id, "Test message", role="user"
            )
            assert success is True

            await stop_session_manager()
        finally:
            Path(db_path).unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
