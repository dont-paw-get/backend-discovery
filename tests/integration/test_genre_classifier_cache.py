"""GenreClassifierCache의 TTL 동작을 실제 Redis로 검증한다."""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from testcontainers.redis import RedisContainer

from discovery.infrastructure.cache.genre_classifier_cache import GenreClassifierCache

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


@pytest.mark.asyncio
async def test_cache_miss_returns_none(redis_client: Redis) -> None:
    cache = GenreClassifierCache(redis_client, ttl_seconds=86400)

    result = await cache.get("9788932917245")

    assert result is None


@pytest.mark.asyncio
async def test_cache_set_then_get_returns_stored_genre_and_confidence(
    redis_client: Redis,
) -> None:
    cache = GenreClassifierCache(redis_client, ttl_seconds=86400)

    await cache.set("9788932917245", "LITERARY_FICTION", 0.95)
    cached = await cache.get("9788932917245")

    assert cached == ("LITERARY_FICTION", 0.95)


@pytest.mark.asyncio
async def test_cache_entry_expires_after_ttl(redis_client: Redis) -> None:
    cache = GenreClassifierCache(redis_client, ttl_seconds=1)

    await cache.set("9788932917245", "LITERARY_FICTION", 0.95)
    ttl = await redis_client.ttl("genre:classification:9788932917245")

    assert 0 < ttl <= 1
