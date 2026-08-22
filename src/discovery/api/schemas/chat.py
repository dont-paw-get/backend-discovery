"""대화(Chat) API 요청 및 응답 Pydantic 스키마."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """대화 요청 스키마."""

    model_config = ConfigDict(from_attributes=True)

    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="대화 세션 ID. 미입력 시 새 세션 UUID가 자동 발급된다.",
        examples=["sess-1234-abcd"],
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="사용자 질문 또는 도서 추천 요청 메시지.",
        examples=["비 오는 날 읽기 좋은 잔잔한 일본 소설 추천해줘."],
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
        description="사서 에이전트의 추천 답변.",
    )
