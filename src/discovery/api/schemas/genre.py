from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StandardGenre(str, Enum):
    """ERD/backend-book 도서 카테고리 표준 규격 (genre_type 16개 장르)."""

    NONE = "NONE"
    SCIENCE_FICTION = "SCIENCE_FICTION"
    FANTASY = "FANTASY"
    ROMANCE = "ROMANCE"
    MYSTERY_THRILLER = "MYSTERY_THRILLER"
    LITERARY_FICTION = "LITERARY_FICTION"
    ESSAY = "ESSAY"
    POETRY_DRAMA = "POETRY_DRAMA"
    HUMANITIES = "HUMANITIES"
    HISTORY = "HISTORY"
    BUSINESS_ECONOMICS = "BUSINESS_ECONOMICS"
    SELF_HELP = "SELF_HELP"
    SCIENCE = "SCIENCE"
    ARTS = "ARTS"
    RELIGION = "RELIGION"
    COMPUTER_IT = "COMPUTER_IT"


class BookClassificationRequest(BaseModel):
    """도서 표준 장르 분류 요청 스키마."""

    model_config = ConfigDict(from_attributes=True)

    isbn: str = Field(
        ...,
        min_length=1,
        description="국제표준도서번호 (10자리 또는 13자리 ISBN)",
        examples=["9788966263769"],
    )

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("ISBN은 공백일 수 없습니다.")
        return cleaned


class BookClassificationResponse(BaseModel):
    """도서 표준 장르 분류 응답 스키마."""

    model_config = ConfigDict(from_attributes=True)

    genre: StandardGenre = Field(
        ...,
        description="매핑된 backend-book 표준 장르 Enum (genre_type)",
        examples=[StandardGenre.COMPUTER_IT],
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="분류 신뢰도 (0.0 ~ 1.0)",
        examples=[0.95],
    )
