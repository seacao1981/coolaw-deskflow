"""
LLM 故障转移增强

在现有 LLMClient 基础上增强:
- 冷静期机制 (Cool-down period)
- 指数退避配置优化
- 健康检查增强
- 故障统计和告警
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ProviderHealth:
    """提供商健康状态"""
    provider_name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    last_check: float = 0
    last_error: str = ""
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    cooldown_until: float = 0  # 冷静期结束时间
    response_time_ms: float = 0

    def is_available(self) -> bool:
        """检查是否可用"""
        if self.status == HealthStatus.UNHEALTHY:
            return False
        if self.cooldown_until > time.time():
            return False
        return True

    def is_in_cooldown(self) -> bool:
        """是否在冷静期内"""
        return self.cooldown_until > time.time()

    def remaining_cooldown(self) -> float:
        """剩余冷静期时间（秒）"""
        if not self.is_in_cooldown():
            return 0
        return max(0, self.cooldown_until - time.time())


@dataclass
class FailoverConfig:
    """故障转移配置"""
    # 冷静期配置
    cooldown_base_seconds: int = 30  # 基础冷静期
    cooldown_max_seconds: int = 300  # 最大冷静期（5 分钟）
    cooldown_multiplier: float = 2.0  # 冷静期倍增系数

    # 健康检查配置
    health_check_interval: int = 60  # 健康检查间隔（秒）
    health_check_timeout: int = 10  # 健康检查超时（秒）
    failure_threshold: int = 3  # 失败阈值（达到后进入冷静期）
    recovery_threshold: int = 2  # 恢复阈值（连续成功后恢复）

    # 重试配置
    max_retries: int = 3  # 最大重试次数
    retry_base_delay: float = 1.0  # 基础重试延迟（秒）
    retry_max_delay: float = 60.0  # 最大重试延迟（秒）
    retry_exponential_base: float = 2.0  # 指数退避基数


class HealthMonitor:
    """
    健康监控器

    跟踪各 LLM 提供商的健康状态，管理冷静期和故障转移。
    """

    def __init__(self, config: FailoverConfig | None = None) -> None:
        self.config = config or FailoverConfig()
        self._providers: dict[str, ProviderHealth] = {}
        self._lock = asyncio.Lock()
        self._health_check_task: asyncio.Task | None = None
        self._running = False

    def register_provider(self, provider_name: str) -> None:
        """注册提供商"""
        if provider_name not in self._providers:
            self._providers[provider_name] = ProviderHealth(
                provider_name=provider_name,
                status=HealthStatus.UNKNOWN,
            )
            logger.info(f"[HealthMonitor] Registered provider: {provider_name}")

    def unregister_provider(self, provider_name: str) -> None:
        """注销提供商"""
        if provider_name in self._providers:
            del self._providers[provider_name]
            logger.info(f"[HealthMonitor] Unregistered provider: {provider_name}")

    def get_provider(self, provider_name: str) -> ProviderHealth | None:
        """获取提供商健康状态"""
        return self._providers.get(provider_name)

    def get_available_providers(self) -> list[str]:
        """获取可用提供商列表"""
        return [
            name for name, health in self._providers.items()
            if health.is_available()
        ]

    async def record_success(self, provider_name: str, response_time_ms: float = 0) -> None:
        """记录成功"""
        async with self._lock:
            if provider_name not in self._providers:
                self.register_provider(provider_name)

            health = self._providers[provider_name]
            health.consecutive_successes += 1
            health.consecutive_failures = 0
            health.last_error = ""
            health.response_time_ms = response_time_ms
            health.last_check = time.time()

            # 连续成功后恢复状态
            if health.status == HealthStatus.DEGRADED:
                if health.consecutive_successes >= self.config.recovery_threshold:
                    health.status = HealthStatus.HEALTHY
                    health.cooldown_until = 0
                    logger.info(f"[HealthMonitor] Provider {provider_name} recovered to HEALTHY")

            elif health.status == HealthStatus.UNKNOWN:
                health.status = HealthStatus.HEALTHY

            logger.debug(
                f"[HealthMonitor] Provider {provider_name} success "
                f"(successes={health.consecutive_successes}, failures={health.consecutive_failures})"
            )

    async def record_failure(
        self,
        provider_name: str,
        error: str,
        response_time_ms: float = 0,
    ) -> None:
        """记录失败"""
        async with self._lock:
            if provider_name not in self._providers:
                self.register_provider(provider_name)

            health = self._providers[provider_name]
            health.consecutive_failures += 1
            health.consecutive_successes = 0
            health.last_error = error
            health.response_time_ms = response_time_ms
            health.last_check = time.time()

            # 达到失败阈值，进入冷静期
            if health.consecutive_failures >= self.config.failure_threshold:
                if health.status != HealthStatus.UNHEALTHY:
                    health.status = HealthStatus.DEGRADED

                # 计算冷静期时间（指数退避）
                cooldown = self._calculate_cooldown(health.consecutive_failures)
                health.cooldown_until = time.time() + cooldown

                logger.warning(
                    f"[HealthMonitor] Provider {provider_name} entering cooldown for {cooldown:.0f}s "
                    f"(failures={health.consecutive_failures})"
                )

            logger.debug(
                f"[HealthMonitor] Provider {provider_name} failure "
                f"(successes={health.consecutive_successes}, failures={health.consecutive_failures})"
            )

    def _calculate_cooldown(self, failure_count: int) -> float:
        """计算冷静期时间（指数退避）"""
        # 基础冷静期 * 倍增系数^(失败次数 -1)
        cooldown = self.config.cooldown_base_seconds * (
            self.config.cooldown_multiplier ** (failure_count - 1)
        )
        # 限制最大冷静期
        return min(cooldown, self.config.cooldown_max_seconds)

    async def health_check(
        self,
        provider_name: str,
        check_func: callable,
    ) -> HealthStatus:
        """
        执行健康检查

        Args:
            provider_name: 提供商名称
            check_func: 健康检查函数（异步）

        Returns:
            健康状态
        """
        if provider_name not in self._providers:
            self.register_provider(provider_name)

        health = self._providers[provider_name]
        start_time = time.time()

        try:
            # 执行健康检查
            await asyncio.wait_for(
                check_func(),
                timeout=self.config.health_check_timeout,
            )

            response_time = (time.time() - start_time) * 1000
            await self.record_success(provider_name, response_time)

            return health.status

        except asyncio.TimeoutError:
            await self.record_failure(provider_name, "Health check timeout")
            return HealthStatus.UNHEALTHY

        except Exception as e:
            await self.record_failure(provider_name, str(e))
            return HealthStatus.UNHEALTHY

    async def start_background_health_check(
        self,
        check_func: callable,
        providers: list[str] | None = None,
    ) -> None:
        """启动后台健康检查"""
        if self._running:
            return

        self._running = True
        providers = providers or list(self._providers.keys())

        async def _check_loop():
            while self._running:
                for provider_name in providers:
                    if provider_name in self._providers:
                        asyncio.create_task(
                            self.health_check(provider_name, check_func)
                        )
                await asyncio.sleep(self.config.health_check_interval)

        self._health_check_task = asyncio.create_task(_check_loop())
        logger.info(
            f"[HealthMonitor] Started background health check "
            f"(interval={self.config.health_check_interval}s)"
        )

    async def stop_background_health_check(self) -> None:
        """停止后台健康检查"""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
        logger.info("[HealthMonitor] Stopped background health check")

    def get_status_summary(self) -> dict[str, Any]:
        """获取状态摘要"""
        total = len(self._providers)
        healthy = sum(
            1 for h in self._providers.values()
            if h.status == HealthStatus.HEALTHY
        )
        degraded = sum(
            1 for h in self._providers.values()
            if h.status == HealthStatus.DEGRADED
        )
        unhealthy = sum(
            1 for h in self._providers.values()
            if h.status == HealthStatus.UNHEALTHY
        )
        in_cooldown = sum(
            1 for h in self._providers.values()
            if h.is_in_cooldown()
        )

        return {
            "total": total,
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "in_cooldown": in_cooldown,
            "providers": {
                name: {
                    "status": h.status.value,
                    "consecutive_failures": h.consecutive_failures,
                    "consecutive_successes": h.consecutive_successes,
                    "in_cooldown": h.is_in_cooldown(),
                    "remaining_cooldown": h.remaining_cooldown(),
                }
                for name, h in self._providers.items()
            },
        }


# 全局健康监控实例
_health_monitor: HealthMonitor | None = None


def get_health_monitor(config: FailoverConfig | None = None) -> HealthMonitor:
    """获取健康监控单例"""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor(config)
    return _health_monitor


def reset_health_monitor() -> None:
    """重置健康监控（用于测试）"""
    global _health_monitor
    if _health_monitor:
        # 尝试在事件循环中停止后台检查
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(_health_monitor.stop_background_health_check())
        except RuntimeError:
            # 没有运行中的事件循环，直接重置
            _health_monitor._running = False
            _health_monitor._health_check_task = None
    _health_monitor = None
