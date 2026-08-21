"""FastAPI 애플리케이션 팩토리."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from discovery.core.config import get_settings
from discovery.db.session import create_engine, create_session_factory
from discovery.infrastructure.cache.redis_client import create_redis_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()
    engine = create_engine(settings)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.redis = create_redis_client(settings)
    try:
        yield
    finally:
        await app.state.redis.aclose()
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="DPYB Discovery API", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
