"""서재 도서 조회 API(GET /api/v1/library/books) 응답 DTO."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = ["LibraryBookItem", "LibraryBooksResponse"]


class LibraryBookItem(BaseModel):
    """서재에 등록된 도서 항목 DTO."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        extra="ignore",
    )

    book_id: int | str = Field(default=0, alias="bookId", description="도서 식별자")
    shelf_id: int | str | None = Field(default=None, alias="shelfId", description="책장 식별자")
    shelf_rank: str | int | None = Field(
        default=None, alias="shelfRank", description="책장 내 순서 랭크"
    )
    title: str = Field(default="", description="도서 제목")
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

    @field_validator("progress", mode="before")
    @classmethod
    def convert_progress_to_int(cls, v: Any) -> int | None:
        """소수점 진행률(예: 88.0165...)을 정수 퍼센트(88)로 반올림 변환한다."""
        if v is None:
            return None
        try:
            return int(round(float(v)))
        except (ValueError, TypeError):
            return None


class LibraryBooksResponse(BaseModel):
    """서재 도서 목록 조회 응답 DTO."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        extra="ignore",
    )

    books: list[LibraryBookItem] = Field(default_factory=list, description="서재 도서 목록")
    page: int = Field(default=0, description="현재 페이지 번호")
    size: int = Field(default=100, description="페이지 크기")
    total_elements: int = Field(default=0, alias="totalElements", description="전체 도서 수")
    total_pages: int = Field(default=0, alias="totalPages", description="전체 페이지 수")

    @model_validator(mode="before")
    @classmethod
    def extract_books_from_various_formats(cls, data: Any) -> Any:
        """Spring Data Page(content), books, data 래핑, 순수 배열 등 모든 형태를 수용한다."""
        if isinstance(data, list):
            return {"books": data, "totalElements": len(data), "totalPages": 1}

        if isinstance(data, dict):
            # 1) Spring Data Page 표준 'content' 필드
            if "content" in data and isinstance(data["content"], list):
                result = dict(data)
                result["books"] = data["content"]
                return result

            # 2) ApiResponse 래핑 구조 (예: {"data": [...] 또는 {"data": {"books": ...}}})
            if "data" in data:
                inner = data["data"]
                if isinstance(inner, list):
                    return {"books": inner, "totalElements": len(inner), "totalPages": 1}
                if isinstance(inner, dict):
                    if "books" in inner and isinstance(inner["books"], list):
                        return inner
                    if "content" in inner and isinstance(inner["content"], list):
                        result = dict(inner)
                        result["books"] = inner["content"]
                        return result
                    if "items" in inner and isinstance(inner["items"], list):
                        result = dict(inner)
                        result["books"] = inner["items"]
                        return result

            # 3) 'items' 필드
            if "items" in data and isinstance(data["items"], list):
                result = dict(data)
                result["books"] = data["items"]
                return result

        return data
