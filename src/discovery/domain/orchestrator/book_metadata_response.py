"""도서 서지 조회 API(GET /api/v1/books/search?isbn=...) 응답 DTO.

backend-book이 알라딘 Open API를 실조회하여 반환하는 서지 정보 중, 이 티켓(CLIAR-237)
에서는 `totalPages`만 사용한다. 응답은 다음 세 가지 형태로 올 수 있다:

1. `alreadyRegistered=false` + `book`: 알라딘에서 신규 조회된 서지 정보.
2. `alreadyRegistered=true` + `libraryBook`(추정, 실측 전): 사용자가 이미 서재에
   등록한 도서라 알라딘 대신 저장된 데이터를 반환하는 경우.
3. `book`/`libraryBook` 모두 없음: 알라딘에도 없어 서지 정보를 확인할 수 없는 경우
   (수동 입력 폴백).

`libraryBook`의 정확한 필드명이 아직 실측되지 않았으므로, `book`과 동일한 스키마라고
가정하고 방어적으로 파싱한다(`extra="ignore"` + 전 필드 옵셔널). 실제 필드명이 다르면
`total_pages`를 못 찾아 `None`이 될 뿐 예외를 던지지 않는다.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = ["BookMetadata", "BookMetadataSearchResponse"]


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
