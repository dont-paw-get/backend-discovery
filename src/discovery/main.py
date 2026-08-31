from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from discovery.api.v1.routers.chat import router as chat_router
from discovery.api.v1.routers.genre import router as genre_router
from discovery.core.config import get_settings
from discovery.infrastructure.cache.redis_client import create_redis_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()
    app.state.redis = create_redis_client(settings)
    try:
        yield
    finally:
        await app.state.redis.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="DPYB Discovery API",
        description="도서 탐색 및 AI 추천 에이전트 서비스",
        version="0.4.0",
        lifespan=lifespan,
    )

    # 프론트엔드 로컬 개발 및 배포 도메인 연동을 위한 CORS 설정
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Session-Id", "X-Signals", "X-Switch-To"],
    )

    @app.get("/health", tags=["Health"])
    @app.get("/api/v1/health", tags=["Health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(genre_router, prefix="/api/v1")

    return app


app = create_app()
