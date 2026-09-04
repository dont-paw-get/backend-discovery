"""서지 정보(ISBN, 페이지수) 캐시. Redis에 정규화한 제목·저자를 키로 결과를 TTL과
함께 저장한다.

CLIAR-282 Task 5: `verify_page_counts_ms` 구간에서 알라딘 2단계 조회
(`by-title-author`→ISBN→`search?isbn=`)가 매 요청 직렬로 발생해 1.3~5.3초 지연이
발생함을 dev 실측으로 확인했다. 출판된 도서의 ISBN·페이지수는 거의 불변 데이터이므로,
`SearchResultCache`(웹 검색 결과 캐시)와 동일한 패턴으로 캐싱해 재추천 시 외부 HTTP
호출을 완전히 건너뛴다.

조회 실패(네트워크 오류, 404 등)로 `(None, None)`이 나온 경우는 캐싱하지 않는다 —
일시적 오류를 TTL 기간 내내 실패로 고정시키지 않기 위함(graceful degradation 원칙 유지).
"""

import json
import re
from collections.abc import Awaitable
from typing import cast

from redis.asyncio import Redis

CACHE_KEY_PREFIX = "book:metadata:"


def normalize_field(value: str) -> str:
    """제목/저자 문자열을 캐시 키로 쓸 수 있게 정규화한다: 소문자화 + 연속 공백 정리."""
    return re.sub(r"\s+", " ", value.strip().lower())


def _cache_key(title: str, author: str) -> str:
    return f"{CACHE_KEY_PREFIX}{normalize_field(title)}:{normalize_field(author)}"


class BookMetadataCache:
    """제목·저자 기준으로 (ISBN, 페이지수)를 캐싱한다. TTL 만료 후에는 다시 조회해야 한다."""

    def __init__(self, redis: Redis, *, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    async def get(self, title: str, author: str) -> tuple[str | None, int | None] | None:
        """캐시된 (ISBN, 페이지수)를 반환한다. 캐시 미스면 None."""
        key = _cache_key(title, author)
        raw = await cast("Awaitable[str | None]", self._redis.get(key))
        if raw is None:
            return None
        data = json.loads(raw)
        return (data.get("isbn"), data.get("total_pages"))

    async def set(self, title: str, author: str, isbn: str | None, total_pages: int | None) -> None:
        """(ISBN, 페이지수)를 캐싱한다. TTL이 지나면 자동 만료된다."""
        key = _cache_key(title, author)
        payload = json.dumps({"isbn": isbn, "total_pages": total_pages})
        await cast("Awaitable[bool]", self._redis.set(key, payload, ex=self._ttl_seconds))
