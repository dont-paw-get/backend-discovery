"""`books` 테이블(HNSW/GIN 인덱스, search_vector generated column)이
실제 PostgreSQL에서 마이그레이션대로 동작하는지 검증한다.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from discovery.domain.book.models import Book

pytestmark = pytest.mark.integration


def _make_book(book_id: str, title: str, description: str, category: str, seed: float) -> Book:
    # 결정론적이고 방향이 다른 두 벡터를 만들기 위해 seed로 첫 두 차원만 다르게 채운다.
    vector = [0.0] * 1536
    vector[0] = seed
    vector[1] = 1.0 - seed
    return Book(
        book_id=book_id,
        title=title,
        author="Test Author",
        description=description,
        category=category,
        embedding=vector,
        synced_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_search_vector_is_generated_from_description_and_category(
    db_session: AsyncSession,
) -> None:
    book = _make_book(
        book_id="book-1",
        title="비 오는 날의 서재",
        description="따뜻한 위로가 되는 소설",
        category="문학",
        seed=1.0,
    )
    db_session.add(book)
    await db_session.flush()

    result = await db_session.execute(
        text(
            "SELECT search_vector @@ to_tsquery('simple', '위로가') "
            "FROM books WHERE book_id = :bid"
        ),
        {"bid": "book-1"},
    )
    assert result.scalar_one() is True

    result_no_match = await db_session.execute(
        text(
            "SELECT search_vector @@ to_tsquery('simple', '존재하지않는단어') "
            "FROM books WHERE book_id = :bid"
        ),
        {"bid": "book-1"},
    )
    assert result_no_match.scalar_one() is False


@pytest.mark.asyncio
async def test_embedding_cosine_distance_orders_by_similarity(db_session: AsyncSession) -> None:
    close_book = _make_book("book-close", "가까운 책", "설명", "카테고리", seed=0.9)
    far_book = _make_book("book-far", "먼 책", "설명", "카테고리", seed=0.1)
    db_session.add_all([close_book, far_book])
    await db_session.flush()

    query_vector = [0.0] * 1536
    query_vector[0] = 0.95
    query_vector[1] = 0.05

    result = await db_session.execute(
        text(
            "SELECT book_id FROM books "
            "WHERE book_id IN ('book-close', 'book-far') "
            "ORDER BY embedding <=> CAST(:query_vector AS vector) LIMIT 2"
        ),
        {"query_vector": str(query_vector)},
    )
    ordered_ids = [row[0] for row in result.all()]

    assert ordered_ids == ["book-close", "book-far"]


@pytest.mark.asyncio
async def test_hnsw_and_gin_indexes_exist(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename = 'books' AND indexname IN "
            "('ix_books_embedding_hnsw', 'ix_books_search_vector_gin')"
        )
    )
    indexes = {row.indexname: row.indexdef for row in result.all()}

    assert "ix_books_embedding_hnsw" in indexes
    assert "hnsw" in indexes["ix_books_embedding_hnsw"].lower()
    assert "ix_books_search_vector_gin" in indexes
    assert "gin" in indexes["ix_books_search_vector_gin"].lower()


@pytest.mark.asyncio
async def test_explain_uses_gin_index_for_search_vector(db_session: AsyncSession) -> None:
    book = _make_book("book-explain", "탐색 대상 책", "탐색용 설명", "카테고리", seed=0.5)
    db_session.add(book)
    await db_session.flush()

    # 플래너가 소량 데이터에서는 인덱스를 안 쓸 수 있어, enable_seqscan을 꺼서
    # 인덱스가 "사용 가능한 상태"인지(플랜에 등장하는지)를 확인한다.
    await db_session.execute(text("SET LOCAL enable_seqscan = off"))
    result = await db_session.execute(
        text(
            "EXPLAIN SELECT * FROM books "
            "WHERE search_vector @@ to_tsquery('simple', '탐색')"
        )
    )
    plan = "\n".join(row[0] for row in result.all())

    assert "ix_books_search_vector_gin" in plan
