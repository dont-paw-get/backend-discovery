"""웹 검색 결과 캐시. Redis에 정규화한 질의를 키로 검색 결과(JSON)를 TTL과 함께 저장한다.

`ChatSessionStore`(대화 세션 데이터)와는 별개 책임이다 — 이 클래스는 세션이 아니라
"같은 질의를 다시 검색하지 않기 위한 캐시"만 담당한다 (.harness/PLAN.md Task 2 참고).
"""

import json
import re
from collections.abc import Awaitable
from typing import Any, cast

from redis.asyncio import Redis

CACHE_KEY_PREFIX = "search:cache:"


def normalize_query(query: str) -> str:
    """검색 질의를 캐시 키로 쓸 수 있게 정규화한다: 소문자화 + 연속 공백 정리."""
    return re.sub(r"\s+", " ", query.strip().lower())


def _cache_key(normalized_query: str) -> str:
    return f"{CACHE_KEY_PREFIX}{normalized_query}"


class SearchResultCache:
    """웹 검색 결과를 질의 기준으로 캐싱한다. TTL 만료 후에는 다시 검색해야 한다."""

    def __init__(self, redis: Redis, *, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    async def get(self, query: str) -> list[dict[str, Any]] | None:
        """캐시된 검색 결과를 반환한다. 캐시 미스면 None."""
        key = _cache_key(normalize_query(query))
        raw = await cast("Awaitable[str | None]", self._redis.get(key))
        if raw is None:
            return None
        return cast(list[dict[str, Any]], json.loads(raw))

    async def set(self, query: str, results: list[dict[str, Any]]) -> None:
        """검색 결과를 캐싱한다. TTL이 지나면 자동 만료된다."""
        key = _cache_key(normalize_query(query))
        await cast(
            "Awaitable[bool]",
            self._redis.set(key, json.dumps(results), ex=self._ttl_seconds),
        )
