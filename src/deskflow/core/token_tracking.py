"""
Token 追踪增强：按端点分组统计、时间线查询、会话级统计。

在原有 contextvars + 后台写入线程基础上新增：
- 按端点分组统计
- 按操作类型分组统计
- 时间线统计（按小时/天/周/月）
- 会话级统计
- 总用量统计
- 上下文大小查询
"""

from __future__ import annotations

import contextvars
import logging
import queue
import sqlite3
import threading
import asyncio
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────── contextvars ────────────────────────


@dataclass
class TokenTrackingContext:
    """Token 追踪上下文"""

    session_id: str = ""
    operation_type: str = "unknown"
    operation_detail: str = ""
    channel: str = ""
    user_id: str = ""
    iteration: int = 0


_tracking_ctx: contextvars.ContextVar[TokenTrackingContext | None] = contextvars.ContextVar(
    "token_tracking_ctx", default=None
)


def set_tracking_context(ctx: TokenTrackingContext) -> contextvars.Token:
    """设置 Token 追踪上下文"""
    return _tracking_ctx.set(ctx)


def get_tracking_context() -> TokenTrackingContext | None:
    """获取 Token 追踪上下文"""
    return _tracking_ctx.get()


def reset_tracking_context(token: contextvars.Token) -> None:
    """重置 Token 追踪上下文"""
    _tracking_ctx.reset(token)


# ──────────────────────── 写入队列 & 后台线程 ────────────────────────

_write_queue: queue.Queue = queue.Queue()
_initialized = False
_db_conn: sqlite3.Connection | None = None


def init_token_tracking(db_path: str) -> None:
    """启动后台写入线程。在应用启动时调用一次。"""
    global _initialized, _db_conn
    if _initialized:
        return

    # 初始化数据库连接
    _db_conn = _init_database(str(db_path))

    _initialized = True
    t = threading.Thread(
        target=_writer_loop,
        args=(str(db_path),),
        daemon=True,
        name="token-usage-writer",
    )
    t.start()
    logger.info(f"[TokenTracking] Background writer started (db={db_path})")


def _init_database(db_path: str) -> sqlite3.Connection:
    """初始化数据库表结构"""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            session_id TEXT,
            endpoint_name TEXT,
            model TEXT,
            operation_type TEXT,
            operation_detail TEXT,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cache_creation_tokens INTEGER DEFAULT 0,
            cache_read_tokens INTEGER DEFAULT 0,
            context_tokens INTEGER DEFAULT 0,
            iteration INTEGER DEFAULT 0,
            channel TEXT,
            user_id TEXT,
            estimated_cost REAL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_token_timestamp ON token_usage(timestamp);
        CREATE INDEX IF NOT EXISTS idx_token_session ON token_usage(session_id);
        CREATE INDEX IF NOT EXISTS idx_token_endpoint ON token_usage(endpoint_name);
        CREATE INDEX IF NOT EXISTS idx_token_model ON token_usage(model);
        CREATE INDEX IF NOT EXISTS idx_token_operation ON token_usage(operation_type);
        CREATE INDEX IF NOT EXISTS idx_token_user ON token_usage(user_id);
        CREATE INDEX IF NOT EXISTS idx_token_channel ON token_usage(channel);
    """)
    conn.commit()
    return conn


def record_usage(
    *,
    model: str = "",
    endpoint_name: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
    context_tokens: int = 0,
    estimated_cost: float = 0.0,
) -> None:
    """将一次 LLM 调用的 token 用量投递到写入队列（非阻塞）。"""
    if not _initialized:
        return

    ctx = _tracking_ctx.get()
    _write_queue.put({
        "session_id": ctx.session_id if ctx else "",
        "endpoint_name": endpoint_name,
        "model": model,
        "operation_type": ctx.operation_type if ctx else "unknown",
        "operation_detail": ctx.operation_detail if ctx else "",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_tokens": cache_creation_tokens,
        "cache_read_tokens": cache_read_tokens,
        "context_tokens": context_tokens,
        "iteration": ctx.iteration if ctx else 0,
        "channel": ctx.channel if ctx else "",
        "user_id": ctx.user_id if ctx else "",
        "estimated_cost": estimated_cost,
    })


def get_db_connection() -> sqlite3.Connection | None:
    """获取数据库连接"""
    global _db_conn
    if _db_conn is None:
        return None
    return _db_conn


# ──────────────────────── 后台写入实现 ────────────────────────

_INSERT_SQL = """
INSERT INTO token_usage (
    session_id, endpoint_name, model, operation_type, operation_detail,
    input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens,
    context_tokens, iteration, channel, user_id, estimated_cost
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _writer_loop(db_path: str) -> None:
    """后台守护线程主循环：批量写入 token_usage 记录。"""
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT,
                endpoint_name TEXT,
                model TEXT,
                operation_type TEXT,
                operation_detail TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cache_creation_tokens INTEGER DEFAULT 0,
                cache_read_tokens INTEGER DEFAULT 0,
                context_tokens INTEGER DEFAULT 0,
                iteration INTEGER DEFAULT 0,
                channel TEXT,
                user_id TEXT,
                estimated_cost REAL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_token_timestamp ON token_usage(timestamp);
            CREATE INDEX IF NOT EXISTS idx_token_session ON token_usage(session_id);
            CREATE INDEX IF NOT EXISTS idx_token_endpoint ON token_usage(endpoint_name);
            CREATE INDEX IF NOT EXISTS idx_token_model ON token_usage(model);
            CREATE INDEX IF NOT EXISTS idx_token_operation ON token_usage(operation_type);
            CREATE INDEX IF NOT EXISTS idx_token_user ON token_usage(user_id);
            CREATE INDEX IF NOT EXISTS idx_token_channel ON token_usage(channel);
        """)
        conn.commit()
    except Exception as e:
        logger.error(f"[TokenTracking] Database init failed: {e}")
        return

    batch = []
    batch_size = 100
    last_flush = 0

    while True:
        try:
            # 等待新数据
            try:
                item = _write_queue.get(timeout=1)
                batch.append(item)
            except queue.Empty:
                # 超时，检查是否需要 flush
                if batch and (datetime.now().timestamp() - last_flush) > 5:
                    _flush_batch(conn, batch)
                    batch = []
                    last_flush = datetime.now().timestamp()
                continue

            # 批量写入
            if len(batch) >= batch_size:
                _flush_batch(conn, batch)
                batch = []
                last_flush = datetime.now().timestamp()

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"[TokenTracking] Writer loop error: {e}")

    # Flush remaining
    if batch:
        _flush_batch(conn, batch)


def _flush_batch(conn: sqlite3.Connection, batch: list[dict]) -> None:
    """批量写入数据"""
    try:
        conn.executemany(_INSERT_SQL, [
            (
                item["session_id"],
                item["endpoint_name"],
                item["model"],
                item["operation_type"],
                item["operation_detail"],
                item["input_tokens"],
                item["output_tokens"],
                item["cache_creation_tokens"],
                item["cache_read_tokens"],
                item["context_tokens"],
                item["iteration"],
                item["channel"],
                item["user_id"],
                item["estimated_cost"],
            )
            for item in batch
        ])
        conn.commit()
        logger.debug(f"[TokenTracking] Flushed {len(batch)} records")
    except Exception as e:
        logger.error(f"[TokenTracking] Batch flush failed: {e}")


# ──────────────────────── 统计查询函数 ────────────────────────


def get_token_summary(
    group_by: str = "endpoint_name",
    start_time: str | None = None,
    end_time: str | None = None,
    endpoint_name: str | None = None,
    operation_type: str | None = None,
) -> list[dict[str, Any]]:
    """
    按维度聚合 Token 用量统计

    Args:
        group_by: 分组维度 (endpoint_name / operation_type / model / user_id / channel)
        start_time: 开始时间 (ISO 格式)
        end_time: 结束时间 (ISO 格式)
        endpoint_name: 按端点过滤
        operation_type: 按操作类型过滤

    Returns:
        按指定维度分组的统计结果
    """
    conn = get_db_connection()
    if not conn:
        return []

    # 验证分组字段
    valid_columns = ["endpoint_name", "operation_type", "model", "user_id", "channel"]
    if group_by not in valid_columns:
        group_by = "endpoint_name"

    # 构建 WHERE 子句
    conditions = []
    params: list[Any] = []

    if start_time:
        conditions.append("timestamp >= ?")
        params.append(start_time)

    if end_time:
        conditions.append("timestamp <= ?")
        params.append(end_time)

    if endpoint_name:
        conditions.append("endpoint_name = ?")
        params.append(endpoint_name)

    if operation_type:
        conditions.append("operation_type = ?")
        params.append(operation_type)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    sql = f"""
        SELECT
            {group_by} as dimension,
            COUNT(*) as request_count,
            SUM(input_tokens) as total_input_tokens,
            SUM(output_tokens) as total_output_tokens,
            SUM(input_tokens + output_tokens) as total_tokens,
            SUM(estimated_cost) as total_cost_usd,
            AVG(input_tokens + output_tokens) as avg_tokens_per_request,
            MIN(timestamp) as first_request,
            MAX(timestamp) as last_request
        FROM token_usage
        WHERE {where_clause}
        GROUP BY {group_by}
        ORDER BY total_tokens DESC
    """

    try:
        cursor = conn.execute(sql, params)
        columns = [desc[0] for desc in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        return results
    except Exception as e:
        logger.error(f"[TokenTracking] Summary query failed: {e}")
        return []


def get_token_timeline(
    interval: str = "hour",
    start_time: str | None = None,
    end_time: str | None = None,
    endpoint_name: str | None = None,
) -> list[dict[str, Any]]:
    """
    Token 用量时间线统计

    Args:
        interval: 时间间隔 (hour / day / week / month)
        start_time: 开始时间
        end_time: 结束时间
        endpoint_name: 按端点过滤

    Returns:
        时间序列统计结果
    """
    conn = get_db_connection()
    if not conn:
        return []

    # 时间间隔映射
    interval_map = {
        "hour": "%Y-%m-%d %H:00:00",
        "day": "%Y-%m-%d",
        "week": "%Y-%W",
        "month": "%Y-%m",
    }
    time_format = interval_map.get(interval, "%Y-%m-%d %H:00:00")

    # SQLite  strftime 格式
    strftime_format = {
        "hour": "%Y-%m-%d %H:00:00",
        "day": "%Y-%m-%d",
        "week": "%Y-%W",
        "month": "%Y-%m",
    }.get(interval, "%Y-%m-%d")

    conditions = []
    params: list[Any] = []

    if start_time:
        conditions.append("timestamp >= ?")
        params.append(start_time)

    if end_time:
        conditions.append("timestamp <= ?")
        params.append(end_time)

    if endpoint_name:
        conditions.append("endpoint_name = ?")
        params.append(endpoint_name)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    sql = f"""
        SELECT
            strftime('{strftime_format}', timestamp) as time_bucket,
            COUNT(*) as request_count,
            SUM(input_tokens) as total_input_tokens,
            SUM(output_tokens) as total_output_tokens,
            SUM(input_tokens + output_tokens) as total_tokens,
            SUM(estimated_cost) as total_cost_usd
        FROM token_usage
        WHERE {where_clause}
        GROUP BY time_bucket
        ORDER BY time_bucket ASC
    """

    try:
        cursor = conn.execute(sql, params)
        columns = [desc[0] for desc in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        return results
    except Exception as e:
        logger.error(f"[TokenTracking] Timeline query failed: {e}")
        return []


def get_token_sessions(
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    会话级 Token 用量统计

    Args:
        start_time: 开始时间
        end_time: 结束时间
        limit: 返回数量限制
        offset: 偏移量

    Returns:
        会话级统计结果
    """
    conn = get_db_connection()
    if not conn:
        return []

    conditions = []
    params: list[Any] = []

    if start_time:
        conditions.append("timestamp >= ?")
        params.append(start_time)

    if end_time:
        conditions.append("timestamp <= ?")
        params.append(end_time)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    sql = f"""
        SELECT
            session_id,
            COUNT(*) as request_count,
            SUM(input_tokens) as total_input_tokens,
            SUM(output_tokens) as total_output_tokens,
            SUM(input_tokens + output_tokens) as total_tokens,
            SUM(estimated_cost) as total_cost_usd,
            MIN(timestamp) as first_request,
            MAX(timestamp) as last_request,
            AVG(input_tokens + output_tokens) as avg_tokens_per_request
        FROM token_usage
        WHERE {where_clause} AND session_id != ''
        GROUP BY session_id
        ORDER BY total_tokens DESC
        LIMIT ? OFFSET ?
    """

    try:
        cursor = conn.execute(sql, params + [limit, offset])
        columns = [desc[0] for desc in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        return results
    except Exception as e:
        logger.error(f"[TokenTracking] Sessions query failed: {e}")
        return []


def get_token_total(
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    """
    Token 总用量统计

    Args:
        start_time: 开始时间
        end_time: 结束时间

    Returns:
        总用量统计
    """
    conn = get_db_connection()
    if not conn:
        return {}

    conditions = []
    params: list[Any] = []

    if start_time:
        conditions.append("timestamp >= ?")
        params.append(start_time)

    if end_time:
        conditions.append("timestamp <= ?")
        params.append(end_time)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    sql = f"""
        SELECT
            COUNT(*) as request_count,
            SUM(input_tokens) as total_input_tokens,
            SUM(output_tokens) as total_output_tokens,
            SUM(input_tokens + output_tokens) as total_tokens,
            SUM(estimated_cost) as total_cost_usd,
            AVG(input_tokens + output_tokens) as avg_tokens_per_request,
            MIN(timestamp) as first_request,
            MAX(timestamp) as last_request
        FROM token_usage
        WHERE {where_clause}
    """

    try:
        cursor = conn.execute(sql, params)
        row = cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return {}
    except Exception as e:
        logger.error(f"[TokenTracking] Total query failed: {e}")
        return {}


def get_current_context_size(session_id: str | None = None) -> dict[str, Any]:
    """
    获取当前会话的上下文 Token 大小

    Args:
        session_id: 会话 ID

    Returns:
        上下文大小信息
    """
    # 这里返回一个占位符，实际值需要从 ContextManager 获取
    return {
        "session_id": session_id or "",
        "context_tokens": 0,
        "context_limit": 124000,
        "percent": 0.0,
    }


def get_daily_stats(days: int = 7) -> list[dict[str, Any]]:
    """
    每日 Token 用量统计

    Args:
        days: 统计天数

    Returns:
        每日统计结果
    """
    end = datetime.now()
    start = end - timedelta(days=days)

    return get_token_timeline(
        interval="day",
        start_time=start.isoformat(),
        end_time=end.isoformat(),
    )


def get_stats_by_user(
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict[str, Any]]:
    """
    按用户统计 Token 用量

    Args:
        start_time: 开始时间
        end_time: 结束时间

    Returns:
        按用户分组的统计结果
    """
    return get_token_summary(
        group_by="user_id",
        start_time=start_time,
        end_time=end_time,
    )


def get_stats_by_channel(
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict[str, Any]]:
    """
    按通道统计 Token 用量

    Args:
        start_time: 开始时间
        end_time: 结束时间

    Returns:
        按通道分组的统计结果
    """
    return get_token_summary(
        group_by="channel",
        start_time=start_time,
        end_time=end_time,
    )


# ──────────────────────── 异步包装函数 ────────────────────────


async def async_get_token_summary(**kwargs: Any) -> list[dict[str, Any]]:
    """异步获取 Token 统计"""
    return await asyncio.to_thread(get_token_summary, **kwargs)


async def async_get_token_timeline(**kwargs: Any) -> list[dict[str, Any]]:
    """异步获取 Token 时间线"""
    return await asyncio.to_thread(get_token_timeline, **kwargs)


async def async_get_token_sessions(**kwargs: Any) -> list[dict[str, Any]]:
    """异步获取会话统计"""
    return await asyncio.to_thread(get_token_sessions, **kwargs)


async def async_get_token_total(**kwargs: Any) -> dict[str, Any]:
    """异步获取 Token 总量"""
    return await asyncio.to_thread(get_token_total, **kwargs)


async def async_get_daily_stats(**kwargs: Any) -> list[dict[str, Any]]:
    """异步获取每日统计"""
    return await asyncio.to_thread(get_daily_stats, **kwargs)
