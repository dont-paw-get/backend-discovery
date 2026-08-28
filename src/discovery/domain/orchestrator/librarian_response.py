"""사서 에이전트(backend-librarian) 응답 규격 Pydantic 모델."""

from pydantic import BaseModel, ConfigDict, Field


class SwitchToSuggestion(BaseModel):
    """사서 페르소나 전환 제안 스키마."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: str = Field(
        ...,
        description="제안된 사서 ID (예: cat, stork).",
        examples=["cat"],
    )
    name: str = Field(
        ...,
        description="제안된 사서 이름.",
        examples=["고양이 사서"],
    )
    icon: str | None = Field(
        default=None,
        description="사서 아이콘/이모지.",
        examples=["🐱"],
    )
    genres: list[str] = Field(
        default_factory=list,
        description="해당 사서의 전문 장르 목록.",
        examples=[["소설", "에세이"]],
    )


class WeatherSignal(BaseModel):
    """사서가 날씨 도구로부터 수집한 날씨 시그널."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    weather: str | None = Field(default=None, description="날씨 상태 (예: 비, 맑음, 눈)")
    condition: str | None = Field(default=None, description="날씨 상태 영문/국문 코드")
    temperature: float | None = Field(default=None, description="기온 (°C)")
    is_rainy: bool | None = Field(default=None, description="강수 여부")
    description: str | None = Field(default=None, description="날씨 설명")
    location_source: str | None = Field(default=None, description="위치 출처")
    confidence: float | None = Field(default=None, description="날씨 분석 신뢰도")


class LibrarianSignals(BaseModel):
    """사서가 대화 및 상황 분석에서 도출한 시그널."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    weather: WeatherSignal | None = Field(default=None, description="날씨 정보")
    time_of_day: str | None = Field(default=None, description="시간대 (day, night 등)")
    mood: str | None = Field(
        default=None,
        description="사용자 감정/무드 키워드 (예: 차분한, 위로가 필요한, adventurous)",
    )
    genre_focus: list[str] | str = Field(
        default_factory=list,
        description="추천 포커스 장르 목록 또는 문자열",
    )


class LibrarianResponse(BaseModel):
    """사서 에이전트(backend-librarian)의 전체 응답 규격."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    message: str = Field(..., description="사서의 페르소나 대화 답변")
    session_id: str | None = Field(default=None, description="사서 세션 ID")
    librarian_id: str | None = Field(default=None, description="응답한 사서 ID")
    signals: LibrarianSignals | None = Field(default=None, description="날씨/무드/장르 시그널")
    switch_to: SwitchToSuggestion | None = Field(default=None, description="사서 전환 제안")
