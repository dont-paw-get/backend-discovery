"""도서 읽기 모델 리포지토리. AsyncSession 컨텍스트가 닫히기 전에 Pydantic DTO로
파싱을 완료해 MissingGreenlet을 원천 차단한다 (AGENTS.md ORM/DTO 직렬화 정책).
"""

from datetime import datetime

from sqlalchemy import Select, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from discovery.api.schemas.book import BookSummary
from discovery.domain.book.models import Book


class BookUpsertData:
    """upsert에 필요한 필드만 담는 입력 DTO. embedding은 애플리케이션이 계산해 전달한다."""

    def __init__(
        self,
        *,
        book_id: str,
        title: str,
        author: str,
        description: str,
        category: str,
        embedding: list[float],
        synced_at: datetime,
    ) -> None:
        self.book_id = book_id
        self.title = title
        self.author = author
        self.description = description
        self.category = category
        self.embedding = embedding
        self.synced_at = synced_at


class BookRepository:
    """`books` 테이블에 대한 조회/저장을 캡슐화한다."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, data: BookUpsertData) -> None:
        """`book_id` 기준으로 upsert한다. search_vector는 generated column이라 직접 넣지 않는다."""
        stmt = pg_insert(Book).values(
            book_id=data.book_id,
            title=data.title,
            author=data.author,
            description=data.description,
            category=data.category,
            embedding=data.embedding,
            synced_at=data.synced_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Book.book_id],
            set_={
                "title": stmt.excluded.title,
                "author": stmt.excluded.author,
                "description": stmt.excluded.description,
                "category": stmt.excluded.category,
                "embedding": stmt.excluded.embedding,
                "synced_at": stmt.excluded.synced_at,
            },
        )
        await self._session.execute(stmt)

    async def search_by_embedding(
        self,
        query_embedding: list[float],
        *,
        limit: int = 10,
        use_hybrid_search: bool = False,
        keyword_query: str | None = None,
    ) -> list[BookSummary]:
        """벡터 유사도 검색. `use_hybrid_search=True`면 키워드(search_vector) 매칭도 결합한다.

        기본값은 벡터 단독 검색이다 (.harness/DECISIONS.md 참고 — 하이브리드 효과가
        실사용 데이터로 검증되지 않아 옵션으로만 제공한다).
        """
        query: Select[tuple[Book]] = select(Book).order_by(
            Book.embedding.cosine_distance(query_embedding)
        )

        if use_hybrid_search:
            if not keyword_query:
                raise ValueError("use_hybrid_search=True이면 keyword_query가 필요하다")
            query = query.where(
                text("search_vector @@ to_tsquery('simple', :keyword_query)")
            ).params(keyword_query=keyword_query)

        query = query.limit(limit)

        result = await self._session.execute(query)
        books = result.scalars().all()

        # 세션이 닫히기 전에 DTO로 완전히 파싱한다 (MissingGreenlet 원천 차단).
        return [BookSummary.model_validate(book) for book in books]
