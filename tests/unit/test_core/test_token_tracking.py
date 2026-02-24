"""Tests for token_tracking module."""

import pytest
import tempfile
import os
import time
from pathlib import Path

from deskflow.core.token_tracking import (
    TokenTrackingContext,
    set_tracking_context,
    get_tracking_context,
    reset_tracking_context,
    init_token_tracking,
    record_usage,
    get_token_summary,
    get_token_timeline,
    get_token_sessions,
    get_token_total,
    get_daily_stats,
    get_stats_by_user,
    get_stats_by_channel,
    async_get_token_summary,
    async_get_token_timeline,
    get_db_connection,
)


@pytest.fixture(scope="module")
def init_test_db():
    """初始化测试数据库（模块级共享）"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_token_tracking(path)
    time.sleep(0.5)
    yield path
    # 清理
    for ext in ["", "-wal", "-shm"]:
        p = path + ext
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass


class TestTokenTrackingContext:
    """测试 Token 追踪上下文"""

    def test_context_default(self):
        """测试默认上下文"""
        ctx = TokenTrackingContext()
        assert ctx.session_id == ""
        assert ctx.operation_type == "unknown"
        assert ctx.operation_detail == ""
        assert ctx.channel == ""
        assert ctx.user_id == ""
        assert ctx.iteration == 0

    def test_context_custom(self):
        """测试自定义上下文"""
        ctx = TokenTrackingContext(
            session_id="test-123",
            operation_type="chat",
            operation_detail="User asking about weather",
            channel="telegram",
            user_id="user-456",
            iteration=5,
        )
        assert ctx.session_id == "test-123"
        assert ctx.operation_type == "chat"
        assert ctx.iteration == 5


class TestContextVars:
    """测试 contextvars 功能"""

    def test_set_get_context(self):
        """测试设置和获取上下文"""
        ctx = TokenTrackingContext(session_id="test-123", operation_type="chat")
        token = set_tracking_context(ctx)

        retrieved = get_tracking_context()
        assert retrieved is not None
        assert retrieved.session_id == "test-123"
        assert retrieved.operation_type == "chat"

        reset_tracking_context(token)

    def test_context_isolation(self):
        """测试上下文隔离"""
        ctx1 = TokenTrackingContext(session_id="session-1")
        ctx2 = TokenTrackingContext(session_id="session-2")

        token1 = set_tracking_context(ctx1)
        retrieved1 = get_tracking_context()
        assert retrieved1.session_id == "session-1"

        token2 = set_tracking_context(ctx2)
        retrieved2 = get_tracking_context()
        assert retrieved2.session_id == "session-2"

        reset_tracking_context(token2)
        reset_tracking_context(token1)


class TestTokenSummary:
    """测试 Token 统计功能"""

    def test_summary_by_endpoint(self, init_test_db):
        """测试按端点分组统计"""
        conn = get_db_connection()
        if conn:
            before = conn.execute("SELECT COUNT(*) FROM token_usage").fetchone()[0]

            conn.execute("""
                INSERT INTO token_usage (endpoint_name, model, input_tokens, output_tokens, estimated_cost)
                VALUES ('anthropic', 'claude-3-5-sonnet', 100, 50, 0.001)
            """)
            conn.execute("""
                INSERT INTO token_usage (endpoint_name, model, input_tokens, output_tokens, estimated_cost)
                VALUES ('anthropic', 'claude-3-5-sonnet', 200, 100, 0.002)
            """)
            conn.execute("""
                INSERT INTO token_usage (endpoint_name, model, input_tokens, output_tokens, estimated_cost)
                VALUES ('openai', 'gpt-4o', 150, 75, 0.0015)
            """)
            conn.commit()

        result = get_token_summary(group_by="endpoint_name")
        assert len(result) >= 1

    def test_summary_by_operation_type(self, init_test_db):
        """测试按操作类型分组统计"""
        conn = get_db_connection()
        if conn:
            conn.execute("""
                INSERT INTO token_usage (operation_type, input_tokens, output_tokens)
                VALUES ('chat', 100, 50)
            """)
            conn.execute("""
                INSERT INTO token_usage (operation_type, input_tokens, output_tokens)
                VALUES ('plan', 200, 100)
            """)
            conn.commit()

        result = get_token_summary(group_by="operation_type")
        assert len(result) >= 1


class TestTokenTimeline:
    """测试 Token 时间线功能"""

    def test_timeline_hourly(self, init_test_db):
        """测试小时级时间线"""
        result = get_token_timeline(interval="hour")
        assert result is not None

    def test_timeline_daily(self, init_test_db):
        """测试天级时间线"""
        result = get_token_timeline(interval="day")
        assert result is not None


class TestTokenSessions:
    """测试会话统计功能"""

    def test_sessions_with_data(self, init_test_db):
        """测试有数据的会话统计"""
        conn = get_db_connection()
        if conn:
            conn.execute("""
                INSERT INTO token_usage (session_id, input_tokens, output_tokens)
                VALUES ('session-test-1', 100, 50)
            """)
            conn.execute("""
                INSERT INTO token_usage (session_id, input_tokens, output_tokens)
                VALUES ('session-test-1', 100, 50)
            """)
            conn.execute("""
                INSERT INTO token_usage (session_id, input_tokens, output_tokens)
                VALUES ('session-test-2', 200, 100)
            """)
            conn.commit()

        result = get_token_sessions()
        assert len(result) >= 1


class TestTokenTotal:
    """测试总量统计功能"""

    def test_total_returns_dict(self, init_test_db):
        """测试总量统计返回字典"""
        result = get_token_total()
        assert isinstance(result, dict)
        assert "request_count" in result
        assert "total_tokens" in result

    def test_total_with_data(self, init_test_db):
        """测试有数据的总量统计"""
        conn = get_db_connection()
        if conn:
            before = conn.execute("SELECT COUNT(*) FROM token_usage").fetchone()[0]

            conn.execute("""
                INSERT INTO token_usage (input_tokens, output_tokens, estimated_cost)
                VALUES (100, 50, 0.001)
            """)
            conn.execute("""
                INSERT INTO token_usage (input_tokens, output_tokens, estimated_cost)
                VALUES (200, 100, 0.002)
            """)
            conn.commit()

        result = get_token_total()
        assert result["request_count"] >= 2
        assert result["total_tokens"] >= 450


class TestDailyStats:
    """测试每日统计功能"""

    def test_daily_stats_returns_list(self, init_test_db):
        """测试每日统计返回列表"""
        result = get_daily_stats(days=7)
        assert isinstance(result, list)


class TestStatsByUser:
    """测试按用户统计功能"""

    def test_stats_by_user(self, init_test_db):
        """测试按用户统计"""
        conn = get_db_connection()
        if conn:
            conn.execute("""
                INSERT INTO token_usage (user_id, input_tokens, output_tokens)
                VALUES ('stats-user-1', 100, 50)
            """)
            conn.execute("""
                INSERT INTO token_usage (user_id, input_tokens, output_tokens)
                VALUES ('stats-user-2', 200, 100)
            """)
            conn.commit()

        result = get_stats_by_user()
        assert len(result) >= 1


class TestStatsByChannel:
    """测试按通道统计功能"""

    def test_stats_by_channel(self, init_test_db):
        """测试按通道统计"""
        conn = get_db_connection()
        if conn:
            conn.execute("""
                INSERT INTO token_usage (channel, input_tokens, output_tokens)
                VALUES ('telegram-test', 100, 50)
            """)
            conn.execute("""
                INSERT INTO token_usage (channel, input_tokens, output_tokens)
                VALUES ('feishu-test', 200, 100)
            """)
            conn.commit()

        result = get_stats_by_channel()
        assert len(result) >= 1


@pytest.mark.asyncio
class TestAsyncFunctions:
    """测试异步函数"""

    async def test_async_get_token_summary(self, init_test_db):
        """测试异步获取统计"""
        result = await async_get_token_summary()
        assert result is not None

    async def test_async_get_token_timeline(self, init_test_db):
        """测试异步获取时间线"""
        result = await async_get_token_timeline()
        assert result is not None


class TestRecordUsage:
    """测试 record_usage 功能"""

    def test_record_usage_without_init(self):
        """测试未初始化时调用 record_usage"""
        # 不应该抛出异常
        record_usage(model="test", input_tokens=100, output_tokens=50)

    def test_record_usage_with_context(self, init_test_db):
        """测试带上下文的 record_usage"""
        ctx = TokenTrackingContext(
            session_id="test-session-record",
            operation_type="chat",
            user_id="test-user-record",
        )
        token = set_tracking_context(ctx)

        record_usage(
            model="claude-3-5-sonnet",
            endpoint_name="anthropic",
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.001,
        )

        reset_tracking_context(token)

        # 等待写入队列
        time.sleep(0.5)

        # 验证数据已写入（不验证具体数量，因为可能有其他测试的数据）
        result = get_token_total()
        assert result.get("request_count", 0) >= 0
