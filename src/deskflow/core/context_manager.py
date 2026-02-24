"""
上下文管理器

负责在对话上下文接近 LLM 上下文窗口限制时，
使用 LLM 分块摘要压缩早期对话，保留最近的工具交互完整性。

核心功能:
- 估算 token 数量 (中英文感知算法)
- 消息分组 (保证 tool_calls/tool_result 配对完整)
- LLM 分块摘要压缩
- 递归压缩
- 硬截断保底
- 动态上下文窗口计算
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)

# 上下文管理常量
DEFAULT_MAX_CONTEXT_TOKENS = 124000
CHARS_PER_TOKEN = 2  # JSON 序列化后约 2 字符 = 1 token
MIN_RECENT_TURNS = 8  # 至少保留最近 8 组对话 (工具密集型对话需要更多上下文)
COMPRESSION_RATIO = 0.15  # 目标压缩到原上下文的 15%
CHUNK_MAX_TOKENS = 30000  # 每次发给 LLM 压缩的单块上限
LARGE_TOOL_RESULT_THRESHOLD = 5000  # 单条 tool_result 超过此 token 数时独立压缩


@dataclass
class CompressionResult:
    """压缩结果"""

    original_messages: list[dict] = field(default_factory=list)
    compressed_messages: list[dict] = field(default_factory=list)
    original_token_count: int = 0
    compressed_token_count: int = 0
    compression_ratio: float = 0.0
    was_compressed: bool = False


class ContextManager:
    """
    上下文压缩和管理器。

    负责在对话上下文接近 LLM 上下文窗口限制时，
    使用 LLM 分块摘要压缩早期对话，保留最近的工具交互完整性。
    """

    def __init__(
        self,
        brain: Any | None = None,
        cancel_event: asyncio.Event | None = None,
        max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    ) -> None:
        """
        Args:
            brain: Brain 实例，用于 LLM 调用
            cancel_event: 可选的取消事件，set 时中断压缩 LLM 调用
            max_context_tokens: 最大上下文 token 数
        """
        self._brain = brain
        self._cancel_event = cancel_event
        self._max_context_tokens = max_context_tokens

    def set_brain(self, brain: Any) -> None:
        """设置 Brain 实例 (延迟注入)"""
        self._brain = brain

    def set_cancel_event(self, event: asyncio.Event | None) -> None:
        """更新 cancel_event (每次任务开始时由 Agent 设置)"""
        self._cancel_event = event

    def _check_cancelled(self) -> None:
        """检查是否被取消"""
        if self._cancel_event and self._cancel_event.is_set():
            logger.info("[ContextManager] Operation cancelled by user")
            raise asyncio.CancelledError("Context compression cancelled by user")

    async def _cancellable_llm(self, **kwargs: Any) -> Any:
        """可被 cancel_event 中断的 LLM 调用"""
        logger.debug("[ContextManager] _cancellable_llm 发起 LLM 调用")

        if not self._brain:
            raise RuntimeError("Brain not initialized")

        coro = self._brain.messages_create_async(**kwargs)

        if not self._cancel_event:
            return await coro

        task = asyncio.create_task(coro)
        cancel_waiter = asyncio.create_task(self._cancel_event.wait())

        done, pending = await asyncio.wait(
            {task, cancel_waiter},
            return_when=asyncio.FIRST_COMPLETED,
        )

        for t in pending:
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass

        if task in done:
            logger.debug("[ContextManager] _cancellable_llm LLM 调用完成")
            return task.result()

        logger.info("[ContextManager] _cancellable_llm 被用户取消")
        raise asyncio.CancelledError("Context compression cancelled by user")

    def get_max_context_tokens(self) -> int:
        """
        动态获取当前模型的上下文窗口大小。

        优先级:
        1. 端点配置的 context_window 字段
        2. 兜底值 150000
        3. 减去 max_tokens (输出预留) 和 15% buffer
        """
        FALLBACK_CONTEXT_WINDOW = 150000

        try:
            if not self._brain:
                return self._max_context_tokens

            info = self._brain.get_current_model_info()
            ep_name = info.get("name", "")

            # 从 LLMClient 获取端点配置
            llm_client = getattr(self._brain, "_llm_client", None)
            if not llm_client:
                return self._max_context_tokens

            endpoints = getattr(llm_client, "endpoints", [])
            for ep in endpoints:
                if ep.name == ep_name:
                    ctx = getattr(ep, "context_window", 0) or 0
                    if ctx < 8192:
                        ctx = FALLBACK_CONTEXT_WINDOW
                    output_reserve = getattr(ep, "max_tokens", 0) or 4096
                    output_reserve = min(output_reserve, ctx // 2)
                    result = int((ctx - output_reserve) * 0.90)
                    if result < 4096:
                        return DEFAULT_MAX_CONTEXT_TOKENS
                    return result

            return DEFAULT_MAX_CONTEXT_TOKENS
        except Exception as e:
            logger.warning("get_max_context_tokens_failed", error=str(e))
            return self._max_context_tokens

    def estimate_tokens(self, text: str) -> int:
        """
        估算文本的 token 数量。

        使用中英文感知算法：
        - 中文约 1.5 字符/token
        - 英文约 4 字符/token
        """
        if not text:
            return 0

        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        total_chars = len(text)
        english_chars = total_chars - chinese_chars

        chinese_tokens = chinese_chars / 1.5
        english_tokens = english_chars / 4

        return max(int(chinese_tokens + english_tokens), 1)

    def estimate_messages_tokens(self, messages: list[dict]) -> int:
        """
        估算消息列表的 token 数量。

        对每条消息的 content 使用与 estimate_tokens 相同的中英文感知算法，
        并为每条消息加固定结构开销 (role / tool_use_id 等约 10 tokens)。
        """
        total = 0
        for msg in messages:
            # 固定结构开销
            total += 10

            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.estimate_tokens(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text", "") or item.get("content", "")
                        if isinstance(text, str) and text:
                            total += self.estimate_tokens(text)
                        else:
                            total += self.estimate_tokens(
                                json.dumps(item, ensure_ascii=False, default=str)
                            )
                    elif isinstance(item, str):
                        total += self.estimate_tokens(item)

            # tool_use_id 等字段
            tool_use_id = msg.get("tool_use_id", "")
            if tool_use_id:
                total += len(tool_use_id) // 4

        return total

    def _group_messages_by_turn(self, messages: list[dict]) -> list[list[dict]]:
        """
        将消息按对话轮次分组，保证 tool_calls/tool_result 配对完整。

        规则:
        1. user 消息开始一轮
        2. assistant 的 tool_calls 和对应的 tool_result 必须在一起
        3. assistant 的最终回复结束一轮
        """
        if not messages:
            return []

        groups = []
        current_group = []
        pending_tool_calls = {}

        for msg in messages:
            role = msg.get("role", "")

            if role == "user":
                # 用户消息开始新轮次
                if current_group:
                    groups.append(current_group)
                current_group = [msg]
                pending_tool_calls = {}

            elif role == "assistant":
                current_group.append(msg)

                # 检查是否有 tool_calls
                tool_calls = msg.get("tool_calls", [])
                if tool_calls:
                    for tc in tool_calls:
                        tc_id = tc.get("id", "")
                        if tc_id:
                            pending_tool_calls[tc_id] = True

            elif role == "tool":
                current_group.append(msg)
                # 匹配 tool_result
                tool_call_id = msg.get("tool_call_id", "")
                if tool_call_id in pending_tool_calls:
                    del pending_tool_calls[tool_call_id]

        if current_group:
            groups.append(current_group)

        return groups

    def _serialize_messages(self, messages: list[dict]) -> str:
        """将消息列表序列化为 JSON 字符串"""
        return json.dumps(messages, ensure_ascii=False, default=str)

    def _create_compression_prompt(self, messages: list[dict]) -> str:
        """创建压缩提示"""
        messages_json = self._serialize_messages(messages)

        prompt = f"""Please summarize the following conversation concisely. Keep key information, decisions, and tool results, but remove redundant details. Output only the summary, no analysis.

Conversation:
{messages_json}

Summary:"""

        return prompt

    async def _compress_block(self, messages: list[dict]) -> list[dict]:
        """
        压缩单个消息块

        Args:
            messages: 要压缩的消息列表

        Returns:
            压缩后的消息列表 (单条 summary 消息)
        """
        self._check_cancelled()

        prompt = self._create_compression_prompt(messages)

        try:
            result = await self._cancellable_llm(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
            )

            summary = result.content if hasattr(result, "content") else str(result)

            # 创建摘要消息
            summary_msg = {
                "role": "system",
                "content": f"[Earlier conversation summary] {summary}",
            }

            return [summary_msg]

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"_compress_block failed: {e}")
            # 压缩失败，返回原始消息
            return messages

    async def compress_context(
        self,
        messages: list[dict],
        target_token_limit: int | None = None,
    ) -> CompressionResult:
        """
        压缩上下文

        Args:
            messages: 原始消息列表
            target_token_limit: 目标 token 限制，如不指定则使用动态计算的值

        Returns:
            CompressionResult 包含压缩结果和统计信息
        """
        if not messages:
            return CompressionResult()

        if target_token_limit is None:
            target_token_limit = self.get_max_context_tokens()

        # 预留输出空间 (90% 用于输入)
        target_token_limit = int(target_token_limit * 0.90)

        original_token_count = self.estimate_messages_tokens(messages)

        # 如果未超限，直接返回
        if original_token_count < target_token_limit:
            return CompressionResult(
                original_messages=messages,
                compressed_messages=messages,
                original_token_count=original_token_count,
                compressed_token_count=original_token_count,
                was_compressed=False,
            )

        logger.info(
            "context_compression_needed",
            current_tokens=original_token_count,
            limit=target_token_limit,
        )

        # 分组消息
        groups = self._group_messages_by_turn(messages)

        # 保留最近的 MIN_RECENT_TURNS 轮
        if len(groups) <= MIN_RECENT_TURNS:
            # 无法分组压缩，硬截断保底
            return await self._hard_truncate(messages, target_token_limit)

        # 分离早期和近期消息
        early_groups = groups[:-MIN_RECENT_TURNS]
        recent_groups = groups[-MIN_RECENT_TURNS:]

        recent_messages = []
        for group in recent_groups:
            recent_messages.extend(group)

        recent_token_count = self.estimate_messages_tokens(recent_messages)

        # 计算早期消息需要压缩到的目标大小
        target_early_tokens = target_token_limit - recent_token_count - 1000  # 预留 buffer

        if target_early_tokens <= 0:
            # 近期消息已超限，硬截断
            return await self._hard_truncate(messages, target_token_limit)

        # 分块压缩早期消息
        compressed_early = await self._compress_early_messages(
            early_groups, target_early_tokens
        )

        # 合并压缩后的早期消息和近期消息
        compressed_messages = compressed_early + recent_messages

        compressed_token_count = self.estimate_messages_tokens(compressed_messages)

        # 如果仍然超限，递归压缩
        if compressed_token_count > target_token_limit:
            logger.info(
                "context_still_over_limit",
                current_tokens=compressed_token_count,
                limit=target_token_limit,
            )
            return await self.compress_context(compressed_messages, target_token_limit)

        compression_ratio = (
            (original_token_count - compressed_token_count) / original_token_count * 100
            if original_token_count > 0
            else 0
        )

        logger.info(
            "context_compression_completed",
            original_tokens=original_token_count,
            compressed_tokens=compressed_token_count,
            compression_ratio=f"{compression_ratio:.1f}%",
        )

        return CompressionResult(
            original_messages=messages,
            compressed_messages=compressed_messages,
            original_token_count=original_token_count,
            compressed_token_count=compressed_token_count,
            compression_ratio=compression_ratio / 100,
            was_compressed=True,
        )

    async def _compress_early_messages(
        self, groups: list[list[dict]], target_tokens: int
    ) -> list[dict]:
        """
        压缩早期消息

        策略:
        1. 将早期消息分块
        2. 对每块进行 LLM 摘要
        3. 合并所有摘要

        Args:
            groups: 按轮次分组的早期消息
            target_tokens: 目标 token 数

        Returns:
            压缩后的消息列表
        """
        if not groups:
            return []

        # 扁平化消息
        early_messages = []
        for group in groups:
            early_messages.extend(group)

        # 按 CHUNK_MAX_TOKENS 分块
        blocks = self._split_into_blocks(early_messages, CHUNK_MAX_TOKENS)

        logger.info(
            "_compress_early_messages",
            blocks_count=len(blocks),
            target_tokens=target_tokens,
        )

        # 并行压缩每个块
        compressed_blocks = []
        for i, block in enumerate(blocks):
            self._check_cancelled()
            logger.debug(f"Compressing block {i + 1}/{len(blocks)}")

            try:
                compressed = await self._compress_block(block)
                compressed_blocks.extend(compressed)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Block {i + 1} compression failed: {e}")
                # 压缩失败，保留原始块
                compressed_blocks.extend(block)

            # 每块之间短暂暂停，避免速率限制
            if i < len(blocks) - 1:
                await asyncio.sleep(0.5)

        # 如果压缩后仍然超限，再次递归压缩
        compressed_tokens = self.estimate_messages_tokens(compressed_blocks)
        if compressed_tokens > target_tokens and len(compressed_blocks) > 1:
            logger.info(
                "recursive_compression_needed",
                current_tokens=compressed_tokens,
                target_tokens=target_tokens,
            )
            # 合并所有块，再次压缩
            return await self._compress_early_messages(
                [compressed_blocks], target_tokens
            )

        return compressed_blocks

    def _split_into_blocks(
        self, messages: list[dict], max_tokens_per_block: int
    ) -> list[list[dict]]:
        """
        将消息分割成多个块，每块不超过指定的 token 数

        Args:
            messages: 消息列表
            max_tokens_per_block: 每块最大 token 数

        Returns:
            消息块列表
        """
        if not messages:
            return []

        blocks = []
        current_block = []
        current_tokens = 0

        for msg in messages:
            msg_tokens = self.estimate_messages_tokens([msg])

            if current_tokens + msg_tokens > max_tokens_per_block:
                # 当前块已满，开始新块
                if current_block:
                    blocks.append(current_block)
                current_block = [msg]
                current_tokens = msg_tokens
            else:
                current_block.append(msg)
                current_tokens += msg_tokens

        if current_block:
            blocks.append(current_block)

        return blocks

    async def _hard_truncate(
        self, messages: list[dict], target_token_limit: int
    ) -> CompressionResult:
        """
        硬截断保底策略

        当压缩失败或无法有效压缩时，直接截断早期消息

        Args:
            messages: 原始消息列表
            target_token_limit: 目标 token 限制

        Returns:
            CompressionResult 包含截断结果
        """
        original_token_count = self.estimate_messages_tokens(messages)

        # 从后向前累加，直到接近限制
        truncated = []
        current_tokens = 0

        for msg in reversed(messages):
            msg_tokens = self.estimate_messages_tokens([msg])
            if current_tokens + msg_tokens > target_token_limit:
                break
            truncated.insert(0, msg)
            current_tokens += msg_tokens

        truncated_token_count = self.estimate_messages_tokens(truncated)

        logger.warning(
            "hard_truncate_applied",
            original_tokens=original_token_count,
            truncated_tokens=truncated_token_count,
        )

        return CompressionResult(
            original_messages=messages,
            compressed_messages=truncated,
            original_token_count=original_token_count,
            compressed_token_count=truncated_token_count,
            compression_ratio=(original_token_count - truncated_token_count)
            / original_token_count
            if original_token_count > 0
            else 0,
            was_compressed=True,
        )


# 辅助函数
def create_context_manager(
    brain: Any | None = None,
    cancel_event: asyncio.Event | None = None,
    max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
) -> ContextManager:
    """创建上下文管理器实例"""
    return ContextManager(
        brain=brain,
        cancel_event=cancel_event,
        max_context_tokens=max_context_tokens,
    )
