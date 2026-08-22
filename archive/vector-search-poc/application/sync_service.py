"""도서 동기화 서비스. Basic API가 보낸 단건 payload를 임베딩해 읽기 모델에 반영한다.

AGENTS.md 정책: 도메인은 계산까지만, 커밋 등 부작용은 이 서비스(application) 계층이 담당한다.
"""

from collections.abc import Callable
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from discovery.api.schemas.sync import SyncBookRequest, SyncBookResponse
from discovery.infrastructure.llm.protocols import EmbeddingClient
from discovery.infrastructure.persistence.book_repository import (
    BookRepository,
    BookUpsertData,
)


def _build_embedding_text(payload: SyncBookRequest) -> str:
    """임베딩 대상 텍스트를 조립한다: 제목+저자+설명+category."""
    return " ".join(
        part for part in (payload.title, payload.author, payload.description, payload.category)
    )


class SyncService:
    """`/internal/sync-book`의 유스케이스를 담당한다."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_client: EmbeddingClient,
        *,
        now: Callable[[], datetime],
    ) -> None:
        self._session = session
        self._embedding_client = embedding_client
        self._now = now

    async def sync(self, payload: SyncBookRequest) -> SyncBookResponse:
        """도서 데이터를 임베딩해 upsert하고 커밋한다. `book_id` 기준 멱등."""
        embedding_text = _build_embedding_text(payload)
        [embedding] = self._embedding_client.embed([embedding_text])

        synced_at = self._now()
        await self._repository.upsert(
            BookUpsertData(
                book_id=payload.book_id,
                title=payload.title,
                author=payload.author,
                description=payload.description,
                category=payload.category,
                embedding=embedding,
                synced_at=synced_at,
            )
        )
        await self._session.commit()

        return SyncBookResponse(book_id=payload.book_id, synced_at=synced_at)

    @property
    def _repository(self) -> BookRepository:
        return BookRepository(self._session)
