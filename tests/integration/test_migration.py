"""Alembic 마이그레이션과 pgvector 확장이 실제 PostgreSQL에서 정상 적용되는지 검증."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_alembic_upgrade_head_enables_vector_extension(db_session: AsyncSession) -> None:
    """conftest의 session-scope 픽스처가 `alembic upgrade head`를 이미 실행했다.
    여기서는 그 결과(vector 확장이 활성화됐는지)만 검증한다.
    """
    result = await db_session.execute(
        text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'")
    )
    row = result.one()

    assert row.extname == "vector"
    assert row.extversion is not None
