"""ChatSessionStore의 순서 보장, LTRIM 상한, TTL(sliding window), clear 동작을
실제 Redis 컨테이너로 검증한다.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from testcontainers.redis import RedisContainer

from discovery.infrastructure.cache.chat_session_store import ChatSessionStore

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def redis_container() -> AsyncGenerator[RedisContainer]:  # type: ignore[misc]
    with RedisContainer("redis:7-alpine") as container:
        yield container


@pytest_asyncio.fixture
async def redis_client(redis_container: RedisContainer) -> AsyncGenerator[Redis]:
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    client: Redis = Redis(host=host, port=int(port), decode_responses=True)
    try:
        yield client
    finally:
        await client.flushall()
        await client.aclose()


def _make_store(
    redis_client: Redis, *, max_turns: int = 20, ttl_seconds: int = 3600
) -> ChatSessionStore:
    return ChatSessionStore(redis_client, max_turns=max_turns, ttl_seconds=ttl_seconds)


@pytest.mark.asyncio
async def test_append_and_get_history_preserves_order(redis_client: Redis) -> None:
    store = _make_store(redis_client)
    session_id = "session-order"

    await store.append_turn(session_id, {"role": "user", "content": "첫 번째"})
    await store.append_turn(session_id, {"role": "assistant", "content": "두 번째"})
    await store.append_turn(session_id, {"role": "user", "content": "세 번째"})

    history = await store.get_history(session_id)

    assert [turn["content"] for turn in history] == ["첫 번째", "두 번째", "세 번째"]


@pytest.mark.asyncio
async def test_append_turn_trims_history_to_max_turns(redis_client: Redis) -> None:
    store = _make_store(redis_client, max_turns=3)
    session_id = "session-trim"

    for i in range(5):
        await store.append_turn(session_id, {"role": "user", "content": f"turn-{i}"})

    history = await store.get_history(session_id)

    assert len(history) == 3
    assert [turn["content"] for turn in history] == ["turn-2", "turn-3", "turn-4"]


@pytest.mark.asyncio
async def test_append_turn_sets_ttl(redis_client: Redis) -> None:
    store = _make_store(redis_client, ttl_seconds=120)
    session_id = "session-ttl"

    await store.append_turn(session_id, {"role": "user", "content": "안녕"})

    ttl = await redis_client.ttl(f"chat:session:{session_id}")

    assert 0 < ttl <= 120


@pytest.mark.asyncio
async def test_clear_removes_history(redis_client: Redis) -> None:
    store = _make_store(redis_client)
    session_id = "session-clear"
    await store.append_turn(session_id, {"role": "user", "content": "지워질 메시지"})

    await store.clear(session_id)
    history = await store.get_history(session_id)

    assert history == []
