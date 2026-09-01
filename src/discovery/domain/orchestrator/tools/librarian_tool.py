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


# 인사 및 정체성 패턴 (1단계 최우선 필터링)
GREETING_PATTERNS = {
    "안녕", "반가워", "반갑습니다", "하이", "hello", "hi", "좋은 아침", "좋은 저녁", "잘 잤어",
    "너 누구", "누구야", "이름이 뭐야", "이름이 뭐", "몇 살", "자기소개", "너는 누구", "소개해줘",
}

# 사서 호칭 키워드셋 (분리)
STORK_CALL_KEYWORDS = {
    "황새", "슈빌", "하루", "stork", "황새사서", "슈빌사서", "황새 사서", "슈빌 사서", "하루 사서"
}
CAT_CALL_KEYWORDS = {
    "블루", "고양이", "나비", "cat", "고양이사서", "고양이 사서", "블루 사서", "나비 사서"
}

# 전환/호출 의도 서술어
SWITCH_ACTION_KEYWORDS = {
    "불러줘", "바꿔줘", "연결해줘", "물어볼래", "물어봐줘",
    "상담할래", "대화할래", "부탁해", "소환", "데려와",
}


# 도서 추천 의도 키워드셋
RECOMMENDATION_INTENT_KEYWORDS = {
    "추천", "읽을만", "읽을 만", "골라줘", "골라주", "찾아줘", "찾아주", "권해줘", "권해주",
    "책 추천", "도서 추천", "새로운 책", "신간", "베스트셀러", "명저", "읽을거리",
}

# 도메인 장르 키워드셋 (호칭 제외)
STORK_GENRE_KEYWORDS = {
    "경영", "경제", "재무", "비즈니스", "투자", "주식", "스타트업", "마케팅",
    "회계", "창업", "조직", "리더십", "전략", "경영학", "비즈니스도서", "sf", "과학", "it", "개발"
}
CAT_GENRE_KEYWORDS = {
    "미스터리", "추리", "스릴러", "탐정", "살인", "트릭", "반전", "범죄", "형사", "수사",
    "시", "시집", "에세이", "수필", "힐링", "위로", "마음", "감성", "소설"
}

# 레거시 호환용 키워드 통합셋
STORK_KEYWORDS = STORK_GENRE_KEYWORDS | STORK_CALL_KEYWORDS
CAT_KEYWORDS = CAT_GENRE_KEYWORDS | CAT_CALL_KEYWORDS


def _is_greeting_or_identity(msg_lower: str) -> bool:
    """인사 또는 정체성/자기소개 질문인지 확인한다."""
    return any(p in msg_lower for p in GREETING_PATTERNS)


def _has_recommendation_intent(msg_lower: str) -> bool:
    """명시적인 도서 추천/탐색 의도가 포함되어 있는지 확인한다."""
    return any(kw in msg_lower for kw in RECOMMENDATION_INTENT_KEYWORDS)


def _is_calling_librarian(msg_lower: str, call_keywords: set[str]) -> bool:
    """특정 사서를 직접 호칭하여 호출/전환을 요청하는지 확인한다."""
    has_call_kw = any(kw in msg_lower for kw in call_keywords)
    if not has_call_kw:
        return False
    # 전환 서술어가 함께 있거나, 호칭 중심의 짧은 호출 문장인 경우
    has_action = any(act in msg_lower for act in SWITCH_ACTION_KEYWORDS)
    return has_action or len(msg_lower.strip()) <= 15


def evaluate_local_persona_response(
    message: str,
    librarian_id: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> LibrarianResponse:
    """원격 사서 서버 장애 또는 fallback 시 Discovery 내부에서 우선순위 의도 게이트에 따라
    사서 페르소나와 switch_to 스위칭 판단을 결정론적으로 생성한다."""
    target_id = (librarian_id or "cat").strip().lower()
    msg_lower = message.lower()

    weather_sig = WeatherSignal(
        condition="clear",
        temperature=27.5,
        description="독서하기 쾌적한 날씨",
        location_source="default",
    )

    # 1단계: 인사 및 정체성 패턴 최우선 필터링 (호칭 키워드 충돌 방어)
    if _is_greeting_or_identity(msg_lower):
        if target_id == "cat":
            return LibrarianResponse(
                message=(
                    "안냥! 나는 Don't Paw Get Your Book 서재의 사서 '블루'다냥 🐾 "
                    "오늘 서재에서 어떤 이야기를 나누고 싶냥?"
                ),
                signals=LibrarianSignals(
                    weather=weather_sig,
                    time_of_day="day",
                    mood="friendly",
                    genre_focus=["에세이", "소설"],
                ),
                switch_to=None,
            )
        else:  # stork
            return LibrarianResponse(
                message=(
                    "두둥! 안녕하십니까. Don't Paw Get Your Book 서재의 수석 사서 '슈빌'입니다 🪶 "
                    "깊이 있는 지식과 사색의 공간에 오신 것을 환영합니다."
                ),
                signals=LibrarianSignals(
                    weather=weather_sig,
                    time_of_day="day",
                    mood="polite",
                    genre_focus=["비즈니스", "인문"],
                ),
                switch_to=None,
            )

    # 2단계: 상대 사서 직접 호출/전환 의도 (`is_call_other_librarian`)
    # 3단계: 도서 추천 의도 및 상대 도메인 결합 (`has_rec_intent AND has_other_domain`)
    has_rec_intent = _has_recommendation_intent(msg_lower)

    if target_id == "cat":
        is_calling_stork = _is_calling_librarian(msg_lower, STORK_CALL_KEYWORDS)
        has_stork_domain = any(kw in msg_lower for kw in STORK_GENRE_KEYWORDS)
        should_switch_to_stork = is_calling_stork or (has_rec_intent and has_stork_domain)

        if should_switch_to_stork:
            matched = [kw for kw in STORK_GENRE_KEYWORDS if kw in msg_lower]
            matched_genre = matched[0] if matched else "비즈니스/경영"
            return LibrarianResponse(
                message=(
                    "비즈니스나 경영, 경제 관련 전문 지식은 우리 슈빌 사서가 훨씬 더 "
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
                    name="슈빌 사서",
                    icon="🪶",
                    genres=["비즈니스", "경영", "경제", "투자", "자기계발", "SF", "과학", "역사"],
                    reason="슈빌 사서 전문 분야 추천",
                ),
            )

        # 4단계: 명시적 도서 추천 요청 (블루 본인 영역)
        if has_rec_intent:
            return LibrarianResponse(
                message=(
                    "이야기를 들으니 딱 맞는 책이 떠오른다냥! "
                    "따뜻하고 흥미진진한 좋은 책을 골라주겠다냥 🐾"
                ),
                signals=LibrarianSignals(
                    weather=weather_sig,
                    time_of_day="day",
                    mood="cozy",
                    genre_focus=["소설", "에세이", "미스터리"],
                ),
                switch_to=None,
            )

        # 5단계: 비추천 일반 대화/감정/잡담
        return LibrarianResponse(
            message=(
                "사서님의 이야기를 들으니 마음이 몽글몽글해진다냥 🐾 "
                "편안한 마음으로 서재에서 쉬어가라냥!"
            ),
            signals=LibrarianSignals(
                weather=weather_sig,
                time_of_day="day",
                mood="casual",
                genre_focus=["에세이"],
            ),
            switch_to=None,
        )

    else:  # stork
        is_calling_cat = _is_calling_librarian(msg_lower, CAT_CALL_KEYWORDS)
        has_cat_domain = any(kw in msg_lower for kw in CAT_GENRE_KEYWORDS)
        should_switch_to_cat = is_calling_cat or (has_rec_intent and has_cat_domain)

        if should_switch_to_cat:
            return LibrarianResponse(
                message=(
                    "손에 땀을 쥐게 하는 미스터리/추리 소설이나 따뜻한 감성 에세이는 블루 사서님이 "
                    "가장 탁월한 안목을 지니고 있습니다 🐾 블루 사서님께 안내해 드릴까요?"
                ),
                signals=LibrarianSignals(
                    weather=weather_sig,
                    time_of_day="day",
                    mood="emotional",
                    genre_focus=["미스터리", "추리", "에세이"],
                ),
                switch_to=SwitchToSuggestion(
                    id="cat",
                    name="블루 사서",
                    icon="🐾",
                    genres=["미스터리", "추리", "소설", "에세이", "시", "힐링"],
                    reason="블루 사서 전문 분야 추천",
                ),
            )

        # 4단계: 명시적 도서 추천 요청 (슈빌 본인 영역)
        if has_rec_intent:
            return LibrarianResponse(
                message=(
                    "두둥! 질문하신 주제에 깊이를 더해줄 훌륭한 통찰을 담은 "
                    "명저들을 선별해 드리겠습니다 🪶"
                ),
                signals=LibrarianSignals(
                    weather=weather_sig,
                    time_of_day="day",
                    mood="analytical",
                    genre_focus=["비즈니스", "경영", "전략"],
                ),
                switch_to=None,
            )

        # 5단계: 비추천 일반 대화/감정/잡담
        return LibrarianResponse(
            message=(
                "두둥! 사서님의 말씀에 깊이 귀를 기울이고 있습니다 🪶 "
                "서재에서 차분하고 평온한 사색의 시간 보내시길 바랍니다."
            ),
            signals=LibrarianSignals(
                weather=weather_sig,
                time_of_day="day",
                mood="peaceful",
                genre_focus=["인문"],
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

