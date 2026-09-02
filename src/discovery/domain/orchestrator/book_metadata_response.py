"""도서 서지 조회 API 응답 DTO.

backend-book의 두 가지 서지 조회 엔드포인트에 대응한다:

1. `GET /api/v1/books/search?isbn=...` (`BookMetadataSearchResponse`) — ISBN 단건 조회.
   서재에 이미 등록된 도서면 `alreadyRegistered=true` + `libraryBook`으로, 아니면
   `alreadyRegistered=false` + `book`으로 응답한다. 현재 추천 파이프라인에서는 더 이상
   호출하지 않지만(CLIAR-237 후속으로 title/author 기반 조회로 통일), 클라이언트
   메서드(`fetch_total_pages`)는 향후 재사용 가능성을 위해 유지한다.
2. `GET /api/v1/books/search/by-title-author` (`BookSearchByTitleAuthorResponse`) —
   제목·저자 교집합 검색. 서재 등록 여부를 확인하지 않는 순수 외부 검색이라
   `alreadyRegistered`/`libraryBook` 분기가 없고, 교집합이 없으면 `book` 필드 자체가
   응답에서 생략된다.

`libraryBook`의 정확한 필드명이 아직 실측되지 않았으므로, `book`과 동일한 스키마라고
가정하고 방어적으로 파싱한다(`extra="ignore"` + 전 필드 옵셔널). 실제 필드명이 다르면
`total_pages`를 못 찾아 `None`이 될 뿐 예외를 던지지 않는다.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = ["BookMetadata", "BookMetadataSearchResponse", "BookSearchByTitleAuthorResponse"]


class BookMetadata(BaseModel):
    """알라딘 조회 결과 또는 서재에 이미 등록된 도서의 서지 정보.

    이 티켓에서는 `total_pages`만 사용하지만, 향후 확장을 대비해 알려진 필드를
    함께 정의해둔다.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        extra="ignore",
    )

    title: str | None = Field(default=None, description="도서 제목")
    author: str | None = Field(default=None, description="저자명")
    isbn: str | None = Field(default=None, description="ISBN")
    publisher: str | None = Field(default=None, description="출판사")
    total_pages: int | None = Field(
        default=None, alias="totalPages", description="총 페이지 수 (알라딘 실측값)"
    )


class BookMetadataSearchResponse(BaseModel):
    """`GET /api/v1/books/search?isbn=...` 응답 DTO."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        extra="ignore",
    )

    already_registered: bool = Field(default=False, alias="alreadyRegistered")
    book: BookMetadata | None = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def normalize_library_book(cls, data: object) -> object:
        """`libraryBook`(서재 기존 등록 도서) 키를 `book`으로 통일해 단일 필드로 처리한다.

        `libraryBook`의 정확한 스키마는 아직 실측되지 않았으므로, `book`과 동일한
        구조라고 가정한다. 두 키가 동시에 있으면 `book`을 우선한다.
        """
        if not isinstance(data, dict):
            return data
        if "book" not in data and "libraryBook" in data:
            result = dict(data)
            result["book"] = data["libraryBook"]
            return result
        return data

    @property
    def total_pages(self) -> int | None:
        """조회된 도서의 총 페이지 수. `book`이 없거나 페이지수 정보가 없으면 `None`."""
        if self.book is None:
            return None
        return self.book.total_pages


class BookSearchByTitleAuthorResponse(BaseModel):
    """`GET /api/v1/books/search/by-title-author` 응답 DTO.

    제목으로 1회, 저자로 1회 알라딘 검색을 수행해 교집합(isbn13 동일) 중 제목 검색
    결과 기준 최상단 1권만 `book`으로 반환한다. 교집합이 없거나 한쪽 검색 결과가
    없으면 `book` 필드 자체가 응답에서 생략된다(수동 입력 폴백 케이스).
    """

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        extra="ignore",
    )

    book: BookMetadata | None = Field(default=None)

    @property
    def total_pages(self) -> int | None:
        """검색된 도서의 총 페이지 수. `book`이 없으면 `None`."""
        return self.book.total_pages if self.book else None

    @property
    def isbn(self) -> str | None:
        """검색된 도서의 ISBN. `book`이 없으면 `None`."""
        return self.book.isbn if self.book else None
