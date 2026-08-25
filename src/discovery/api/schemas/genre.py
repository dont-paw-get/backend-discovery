from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class StandardGenre(str, Enum):
    """ERD 도서 카테고리 표준 규격 (16개 장르)."""

    SF = "SF"
    FANTASY = "판타지"
    ROMANCE = "로맨스"
    MYSTERY_THRILLER = "미스터리/스릴러"
    GENERAL_FICTION = "순수소설/일반소설"
    ESSAY = "에세이"
    POETRY_PLAY = "시/희곡"
    HUMANITIES = "인문학"
    HISTORY = "역사"
    BUSINESS_ECONOMY = "경제/경영"
    SELF_HELP = "자기계발"
    SCIENCE = "과학"
    ART = "예술"
    RELIGION = "종교"
    IT_COMPUTER = "컴퓨터/IT"
    ETC = "기타"


class BookClassificationRequest(BaseModel):
    """도서 표준 장르 분류 요청 스키마."""

    model_config = ConfigDict(from_attributes=True)

    title: str = Field(..., min_length=1, description="도서 제목", examples=["파이썬 코딩의 기술"])
    author: str = Field(default="", description="저자명", examples=["브렛 슬라킨"])
    raw_category: str = Field(
        default="",
        description="알라딘/OCR 원본 카테고리 문자열",
        examples=["국내도서 > 컴퓨터/모바일 > 프로그래밍 언어 > 파이썬"],
    )


class BookClassificationResponse(BaseModel):
    """도서 표준 장르 분류 응답 스키마."""

    model_config = ConfigDict(from_attributes=True)

    genre: StandardGenre = Field(
        ...,
        description="매핑된 표준 장르 Enum",
        examples=[StandardGenre.IT_COMPUTER],
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="분류 신뢰도 (0.0 ~ 1.0)",
        examples=[0.95],
    )
