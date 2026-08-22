"""SyncService의 임베딩 텍스트 조립과 반환 DTO를 mocker로 검증한다.

AGENTS.md 테스트 원칙: 반환값을 우선 검증하고, 부작용(upsert/commit 호출)은
assert_called_once() 등으로 제한적으로만 확인한다.
"""

from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from discovery.api.schemas.sync import SyncBookRequest, SyncBookResponse
from discovery.application.sync_service import SyncService
from discovery.infrastructure.llm.protocols import EmbeddingClient
from discovery.infrastructure.persistence.book_repository import BookUpsertData


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 8, 21, 12, 0, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_sync_assembles_embedding_text_from_title_author_description_category(
    mocker: MockerFixture, fixed_now: datetime
) -> None:
    session = mocker.AsyncMock()
    embedding_client = mocker.Mock(spec=EmbeddingClient)
    embedding_client.embed.return_value = [[0.1, 0.2, 0.3]]
    mocker.patch(
        "discovery.application.sync_service.BookRepository.upsert",
        new_callable=AsyncMock,
    )

    service = SyncService(session, embedding_client, now=lambda: fixed_now)
    payload = SyncBookRequest(
        book_id="bk-1",
        title="제목",
        author="저자",
        description="설명",
        category="카테고리",
    )

    await service.sync(payload)

    embedding_client.embed.assert_called_once_with(["제목 저자 설명 카테고리"])


@pytest.mark.asyncio
async def test_sync_returns_book_id_and_synced_at(
    mocker: MockerFixture, fixed_now: datetime
) -> None:
    session = mocker.AsyncMock()
    embedding_client = mocker.Mock(spec=EmbeddingClient)
    embedding_client.embed.return_value = [[0.1, 0.2, 0.3]]
    mocker.patch(
        "discovery.application.sync_service.BookRepository.upsert",
        new_callable=AsyncMock,
    )

    service = SyncService(session, embedding_client, now=lambda: fixed_now)
    payload = SyncBookRequest(book_id="bk-1", title="제목", author="저자")

    result = await service.sync(payload)

    assert result == SyncBookResponse(book_id="bk-1", synced_at=fixed_now)


@pytest.mark.asyncio
async def test_sync_commits_after_upsert(mocker: MockerFixture, fixed_now: datetime) -> None:
    session = mocker.AsyncMock()
    embedding_client = mocker.Mock(spec=EmbeddingClient)
    embedding_client.embed.return_value = [[0.1, 0.2, 0.3]]
    upsert_mock = mocker.patch(
        "discovery.application.sync_service.BookRepository.upsert",
        new_callable=AsyncMock,
    )

    service = SyncService(session, embedding_client, now=lambda: fixed_now)
    payload = SyncBookRequest(book_id="bk-1", title="제목", author="저자")

    await service.sync(payload)

    upsert_mock.assert_called_once()
    called_data = cast(BookUpsertData, upsert_mock.call_args.args[0])
    assert called_data.book_id == "bk-1"
    assert called_data.embedding == [0.1, 0.2, 0.3]
    session.commit.assert_called_once()
