"""Tavily 월간 호출 횟수를 제한한다. 캐시 히트는 카운트하지 않는다(Tavily 미호출이므로).

무료 티어(월 1,000 크레딧) 소진을 막기 위한 안전 마진으로 기본 900회를 상한으로 둔다
(.harness/PLAN.md Task 2 참고). 카운터 키에 `YYYY-MM`을 포함해 다음 달이 되면 자동으로
새 키를 쓰게 되므로 별도 리셋 로직이 필요 없다. 그래도 오래된 키가 영구히 남지 않도록
넉넉한 TTL(기본 40일)을 둔다.
"""

from collections.abc import Awaitable
from datetime import datetime
from typing import cast

from redis.asyncio import Redis

USAGE_KEY_PREFIX = "search:usage:"
# 40일 — 다음 달 키로 넘어간 뒤에도 잠시 남아있다가 만료된다.
DEFAULT_USAGE_KEY_TTL_SECONDS = 40 * 24 * 60 * 60


def _usage_key(now: datetime) -> str:
    return f"{USAGE_KEY_PREFIX}{now:%Y-%m}"


class SearchUsageLimiter:
    """월간 Tavily 호출 횟수를 추적하고, 상한 초과 여부를 판단한다."""

    def __init__(self, redis: Redis, *, monthly_limit: int) -> None:
        self._redis = redis
        self._monthly_limit = monthly_limit

    async def is_limit_exceeded(self, *, now: datetime) -> bool:
        """이번 달 호출 횟수가 상한을 이미 넘었는지 확인한다(증가시키지 않음)."""
        key = _usage_key(now)
        raw_count = await cast("Awaitable[str | None]", self._redis.get(key))
        count = int(raw_count) if raw_count is not None else 0
        return count >= self._monthly_limit

    async def increment(self, *, now: datetime) -> int:
        """이번 달 호출 횟수를 1 증가시키고 새 값을 반환한다. 캐시 히트 시에는 호출하지 않는다."""
        key = _usage_key(now)
        new_count = await cast("Awaitable[int]", self._redis.incr(key))
        if new_count == 1:
            # 이번 달 첫 호출일 때만 TTL을 설정한다(이미 설정돼 있으면 덮어쓸 필요 없음).
            await cast(
                "Awaitable[bool]",
                self._redis.expire(key, DEFAULT_USAGE_KEY_TTL_SECONDS),
            )
        return new_count
