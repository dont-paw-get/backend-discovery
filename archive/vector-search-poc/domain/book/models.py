"""도서 읽기 모델(CQRS Read Model). Basic API가 소유한 원본 데이터의 비정규화 복제본이다.

.harness/DECISIONS.md 참고: mood_tags/genre_tags/color_tags 컬럼은 만들지 않는다.
category는 파싱 없이 원본 TEXT로 저장하고 임베딩·전문검색 대상 텍스트에 포함한다.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, DateTime, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from discovery.db.base import Base

EMBEDDING_DIM = 1536

# description + category를 결합해 tsvector로 계산하는 PostgreSQL generated column 표현식.
# STORED로 지정해 upsert 시 애플리케이션 코드가 search_vector 값을 직접 넣지 않아도
# DB가 항상 최신 상태로 유지한다 (트리거보다 누락 위험이 낮다).
SEARCH_VECTOR_EXPRESSION = (
    "to_tsvector('simple', coalesce(description, '') || ' ' || coalesce(category, ''))"
)


class Book(Base):
    """읽기 전용 복제 도서 모델. Basic API의 도서 데이터를 동기화해 저장한다."""

    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(Text, nullable=False, default="")
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR, Computed(SEARCH_VECTOR_EXPRESSION, persisted=True), nullable=False
    )
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # HNSW(embedding), GIN(search_vector) 인덱스는 alembic 마이그레이션에서만 생성한다.
    # create_all()을 쓰지 않으므로(AGENTS.md DB 정책) 여기서는 인덱스를 중복 선언하지 않는다.
