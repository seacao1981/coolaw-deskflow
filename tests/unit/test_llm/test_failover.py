"""Tests for LLM failover module."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from deskflow.llm.failover import (
    HealthStatus,
    ProviderHealth,
    FailoverConfig,
    HealthMonitor,
    get_health_monitor,
    reset_health_monitor,
)


class TestProviderHealth:
    """测试提供商健康状态"""

    def test_default_status(self):
        """测试默认状态"""
        health = ProviderHealth(provider_name="test")
        assert health.status == HealthStatus.UNKNOWN
        assert health.consecutive_failures == 0
        assert health.consecutive_successes == 0

    def test_is_available_healthy(self):
        """测试健康状态可用"""
        health = ProviderHealth(provider_name="test", status=HealthStatus.HEALTHY)
        assert health.is_available() is True

    def test_is_available_unhealthy(self):
        """测试不健康状态不可用"""
        health = ProviderHealth(provider_name="test", status=HealthStatus.UNHEALTHY)
        assert health.is_available() is False

    def test_is_available_in_cooldown(self):
        """测试冷静期内不可用"""
        import time
        health = ProviderHealth(
            provider_name="test",
            status=HealthStatus.HEALTHY,
            cooldown_until=time.time() + 100,  # 100 秒后
        )
        assert health.is_available() is False
        assert health.is_in_cooldown() is True

    def test_remaining_cooldown(self):
        """测试剩余冷静期时间"""
        import time
        cooldown_time = time.time() + 30
        health = ProviderHealth(
            provider_name="test",
            cooldown_until=cooldown_time,
        )
        remaining = health.remaining_cooldown()
        assert 0 < remaining <= 30


class TestFailoverConfig:
    """测试故障转移配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = FailoverConfig()
        assert config.cooldown_base_seconds == 30
        assert config.cooldown_max_seconds == 300
        assert config.failure_threshold == 3
        assert config.recovery_threshold == 2

    def test_custom_config(self):
        """测试自定义配置"""
        config = FailoverConfig(
            cooldown_base_seconds=60,
            cooldown_max_seconds=600,
            failure_threshold=5,
        )
        assert config.cooldown_base_seconds == 60
        assert config.cooldown_max_seconds == 600
        assert config.failure_threshold == 5


@pytest.mark.asyncio
class TestHealthMonitor:
    """测试健康监控器"""

    def setup_method(self):
        """每个测试前重置监控器"""
        reset_health_monitor()

    def teardown_method(self):
        """每个测试后清理"""
        reset_health_monitor()

    def test_register_provider(self):
        """测试注册提供商"""
        monitor = HealthMonitor()
        monitor.register_provider("anthropic")
        health = monitor.get_provider("anthropic")
        assert health is not None
        assert health.provider_name == "anthropic"
        assert health.status == HealthStatus.UNKNOWN

    def test_unregister_provider(self):
        """测试注销提供商"""
        monitor = HealthMonitor()
        monitor.register_provider("anthropic")
        monitor.unregister_provider("anthropic")
        health = monitor.get_provider("anthropic")
        assert health is None

    def test_get_available_providers(self):
        """测试获取可用提供商"""
        monitor = HealthMonitor()
        monitor.register_provider("anthropic")
        monitor.register_provider("openai")
        monitor.register_provider("dashscope")

        # 设置不同状态
        monitor._providers["anthropic"].status = HealthStatus.HEALTHY
        monitor._providers["openai"].status = HealthStatus.UNHEALTHY
        monitor._providers["dashscope"].status = HealthStatus.HEALTHY

        available = monitor.get_available_providers()
        assert "anthropic" in available
        assert "openai" not in available
        assert "dashscope" in available

    async def test_record_success(self):
        """测试记录成功"""
        monitor = HealthMonitor()
        monitor.register_provider("anthropic")

        await monitor.record_success("anthropic", response_time_ms=100)

        health = monitor.get_provider("anthropic")
        assert health.consecutive_successes == 1
        assert health.consecutive_failures == 0
        assert health.status == HealthStatus.HEALTHY

    async def test_record_success_recovery(self):
        """测试连续成功后恢复"""
        monitor = HealthMonitor(
            FailoverConfig(recovery_threshold=2)
        )
        monitor.register_provider("anthropic")

        # 先设为降级状态
        monitor._providers["anthropic"].status = HealthStatus.DEGRADED

        # 连续成功 2 次
        await monitor.record_success("anthropic")
        assert monitor._providers["anthropic"].status == HealthStatus.DEGRADED

        await monitor.record_success("anthropic")
        assert monitor._providers["anthropic"].status == HealthStatus.HEALTHY

    async def test_record_failure(self):
        """测试记录失败"""
        monitor = HealthMonitor()
        monitor.register_provider("anthropic")

        await monitor.record_failure("anthropic", "API error")

        health = monitor.get_provider("anthropic")
        assert health.consecutive_failures == 1
        assert health.consecutive_successes == 0
        assert health.last_error == "API error"

    async def test_record_failure_cooldown(self):
        """测试失败达到阈值进入冷静期"""
        import time

        monitor = HealthMonitor(
            FailoverConfig(
                failure_threshold=2,
                cooldown_base_seconds=10,
            )
        )
        monitor.register_provider("anthropic")

        # 连续失败 2 次
        await monitor.record_failure("anthropic", "Error 1")
        await monitor.record_failure("anthropic", "Error 2")

        health = monitor.get_provider("anthropic")
        assert health.status == HealthStatus.DEGRADED
        assert health.is_in_cooldown() is True
        assert health.remaining_cooldown() > 0

    async def test_calculate_cooldown_exponential(self):
        """测试冷静期指数退避"""
        monitor = HealthMonitor(
            FailoverConfig(
                cooldown_base_seconds=10,
                cooldown_multiplier=2.0,
                cooldown_max_seconds=100,
            )
        )

        # 失败 1 次：10 秒
        assert monitor._calculate_cooldown(1) == 10

        # 失败 2 次：20 秒
        assert monitor._calculate_cooldown(2) == 20

        # 失败 3 次：40 秒
        assert monitor._calculate_cooldown(3) == 40

        # 失败 10 次：应该被限制在 100 秒
        assert monitor._calculate_cooldown(10) == 100

    async def test_health_check_success(self):
        """测试健康检查成功"""
        monitor = HealthMonitor()
        check_func = AsyncMock()

        status = await monitor.health_check("anthropic", check_func)

        assert status == HealthStatus.HEALTHY
        check_func.assert_called_once()

    async def test_health_check_timeout(self):
        """测试健康检查超时"""
        monitor = HealthMonitor(
            FailoverConfig(health_check_timeout=1)
        )

        async def slow_check():
            await asyncio.sleep(2)

        status = await monitor.health_check("anthropic", slow_check)
        assert status == HealthStatus.UNHEALTHY

    async def test_health_check_failure(self):
        """测试健康检查失败"""
        monitor = HealthMonitor()

        async def failing_check():
            raise Exception("Connection error")

        status = await monitor.health_check("anthropic", failing_check)
        assert status == HealthStatus.UNHEALTHY

    async def test_get_status_summary(self):
        """测试获取状态摘要"""
        monitor = HealthMonitor()
        monitor.register_provider("anthropic")
        monitor.register_provider("openai")

        monitor._providers["anthropic"].status = HealthStatus.HEALTHY
        monitor._providers["openai"].status = HealthStatus.DEGRADED

        summary = monitor.get_status_summary()

        assert summary["total"] == 2
        assert summary["healthy"] == 1
        assert summary["degraded"] == 1
        assert summary["unhealthy"] == 0

    async def test_background_health_check(self):
        """测试后台健康检查"""
        monitor = HealthMonitor(
            FailoverConfig(health_check_interval=0.5)
        )
        monitor.register_provider("anthropic")

        check_count = 0

        async def mock_check():
            nonlocal check_count
            check_count += 1

        await monitor.start_background_health_check(mock_check, ["anthropic"])

        # 等待一段时间
        await asyncio.sleep(1.2)

        await monitor.stop_background_health_check()

        # 应该至少检查了 2 次
        assert check_count >= 2


class TestSingleton:
    """测试单例模式"""

    def setup_method(self):
        reset_health_monitor()

    def teardown_method(self):
        reset_health_monitor()

    def test_get_health_monitor_singleton(self):
        """测试单例获取"""
        monitor1 = get_health_monitor()
        monitor2 = get_health_monitor()
        assert monitor1 is monitor2

    def test_get_health_monitor_custom_config(self):
        """测试自定义配置"""
        config = FailoverConfig(cooldown_base_seconds=60)
        monitor = get_health_monitor(config)
        assert monitor.config.cooldown_base_seconds == 60
