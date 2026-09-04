"""도서 표준 장르 분류 결과 캐시. Redis에 ISBN을 키로 분류 결과를 TTL과 함께 저장한다.

CLIAR-282 Task 5: `RecommendBooksTool._backfill_missing_genres`가 장르가 `NONE`인
도서마다 `GenreClassifierService.classify_genre`(Bedrock LLM 호출)를 재호출해 지연이
발생함을 dev 실측으로 확인했다. 같은 ISBN의 표준 장르는 불변 데이터이므로 캐싱해
재분류 시 LLM 호출을 완전히 건너뛴다.

이 캐시는 `GenreClassifierService`를 사용하는 두 경로(`POST /api/v1/classify-genre`
외부 API, `RecommendBooksTool` 내부 재사용) 모두에 적용되어 양쪽 응답 속도를 함께
개선한다.

분류 결과가 `NONE`(미식별)인 경우는 캐싱하지 않는다 — 프롬프트 개선이나 재시도로
나중에 더 정확한 분류가 나올 수 있는 불확실한 결과를 TTL 기간 내내 고정시키지 않기
위함(graceful degradation 원칙 유지, `BookMetadataCache`와 동일한 논리).
"""

import json
from collections.abc import Awaitable
from typing import cast

from redis.asyncio import Redis

CACHE_KEY_PREFIX = "genre:classification:"


def _cache_key(isbn: str) -> str:
    return f"{CACHE_KEY_PREFIX}{isbn.strip()}"


class GenreClassifierCache:
    """ISBN 기준으로 표준 장르 분류 결과를 캐싱한다. TTL 만료 후에는 다시 분류해야 한다."""

    def __init__(self, redis: Redis, *, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    async def get(self, isbn: str) -> tuple[str, float] | None:
        """캐시된 (장르, 신뢰도)를 반환한다. 캐시 미스면 None."""
        key = _cache_key(isbn)
        raw = await cast("Awaitable[str | None]", self._redis.get(key))
        if raw is None:
            return None
        data = json.loads(raw)
        return (data["genre"], data["confidence"])

    async def set(self, isbn: str, genre: str, confidence: float) -> None:
        """(장르, 신뢰도)를 캐싱한다. TTL이 지나면 자동 만료된다."""
        key = _cache_key(isbn)
        payload = json.dumps({"genre": genre, "confidence": confidence})
        await cast("Awaitable[bool]", self._redis.set(key, payload, ex=self._ttl_seconds))
