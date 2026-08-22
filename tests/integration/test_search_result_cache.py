"""SearchResultCache의 TTL·정규화 동작을 실제 Redis로 검증한다."""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from testcontainers.redis import RedisContainer

from discovery.infrastructure.search.result_cache import SearchResultCache, normalize_query

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


def test_normalize_query_lowercases_and_collapses_whitespace() -> None:
    assert normalize_query("  비 오는 날   소설  ") == "비 오는 날 소설"
    assert normalize_query("Warm Novel") == "warm novel"


@pytest.mark.asyncio
async def test_cache_miss_returns_none(redis_client: Redis) -> None:
    cache = SearchResultCache(redis_client, ttl_seconds=86400)

    result = await cache.get("없는 질의")

    assert result is None


@pytest.mark.asyncio
async def test_cache_set_then_get_returns_stored_results(redis_client: Redis) -> None:
    cache = SearchResultCache(redis_client, ttl_seconds=86400)
    results = [{"title": "따뜻한 소설", "url": "https://example.com"}]

    await cache.set("비 오는 날 소설", results)
    cached = await cache.get("비 오는 날 소설")

    assert cached == results


@pytest.mark.asyncio
async def test_cache_get_normalizes_query_before_lookup(redis_client: Redis) -> None:
    cache = SearchResultCache(redis_client, ttl_seconds=86400)
    results = [{"title": "따뜻한 소설"}]

    await cache.set("Warm Novel", results)
    cached = await cache.get("  warm   novel  ")

    assert cached == results


@pytest.mark.asyncio
async def test_cache_entry_expires_after_ttl(redis_client: Redis) -> None:
    cache = SearchResultCache(redis_client, ttl_seconds=1)

    await cache.set("곧 만료될 질의", [{"title": "결과"}])
    ttl = await redis_client.ttl("search:cache:곧 만료될 질의")

    assert 0 < ttl <= 1
