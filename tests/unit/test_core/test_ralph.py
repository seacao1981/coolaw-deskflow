"""Tests for RalphLoop retry mechanism."""

from __future__ import annotations

import asyncio

import pytest

from deskflow.core.ralph import RalphLoop


class TestRalphLoop:
    """Tests for RalphLoop."""

    async def test_success_on_first_attempt(self) -> None:
        loop = RalphLoop(max_retries=3)

        async def success_task() -> str:
            return "done"

        result = await loop.execute(success_task)
        assert result == "done"
        assert loop.current_attempt == 0
        assert loop.is_running is False

    async def test_success_after_retry(self) -> None:
        loop = RalphLoop(max_retries=3, retry_delay=0.01)
        attempts = 0

        async def flaky_task() -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ValueError("not yet")
            return "finally"

        result = await loop.execute(flaky_task)
        assert result == "finally"
        assert attempts == 3

    async def test_exhausted_retries(self) -> None:
        loop = RalphLoop(max_retries=2, retry_delay=0.01)

        async def always_fail() -> None:
            raise RuntimeError("nope")

        with pytest.raises(RuntimeError, match="nope"):
            await loop.execute(always_fail)

        assert loop.is_running is False

    async def test_cancellation(self) -> None:
        loop = RalphLoop(max_retries=5, retry_delay=0.01)

        async def slow_fail() -> None:
            raise ValueError("fail")

        # Cancel after a short delay
        async def cancel_later() -> None:
            await asyncio.sleep(0.02)
            loop.cancel()

        task = asyncio.create_task(cancel_later())

        with pytest.raises(asyncio.CancelledError):
            await loop.execute(slow_fail)

        await task

    async def test_on_retry_callback(self) -> None:
        loop = RalphLoop(max_retries=2, retry_delay=0.01)
        retry_log: list[tuple[int, str]] = []

        async def fail_once() -> str:
            if len(retry_log) == 0:
                raise ValueError("first fail")
            return "ok"

        async def on_retry(attempt: int, error: Exception) -> None:
            retry_log.append((attempt, str(error)))

        await loop.execute(fail_once, on_retry=on_retry)
        assert len(retry_log) == 1
        assert retry_log[0][0] == 0
        assert "first fail" in retry_log[0][1]

    async def test_reset(self) -> None:
        loop = RalphLoop(max_retries=1, retry_delay=0.01)

        async def fail_task() -> None:
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await loop.execute(fail_task)

        # Reset and reuse
        loop.reset()
        assert loop.is_running is False
        assert loop.current_attempt == 0

    async def test_backoff(self) -> None:
        loop = RalphLoop(
            max_retries=2,
            retry_delay=0.01,
            backoff_factor=2.0,
            max_delay=1.0,
        )
        attempt_times: list[float] = []

        async def timed_fail() -> None:
            import time

            attempt_times.append(time.time())
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await loop.execute(timed_fail)

        # Should have 3 attempts (0, 1, 2)
        assert len(attempt_times) == 3
        # Gap between attempts should increase (with backoff)
        gap1 = attempt_times[1] - attempt_times[0]
        gap2 = attempt_times[2] - attempt_times[1]
        assert gap2 > gap1 * 1.5  # Allowing some tolerance

    async def test_is_running_during_execution(self) -> None:
        loop = RalphLoop(max_retries=0)
        running_state = False

        async def check_running() -> None:
            nonlocal running_state
            running_state = loop.is_running

        await loop.execute(check_running)
        assert running_state is True
        assert loop.is_running is False

    async def test_with_args_and_kwargs(self) -> None:
        loop = RalphLoop(max_retries=0)

        async def add(a: int, b: int, extra: int = 0) -> int:
            return a + b + extra

        result = await loop.execute(add, 3, 4, extra=10)
        assert result == 17
