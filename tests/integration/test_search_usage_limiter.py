"""SearchUsageLimiter의 월간 카운터 증가·상한 판단·월별 키 분리를 실제 Redis로 검증한다."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from testcontainers.redis import RedisContainer

from discovery.infrastructure.search.usage_limiter import SearchUsageLimiter

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
async def test_is_limit_exceeded_returns_false_when_no_calls_made(redis_client: Redis) -> None:
    limiter = SearchUsageLimiter(redis_client, monthly_limit=900)
    now = datetime(2026, 8, 21, tzinfo=UTC)

    assert await limiter.is_limit_exceeded(now=now) is False


@pytest.mark.asyncio
async def test_increment_increases_count_and_sets_ttl(redis_client: Redis) -> None:
    limiter = SearchUsageLimiter(redis_client, monthly_limit=900)
    now = datetime(2026, 8, 21, tzinfo=UTC)

    first = await limiter.increment(now=now)
    second = await limiter.increment(now=now)

    assert first == 1
    assert second == 2
    ttl = await redis_client.ttl("search:usage:2026-08")
    assert ttl > 0


@pytest.mark.asyncio
async def test_is_limit_exceeded_true_after_reaching_monthly_limit(redis_client: Redis) -> None:
    limiter = SearchUsageLimiter(redis_client, monthly_limit=2)
    now = datetime(2026, 8, 21, tzinfo=UTC)

    await limiter.increment(now=now)
    await limiter.increment(now=now)

    assert await limiter.is_limit_exceeded(now=now) is True


@pytest.mark.asyncio
async def test_different_months_use_separate_counters(redis_client: Redis) -> None:
    limiter = SearchUsageLimiter(redis_client, monthly_limit=1)
    august = datetime(2026, 8, 21, tzinfo=UTC)
    september = datetime(2026, 9, 1, tzinfo=UTC)

    await limiter.increment(now=august)

    assert await limiter.is_limit_exceeded(now=august) is True
    assert await limiter.is_limit_exceeded(now=september) is False
