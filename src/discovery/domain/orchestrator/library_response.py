"""서재 도서 조회 API(GET /api/v1/library/books) 응답 DTO."""

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["LibraryBookItem", "LibraryBooksResponse"]


class LibraryBookItem(BaseModel):
    """서재에 등록된 도서 항목 DTO."""

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    book_id: int = Field(alias="bookId", description="도서 식별자")
    shelf_id: int | None = Field(default=None, alias="shelfId", description="책장 식별자")
    shelf_rank: str | None = Field(default=None, alias="shelfRank", description="책장 내 순서 랭크")
    title: str = Field(description="도서 제목")
    author: str | None = Field(default=None, description="저자명")
    genre: str | None = Field(default=None, description="도서 장르 (예: MYSTERY_THRILLER, SF 등)")
    reading_status: str | None = Field(
        default=None,
        alias="readingStatus",
        description="독서 상태 (예: READING, COMPLETED, WISH 등)",
    )
    cover_url: str | None = Field(
        default=None, alias="coverUrl", description="도서 표지 이미지 URL"
    )
    progress: int | None = Field(default=None, description="독서 진행률 (0~100 %)")


class LibraryBooksResponse(BaseModel):
    """서재 도서 목록 조회 응답 DTO."""

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    books: list[LibraryBookItem] = Field(default_factory=list, description="서재 도서 목록")
    page: int = Field(default=0, description="현재 페이지 번호")
    size: int = Field(default=20, description="페이지 크기")
    total_elements: int = Field(default=0, alias="totalElements", description="전체 도서 수")
    total_pages: int = Field(default=0, alias="totalPages", description="전체 페이지 수")
