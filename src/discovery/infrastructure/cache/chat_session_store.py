"""Redis 기반 대화 세션 스토어. 세션당 하나의 List(`chat:session:{session_id}`)에
turn을 JSON 문자열로 RPUSH하고, LTRIM으로 최근 N턴만 유지한다.

TTL은 sliding window 방식이다 — append_turn마다 EXPIRE를 갱신해 활성 대화는
계속 유지하고, 방치된 세션만 자동 만료시킨다 (.harness/DECISIONS.md 참고).
session_id는 이 스토어가 생성하지 않는다. 호출자(라우터 의존성 등)가 결정론적으로
발급해 주입해야 테스트가 예측 가능하다 (AGENTS.md 테스트 작성 원칙).
"""

import json
from collections.abc import Awaitable
from typing import cast

from redis.asyncio import Redis

SESSION_KEY_PREFIX = "chat:session:"


def _session_key(session_id: str) -> str:
    return f"{SESSION_KEY_PREFIX}{session_id}"


class ChatSessionStore:
    """멀티턴 대화 문맥을 TTL과 함께 저장·조회하는 스토어."""

    def __init__(self, redis: Redis, *, max_turns: int, ttl_seconds: int) -> None:
        self._redis = redis
        self._max_turns = max_turns
        self._ttl_seconds = ttl_seconds

    async def append_turn(self, session_id: str, turn: dict[str, str]) -> None:
        """turn을 세션 히스토리 끝에 추가하고, 최근 N턴만 유지, TTL을 갱신한다."""
        key = _session_key(session_id)
        # redis-py의 비동기 클라이언트 메서드는 `Awaitable[T] | T`로 선언되어 있어
        # (sync/async 겸용 시그니처), 런타임에는 항상 코루틴이지만 정적으로는 모호하다.
        # cast로 실제 반환 타입을 명시해 mypy가 await 대상을 인식하게 한다.
        await cast("Awaitable[int]", self._redis.rpush(key, json.dumps(turn)))
        await cast("Awaitable[str]", self._redis.ltrim(key, -self._max_turns, -1))
        await cast("Awaitable[bool]", self._redis.expire(key, self._ttl_seconds))

    async def get_history(self, session_id: str) -> list[dict[str, str]]:
        """세션의 전체(최대 max_turns개) 히스토리를 오래된 것부터 순서대로 반환한다."""
        key = _session_key(session_id)
        raw_turns = await cast(
            "Awaitable[list[str]]", self._redis.lrange(key, 0, -1)
        )
        return [json.loads(raw_turn) for raw_turn in raw_turns]

    async def clear(self, session_id: str) -> None:
        """세션 히스토리를 완전히 삭제한다."""
        await cast("Awaitable[int]", self._redis.delete(_session_key(session_id)))
