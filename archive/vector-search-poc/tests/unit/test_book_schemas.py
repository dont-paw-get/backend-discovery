"""BookSummary/BookDetail DTO의 직렬화 필드를 검증한다 (실제 DB 없이 동작하는 단위 테스트)."""

from datetime import UTC, datetime

from discovery.api.schemas.book import BookDetail, BookSummary


class _FakeBookRow:
    """ORM 객체 대신 사용하는 단순 속성 컨테이너. from_attributes=True 검증용."""

    def __init__(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_book_summary_excludes_description() -> None:
    row = _FakeBookRow(
        book_id="b1",
        title="제목",
        author="저자",
        description="긴 설명 텍스트",
        category="카테고리",
        synced_at=datetime.now(UTC),
    )

    dto = BookSummary.model_validate(row)

    assert dto.book_id == "b1"
    assert dto.title == "제목"
    assert not hasattr(dto, "description")


def test_book_detail_includes_description() -> None:
    row = _FakeBookRow(
        book_id="b1",
        title="제목",
        author="저자",
        description="긴 설명 텍스트",
        category="카테고리",
        synced_at=datetime.now(UTC),
    )

    dto = BookDetail.model_validate(row)

    assert dto.description == "긴 설명 텍스트"
