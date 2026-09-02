"""대화(Chat) API 요청 및 응답 Pydantic 스키마."""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from discovery.api.schemas.genre import StandardGenre
from discovery.domain.orchestrator.librarian_response import (
    LibrarianSignals,
    SwitchToSuggestion,
)

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "LibraryBookCard",
    "RecommendedBookCard",
    "SwitchToSuggestion",
]


class LibraryBookCard(BaseModel):
    """서재 도서 카드 응답 스키마 (클라이언트 '책 열기' 연동용)."""

    model_config = ConfigDict(from_attributes=True)

    book_id: int | str = Field(
        validation_alias=AliasChoices("book_id", "bookId"),
        description="도서 식별자",
        examples=[101],
    )
    title: str = Field(description="도서 제목", examples=["성공하는 인생의 비밀"])
    author: str | None = Field(default=None, description="저자명", examples=["이수진"])
    reading_status: str | None = Field(
        default=None,
        validation_alias=AliasChoices("reading_status", "readingStatus"),
        description="독서 상태 (READING, COMPLETED, WISH 등)",
        examples=["READING"],
    )
    progress: int | None = Field(default=None, description="독서 진행률 (0~100 %)", examples=[88])


class RecommendedBookCard(BaseModel):
    """도서 추천 카드 구조화 응답 스키마 (클라이언트 '책 등록' 자동입력 연동용).

    `message`(마크다운 텍스트)의 `### 📖` 블록에서 파싱된 필드를 그대로 노출한다.
    저자명과 쪽수를 분리된 필드로 제공하여, 클라이언트가 `- **저자**: {name} ({page}쪽)`
    형태의 문자열을 직접 파싱할 필요가 없게 한다(파싱 실패 시 필드가 함께 뒤섞이는
    문제를 구조적으로 방지).
    """

    model_config = ConfigDict(from_attributes=True)

    title: str = Field(description="도서 제목", examples=["세계 경영학 필독서 50"])
    author: str | None = Field(
        default=None, description="저자명 (쪽수 제외)", examples=["톰 버틀러 보던"]
    )
    page_count: int | None = Field(
        default=None, description="총 페이지 수 (쪽수 확인 불가 시 null)", examples=[548]
    )
    reason: str | None = Field(default=None, description="추천 이유")
    genre: StandardGenre = Field(
        default=StandardGenre.NONE,
        description="ERD 16개 표준 장르 Enum (genre_type). 추천 에이전트가 도서 생성 "
        "시점에 함께 판단한 값으로, 매핑 실패 또는 미확인 시 'NONE'.",
        examples=[StandardGenre.MYSTERY_THRILLER],
    )


class ChatRequest(BaseModel):
    """대화 요청 스키마."""

    model_config = ConfigDict(from_attributes=True)

    session_id: str | None = Field(
        default=None,
        description="대화 세션 ID. 미입력 또는 null 시 새 세션 UUID가 자동 발급된다.",
        examples=["sess-1234-abcd"],
    )
    librarian_id: str | None = Field(
        default=None,
        description="사서 ID ('cat' 또는 'stork'). 미전달 시 세션 메타 또는 기본값 'cat' 사용.",
        examples=["cat", "stork"],
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="사용자 질문 또는 도서 추천 요청 메시지.",
        examples=["비 오는 날 읽기 좋은 잔잔한 일본 소설 추천해줘."],
    )

    @field_validator("message")
    @classmethod
    def validate_message_not_blank(cls, v: str) -> str:
        """공백만으로 이루어진 메시지를 422로 거부한다."""
        if not v or not v.strip():
            raise ValueError("메시지는 공백만으로 구성될 수 없습니다.")
        return v
    latitude: float | None = Field(
        default=None,
        description="사용자 위도 (선택, 사서 날씨 큐레이션용).",
        examples=[37.5665],
    )
    longitude: float | None = Field(
        default=None,
        description="사용자 경도 (선택, 사서 날씨 큐레이션용).",
        examples=[126.9780],
    )
    stream: bool = Field(
        default=False,
        description="스트리밍 응답(True) 여부. False이면 전체 완성된 JSON 응답을 반환한다.",
    )


class ChatResponse(BaseModel):
    """대화 응답 스키마."""

    model_config = ConfigDict(from_attributes=True)

    session_id: str = Field(
        ...,
        description="대화 세션 ID.",
        examples=["sess-1234-abcd"],
    )
    message: str = Field(
        ...,
        description="추천 에이전트의 답변.",
    )
    switch_to: SwitchToSuggestion | None = Field(
        default=None,
        description="다른 사서 페르소나로의 전환 제안 (선택).",
    )
    signals: LibrarianSignals | None = Field(
        default=None,
        description="사서 분석 신호 (날씨, 시간대, 무드, 장르 포커스).",
    )
    library_books: list[LibraryBookCard] | None = Field(
        default=None,
        validation_alias=AliasChoices("library_books", "libraryBooks"),
        description="조회된 사용자 서재 도서 카드 목록 (선택).",
    )
    recommended_books: list[RecommendedBookCard] | None = Field(
        default=None,
        validation_alias=AliasChoices("recommended_books", "recommendedBooks"),
        description="추천된 도서 카드 목록 (선택). `message`의 `### 📖` 블록에서 파싱됨.",
    )
