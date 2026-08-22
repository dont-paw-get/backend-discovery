"""`POST /internal/sync-book`을 실제 DB·FastAPI 라우팅을 통과시켜 검증한다."""

import os

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from discovery.domain.book.models import Book

pytestmark = pytest.mark.integration


def _payload(book_id: str = "bk-e2e-1") -> dict[str, str]:
    return {
        "book_id": book_id,
        "title": "제목",
        "author": "저자",
        "description": "설명",
        "category": "카테고리",
    }


@pytest.mark.asyncio
async def test_sync_book_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.post("/internal/sync-book", json=_payload())

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sync_book_with_wrong_token_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/internal/sync-book",
        json=_payload(),
        headers={"X-Internal-Token": "wrong-token"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sync_book_with_valid_token_creates_one_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    token = os.environ["INTERNAL_API_TOKEN"]

    response = await client.post(
        "/internal/sync-book",
        json=_payload("bk-e2e-2"),
        headers={"X-Internal-Token": token},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["book_id"] == "bk-e2e-2"

    result = await db_session.execute(select(Book).where(Book.book_id == "bk-e2e-2"))
    assert result.scalar_one() is not None


@pytest.mark.asyncio
async def test_sync_book_resent_is_idempotent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    token = os.environ["INTERNAL_API_TOKEN"]

    first = await client.post(
        "/internal/sync-book",
        json=_payload("bk-e2e-3"),
        headers={"X-Internal-Token": token},
    )
    second = await client.post(
        "/internal/sync-book",
        json=_payload("bk-e2e-3"),
        headers={"X-Internal-Token": token},
    )

    assert first.status_code == 200
    assert second.status_code == 200

    result = await db_session.execute(
        select(Book).where(Book.book_id == "bk-e2e-3")
    )
    books = result.scalars().all()
    assert len(books) == 1
