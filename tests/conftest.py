"""공용 테스트 픽스처.

AGENTS.md 통합 테스트 구조 정책:
- Repository 계층 테스트 → `db_session` (Testcontainers, function-scope, savepoint 롤백)
- E2E/API 계층 테스트 → `client` (httpx.AsyncClient, DI 오버라이드)
- 스키마는 `Base.metadata.create_all()`이 아니라 `alembic upgrade head`로 생성한다.
"""

import os
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from alembic import command
from alembic.config import Config
from discovery.api.deps import get_db_session
from discovery.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _to_asyncpg_url(sync_url: str) -> str:
    """testcontainers가 주는 psycopg2 URL을 asyncpg용으로 변환한다."""
    return sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer]:
    """세션 전체에서 재사용하는 PostgreSQL(pgvector) 컨테이너."""
    with PostgresContainer("pgvector/pgvector:pg16") as container:
        yield container


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    return _to_asyncpg_url(postgres_container.get_connection_url())


@pytest.fixture(scope="session", autouse=True)
def _run_migrations(database_url: str) -> None:
    """컨테이너 기동 후 `alembic upgrade head`로 실제 마이그레이션 스크립트를 검증한다."""
    os.environ["DATABASE_URL"] = database_url
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("INTERNAL_API_TOKEN", "test-token")

    alembic_cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_cfg, "head")


@pytest_asyncio.fixture
async def db_session(database_url: str) -> AsyncGenerator[AsyncSession]:
    """function-scope 세션. 매 테스트를 트랜잭션+savepoint로 감싸고 끝나면 롤백한다."""
    engine = create_async_engine(database_url)
    connection = await engine.connect()
    transaction = await connection.begin()

    session_factory = async_sessionmaker(bind=connection, expire_on_commit=False)
    session = session_factory()

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()
        await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """`get_db_session` 의존성을 테스트용 `db_session`으로 오버라이드한 E2E 클라이언트."""
    app = create_app()

    async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_get_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
