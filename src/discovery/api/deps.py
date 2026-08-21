"""FastAPI 의존성 주입 지점. 테스트에서 이 함수들을 오버라이드해 실제 인프라를 대체한다."""

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from discovery.core.config import get_settings
from discovery.infrastructure.llm.factory import (
    create_chat_completion_client,
    create_embedding_client,
)
from discovery.infrastructure.llm.protocols import ChatCompletionClient, EmbeddingClient


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession]:
    """요청 스코프 DB 세션. app.state.session_factory(lifespan에서 생성)를 사용한다."""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


def get_embedding_client() -> EmbeddingClient:
    """LLM_PROVIDER 설정에 따라 Mock 또는 Bedrock 임베딩 클라이언트를 반환한다."""
    return create_embedding_client(get_settings())


def get_chat_completion_client() -> ChatCompletionClient:
    """LLM_PROVIDER 설정에 따라 Mock 또는 Bedrock 챗 완성 클라이언트를 반환한다."""
    return create_chat_completion_client(get_settings())
