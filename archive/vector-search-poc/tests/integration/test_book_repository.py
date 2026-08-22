"""BookRepository의 upsert 멱등성과 벡터/하이브리드 검색을 실제 PostgreSQL로 검증한다."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from discovery.domain.book.models import Book
from discovery.infrastructure.persistence.book_repository import (
    BookRepository,
    BookUpsertData,
)

pytestmark = pytest.mark.integration


def _make_upsert_data(book_id: str, seed: float, description: str = "설명") -> BookUpsertData:
    vector = [0.0] * 1536
    vector[0] = seed
    vector[1] = 1.0 - seed
    return BookUpsertData(
        book_id=book_id,
        title=f"제목-{book_id}",
        author="저자",
        description=description,
        category="카테고리",
        embedding=vector,
        synced_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_upsert_is_idempotent_on_book_id(db_session: AsyncSession) -> None:
    repo = BookRepository(db_session)

    await repo.upsert(_make_upsert_data("book-idem", seed=0.3, description="첫 버전"))
    await db_session.flush()

    await repo.upsert(_make_upsert_data("book-idem", seed=0.7, description="갱신된 버전"))
    await db_session.flush()

    count_result = await db_session.execute(
        select(func.count()).select_from(Book).where(Book.book_id == "book-idem")
    )
    assert count_result.scalar_one() == 1

    row_result = await db_session.execute(select(Book).where(Book.book_id == "book-idem"))
    book = row_result.scalar_one()
    assert book.description == "갱신된 버전"


@pytest.mark.asyncio
async def test_search_by_embedding_returns_book_summary_dto(db_session: AsyncSession) -> None:
    repo = BookRepository(db_session)
    await repo.upsert(_make_upsert_data("book-search", seed=0.5, description="검색 대상 도서"))
    await db_session.flush()

    query_vector = [0.0] * 1536
    query_vector[0] = 0.5
    query_vector[1] = 0.5

    results = await repo.search_by_embedding(query_vector, limit=5)

    assert any(r.book_id == "book-search" for r in results)
    found = next(r for r in results if r.book_id == "book-search")
    assert found.title == "제목-book-search"
    # BookSummary는 description을 포함하지 않는다 (목록용 경량 DTO).
    assert type(found).model_fields.get("description") is None


@pytest.mark.asyncio
async def test_hybrid_search_filters_by_keyword_in_addition_to_vector(
    db_session: AsyncSession,
) -> None:
    repo = BookRepository(db_session)
    await repo.upsert(
        _make_upsert_data("book-keyword-match", seed=0.5, description="비 오는 날 읽기 좋은 소설")
    )
    await repo.upsert(
        _make_upsert_data("book-keyword-nomatch", seed=0.5, description="맑은 날 산책")
    )
    await db_session.flush()

    query_vector = [0.0] * 1536
    query_vector[0] = 0.5
    query_vector[1] = 0.5

    vector_only = await repo.search_by_embedding(query_vector, limit=10)
    vector_only_ids = {r.book_id for r in vector_only}
    assert "book-keyword-match" in vector_only_ids
    assert "book-keyword-nomatch" in vector_only_ids

    hybrid = await repo.search_by_embedding(
        query_vector, limit=10, use_hybrid_search=True, keyword_query="비"
    )
    hybrid_ids = {r.book_id for r in hybrid}
    assert "book-keyword-match" in hybrid_ids
    assert "book-keyword-nomatch" not in hybrid_ids


@pytest.mark.asyncio
async def test_hybrid_search_without_keyword_query_raises(db_session: AsyncSession) -> None:
    repo = BookRepository(db_session)
    query_vector = [0.0] * 1536

    with pytest.raises(ValueError, match="keyword_query"):
        await repo.search_by_embedding(query_vector, use_hybrid_search=True)
