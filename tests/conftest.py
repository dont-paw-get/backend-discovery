"""공용 테스트 픽스처.

AGENTS.md 통합 테스트 구조 정책:
- E2E/API 계층 테스트 → `client` (httpx.AsyncClient)

PostgreSQL/SQLAlchemy/Alembic은 2026-08-21 방향 전환으로 backend-discovery에서
완전히 제거됐다 (`.harness/DECISIONS.md` 참고). 남은 인프라는 Redis(`ChatSessionStore`)뿐이라
DB 세션 관련 픽스처(`db_session`, `postgres_container` 등)는 더 이상 필요하지 않다.
"""

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from discovery.main import create_app


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    """E2E 테스트용 httpx.AsyncClient. 필요한 의존성은 테스트마다 오버라이드한다."""
    app = create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
