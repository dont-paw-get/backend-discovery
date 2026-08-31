"""사서 에이전트(backend-librarian)와 HTTP로 통신하는 도구."""

import logging
from collections.abc import Callable
from typing import Any

import httpx
from strands import tool

from discovery.core.config import Settings
from discovery.domain.orchestrator.librarian_response import (
    LibrarianResponse,
    LibrarianSignals,
    SwitchToSuggestion,
    WeatherSignal,
)

logger = logging.getLogger(__name__)

LIBRARIAN_UNAVAILABLE_MESSAGE = "사서 에이전트 서비스가 현재 준비 중입니다."


def format_signals_for_llm(signals: LibrarianSignals | None) -> str:
    """사서가 전달한 signals(날씨/무드/장르)를 LLM 프롬프트에 주입할 텍스트 블록으로 포맷팅한다."""
    if not signals:
        return ""

    lines: list[str] = []
    if signals.genre_focus:
        genres = (
            signals.genre_focus
            if isinstance(signals.genre_focus, list)
            else [signals.genre_focus]
        )
        if genres:
            lines.append(f"- 추천 포커스 장르: {', '.join(genres)}")
    if signals.mood:
        lines.append(f"- 사용자 무드/분위기: {signals.mood}")
    if signals.weather:
        w_text = (
            signals.weather.weather
            or signals.weather.condition
            or signals.weather.description
        )
        if w_text:
            temp_str = (
                f" ({signals.weather.temperature}°C)"
                if signals.weather.temperature is not None
                else ""
            )
            lines.append(f"- 현재 날씨: {w_text}{temp_str}")

    if lines:
        return "\n\n[사서 분석 정보]\n" + "\n".join(lines)
    return ""


# 황새(슈빌) 사서 특화 영역 및 호칭 키워드 (고양이 -> 황새 스위칭 트리거)
STORK_KEYWORDS = {
    "경영", "경제", "재무", "비즈니스", "투자", "주식", "스타트업", "마케팅",
    "회계", "돈", "부자", "창업", "조직", "리더십", "전략", "경영학", "비즈니스도서",
    "황새", "슈빌", "하루", "stork", "황새사서", "슈빌사서", "황새 사서", "슈빌 사서", "하루 사서"
}

# 고양이(블루) 사서 특화 영역 및 호칭 키워드 (황새 -> 고양이 스위칭 트리거)
CAT_KEYWORDS = {
    "미스터리", "추리", "스릴러", "탐정", "살인", "트릭", "반전", "범죄", "형사", "수사",
    "시", "시집", "에세이", "수필", "힐링", "위로", "마음", "감성", "일상", "따뜻",
    "블루", "고양이", "나비", "cat", "고양이사서", "고양이 사서", "블루 사서", "나비 사서"
}


def evaluate_local_persona_response(
    message: str,
    librarian_id: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> LibrarianResponse:
    """원격 사서 서버 장애 또는 fallback 시 Discovery 내부에서 직접 사서 페르소나와
    switch_to 스위칭 판단을 완결적으로 생성한다."""
    target_id = (librarian_id or "cat").strip().lower()
    msg_lower = message.lower()

    weather_sig = WeatherSignal(
        condition="clear",
        temperature=27.5,
        description="독서하기 쾌적한 날씨",
        location_source="default",
    )

    if target_id == "cat":
        is_stork_domain = any(kw in msg_lower for kw in STORK_KEYWORDS)
        if is_stork_domain:
            matched = [kw for kw in STORK_KEYWORDS if kw in msg_lower]
            matched_genre = matched[0] if matched else "비즈니스/경영"
            return LibrarianResponse(
                message=(
                    "비즈니스나 경영, 경제 관련 전문 지식은 우리 황새 사서 슈빌이 훨씬 더 "
                    "해박하고 깊이 있는 통찰을 준다냥! 🪶 슈빌 사서님을 불러드릴까냥?"
                ),
                signals=LibrarianSignals(
                    weather=weather_sig,
                    time_of_day="day",
                    mood="intellectual",
                    genre_focus=[matched_genre, "경영"],
                ),
                switch_to=SwitchToSuggestion(
                    id="stork",
                    name="황새 사서",
                    icon="🪶",
                    genres=["비즈니스", "경영", "경제", "투자", "자기계발", "SF", "과학", "역사"],
                    reason="황새 사서 전문 분야 추천",
                ),
            )
        return LibrarianResponse(
            message=(
                "이야기를 들으니 마음이 몽글몽글해진다냥! "
                "딱 맞는 따뜻하고 좋은 책을 골라주겠다냥 🐾"
            ),
            signals=LibrarianSignals(
                weather=weather_sig,
                time_of_day="day",
                mood="cozy",
                genre_focus=["소설", "에세이", "미스터리"],
            ),
            switch_to=None,
        )
    else:  # stork
        is_cat_domain = (
            any(kw in msg_lower for kw in CAT_KEYWORDS)
            and not any(kw in msg_lower for kw in STORK_KEYWORDS)
        )
        if is_cat_domain:
            return LibrarianResponse(
                message=(
                    "손에 땀을 쥐게 하는 미스터리/추리 소설이나 따뜻한 감성 에세이는 고양이 사서 "
                    "블루님이 가장 탁월한 안목을 지니고 있습니다. 🐾 블루 사서님께 안내해 드릴까요?"
                ),
                signals=LibrarianSignals(
                    weather=weather_sig,
                    time_of_day="day",
                    mood="emotional",
                    genre_focus=["미스터리", "추리", "에세이"],
                ),
                switch_to=SwitchToSuggestion(
                    id="cat",
                    name="고양이 사서",
                    icon="🐾",
                    genres=["미스터리", "추리", "소설", "에세이", "시", "힐링"],
                    reason="고양이 사서 전문 분야 추천",
                ),
            )
        return LibrarianResponse(
            message=(
                "두둥! 질문하신 주제에 깊이를 더해줄 훌륭한 통찰을 담은 "
                "명저들을 선별해 드리겠습니다. 🪶"
            ),
            signals=LibrarianSignals(
                weather=weather_sig,
                time_of_day="day",
                mood="analytical",
                genre_focus=["비즈니스", "경영", "전략"],
            ),
            switch_to=None,
        )


class ConsultLibrarianTool:
    """사서 에이전트 및 로컬 페르소나 엔진을 호출하는 도구."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client

    async def consult(
        self,
        message: str,
        session_id: str | None = None,
        librarian_id: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> LibrarianResponse:
        """사서 에이전트 API를 호출하되, 서버 장애 또는 fallback 응답 시 Discovery 로컬 엔진이
        스위칭 판단과 페르소나를 지능적으로 보정한다."""
        if not self._settings.librarian_agent_url:
            logger.info("librarian_agent_url is not configured, using local persona engine.")
            return evaluate_local_persona_response(
                message=message, librarian_id=librarian_id, latitude=latitude, longitude=longitude
            )

        base = self._settings.librarian_agent_url.rstrip('/')
        url = base if base.endswith('/api/v1/chat') else f"{base}/api/v1/chat"
        payload: dict[str, Any] = {
            "message": message,
            "librarian_id": librarian_id or self._settings.librarian_default_id,
        }
        if session_id:
            payload["session_id"] = session_id
        if latitude is not None:
            payload["latitude"] = latitude
        if longitude is not None:
            payload["longitude"] = longitude

        timeout = self._settings.librarian_http_timeout_seconds

        try:
            if self._http_client is not None:
                response = await self._http_client.post(url, json=payload, timeout=timeout)
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, json=payload, timeout=timeout)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    remote_res = LibrarianResponse.model_validate(data)
                    # 원격 서버가 정상 답변을 제공한 경우
                    is_unavailable = remote_res.message == LIBRARIAN_UNAVAILABLE_MESSAGE
                    if "생각이 안 나는" not in remote_res.message and not is_unavailable:
                        # 원격 서버가 switch_to를 빠뜨렸어도 로컬 엔진으로 스위칭 보강
                        if remote_res.switch_to is None:
                            local_res = evaluate_local_persona_response(
                                message, librarian_id, latitude, longitude
                            )
                            if local_res.switch_to is not None:
                                remote_res.switch_to = local_res.switch_to
                        return remote_res

            logger.warning(
                "Librarian responded with status %d. Using local persona engine.",
                response.status_code,
            )
            return evaluate_local_persona_response(
                message=message, librarian_id=librarian_id, latitude=latitude, longitude=longitude
            )
        except Exception:
            logger.exception("Failed to connect to librarian at %s. Using local persona.", url)
            return evaluate_local_persona_response(
                message=message, librarian_id=librarian_id, latitude=latitude, longitude=longitude
            )

    def as_tool(
        self,
        session_id: str | None = None,
        librarian_id: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        on_response: Callable[[LibrarianResponse], None] | None = None,
    ) -> Any:
        """Strands 오케스트레이터 에이전트에 등록할 @tool 함수를 반환한다.

        세션 ID, 사서 ID, 좌표 정보는 서비스 레이어에서 클로저로 주입되어
        LLM은 순수 대화 메시지만 인자로 전달한다(IDOR 방지).
        """

        @tool(name="consult_librarian")
        async def consult_librarian_tool(message: str) -> str:
            """도서관 사서와의 페르소나 대화, 감정 및 독서 고민 상담 등이 필요할 때 호출합니다.

            주의: 사서 에이전트는 직접적인 웹 도서 검색 기능이 없습니다. 도서 추천이
            필요할 때는 이 도구의 분석 신호(장르, 무드 등)를 활용하여 반드시
            `recommend_books` 도구를 이어서 호출해야 합니다.

            Args:
                message: 사서에게 전달할 사용자의 이야기나 고민 내용
                    (예: '요즘 마음이 허전해요', '사서님과 이야기하고 싶어요').
            """
            res = await self.consult(
                message=message,
                session_id=session_id,
                librarian_id=librarian_id,
                latitude=latitude,
                longitude=longitude,
            )
            if on_response is not None:
                on_response(res)
            return f"{res.message}{format_signals_for_llm(res.signals)}"

        return consult_librarian_tool

