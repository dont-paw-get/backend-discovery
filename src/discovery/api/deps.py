"""FastAPI 의존성 주입 지점. 테스트에서 이 함수들을 오버라이드해 실제 인프라를 대체한다."""

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession]:
    """요청 스코프 DB 세션. app.state.session_factory(lifespan에서 생성)를 사용한다."""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session
