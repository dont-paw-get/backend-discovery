"""Redis 비동기 커넥션 풀 생성. FastAPI lifespan에서 생성/정리한다."""

from typing import cast

from redis.asyncio import Redis

from discovery.core.config import Settings


def create_redis_client(settings: Settings) -> Redis:
    return cast(Redis, Redis.from_url(settings.redis_url, decode_responses=True))
