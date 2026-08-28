"""대화(Chat) API 요청 및 응답 Pydantic 스키마."""

from pydantic import BaseModel, ConfigDict, Field

from discovery.domain.orchestrator.librarian_response import (
    LibrarianSignals,
    SwitchToSuggestion,
)

__all__ = ["ChatRequest", "ChatResponse", "SwitchToSuggestion"]


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
        max_length=1000,
        description="사용자 질문 또는 도서 추천 요청 메시지.",
        examples=["비 오는 날 읽기 좋은 잔잔한 일본 소설 추천해줘."],
    )
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
