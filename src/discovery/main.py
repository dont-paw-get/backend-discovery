"""FastAPI 애플리케이션 진입점.

로깅: `configure_json_logging`이 루트 로거를 stdout JSON 핸들러로 재구성하고
`discovery.*` 로거를 INFO로 올린다 (uvicorn 기본 effective level WARNING 회피).
각 로그에는 활성 span의 trace_id/span_id가 주입된다.

트레이싱: `configure_tracing`은 `OTEL_EXPORTER_OTLP_ENDPOINT`가 설정된 경우에만
OTLP exporter를 붙인다. 미설정(로컬)에서도 앱은 정상 기동한다. 자세한 내용은
`core/tracing.py` 참고.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from discovery.api.v1.routers.chat import router as chat_router
from discovery.api.v1.routers.genre import router as genre_router
from discovery.core.config import get_settings
from discovery.core.logging import configure_json_logging
from discovery.core.tracing import configure_tracing, instrument_fastapi_app
from discovery.infrastructure.cache.redis_client import create_redis_client

# stdout JSON 로깅 (trace_id/span_id 자동 주입).
configure_json_logging(service_name="backend-discovery")

# OpenTelemetry 분산 트레이싱 초기화 (FastAPI app 생성 전, 자동 계측 적용을 위해).
configure_tracing()


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

    # OpenTelemetry 서버 span 계측 (health probe 제외). 다른 backend가 보낸
    # W3C traceparent를 이어받아 동일 Trace로 연결한다.
    instrument_fastapi_app(app)

    # 프론트엔드 로컬 개발 및 배포 도메인 연동을 위한 CORS 설정
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Session-Id", "X-Signals", "X-Switch-To", "X-Library-Books"],
    )

    @app.get("/health", tags=["Health"])
    @app.get("/api/v1/health", tags=["Health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(genre_router, prefix="/api/v1")

    return app


app = create_app()
