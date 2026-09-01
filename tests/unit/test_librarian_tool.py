"""ConsultLibrarianTool 단위 테스트.

실제 HTTP 통신 없이 httpx Mock으로 사서 에이전트 연동, DTO 파싱, signals 포맷팅,
switch_to 제안, 타임아웃 설정값 반영, 스텁 폴백을 검증한다.
"""

from unittest.mock import AsyncMock

import httpx
import pytest
from pytest_mock import MockerFixture

from discovery.core.config import Settings
from discovery.domain.orchestrator.librarian_response import LibrarianResponse
from discovery.domain.orchestrator.tools.librarian_tool import ConsultLibrarianTool


@pytest.mark.asyncio
async def test_consult_librarian_url_none_uses_local_persona() -> None:
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        librarian_agent_url=None,
    )
    tool_instance = ConsultLibrarianTool(settings=settings)

    # 1. 고양이 사서에게 명시적 SF/경영 추천 질문 -> 슈빌 사서로 switch_to 생성
    result_sf = await tool_instance.consult("SF 우주 소설과 경영학 책 추천해줘", librarian_id="cat")
    assert result_sf.switch_to is not None
    assert result_sf.switch_to.id == "stork"
    assert "슈빌 사서" in result_sf.message

    # 2. 황새 사서에게 명시적 시/에세이 추천 질문 -> 블루 사서로 switch_to 생성
    result_poem = await tool_instance.consult(
        "따뜻한 시집과 힐링 에세이 추천해주세요", librarian_id="stork"
    )
    assert result_poem.switch_to is not None
    assert result_poem.switch_to.id == "cat"
    assert "블루 사서" in result_poem.message

    # 3. 고양이 사서에게 "슈빌 사서" 상대 호칭 단독 입력 -> 슈빌 사서로 switch_to 생성
    result_shoebill = await tool_instance.consult("슈빌 사서 불러줘", librarian_id="cat")
    assert result_shoebill.switch_to is not None
    assert result_shoebill.switch_to.id == "stork"
    assert "슈빌 사서" in result_shoebill.message



@pytest.mark.asyncio
async def test_local_persona_greetings_and_identity_no_switch_to() -> None:
    """인사/정체성 질문 시 호칭 키워드가 있어도 인사가 우선하며 switch_to가 발생하지 않는다."""
    settings = Settings(

        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        librarian_agent_url=None,
    )
    tool_instance = ConsultLibrarianTool(settings=settings)

    # 1. 블루에게 인사 (호칭 포함)
    res_cat_greet = await tool_instance.consult("블루야 안녕! 반가워", librarian_id="cat")
    assert res_cat_greet.switch_to is None
    assert "사서 '블루'다냥" in res_cat_greet.message
    assert "골라주겠다냥" not in res_cat_greet.message

    # 2. 슈빌에게 인사 (호칭 포함)
    res_stork_greet = await tool_instance.consult(
        "슈빌님 안녕하세요 반갑습니다", librarian_id="stork"
    )
    assert res_stork_greet.switch_to is None
    assert "수석 사서 '슈빌'입니다" in res_stork_greet.message
    assert "선별해 드리겠습니다" not in res_stork_greet.message


    # 3. 정체성 질문
    res_identity = await tool_instance.consult("너 누구야?", librarian_id="cat")
    assert res_identity.switch_to is None
    assert "사서 '블루'다냥" in res_identity.message


@pytest.mark.asyncio
async def test_local_persona_same_librarian_call_no_switch_to() -> None:
    """이미 활성화된 동일 사서를 부르는 호칭은 switch_to를 발생시키지 않는다."""
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        librarian_agent_url=None,
    )
    tool_instance = ConsultLibrarianTool(settings=settings)

    # cat 활성 상태에서 블루 호칭
    res_cat = await tool_instance.consult("블루 사서님", librarian_id="cat")
    assert res_cat.switch_to is None

    # stork 활성 상태에서 슈빌 호칭
    res_stork = await tool_instance.consult("슈빌 사서님", librarian_id="stork")
    assert res_stork.switch_to is None


@pytest.mark.asyncio
async def test_local_persona_daily_chat_no_book_recommendation_mentions() -> None:
    """추천 의도가 없는 일상 대화나 감정 토로 시 도서 추천 멘트와 switch_to가 발생하지 않는다."""
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        librarian_agent_url=None,
    )
    tool_instance = ConsultLibrarianTool(settings=settings)

    # 1. '돈' 단어가 들어간 일상 팁 질문 (stork 스위칭 오발동 방어)
    res_money = await tool_instance.consult("돈 아끼는 좋은 팁이 있을까?", librarian_id="cat")
    assert res_money.switch_to is None
    assert "골라주겠다냥" not in res_money.message
    assert "서재에서 쉬어가라냥" in res_money.message

    # 2. '마음' 단어가 들어간 감정 토로 (cat 스위칭 오발동 방어)
    res_mood = await tool_instance.consult("요즘 마음이 좀 허전하고 그래요", librarian_id="stork")
    assert res_mood.switch_to is None
    assert "선별해 드리겠습니다" not in res_mood.message
    assert "사색의 시간" in res_mood.message


@pytest.mark.asyncio
async def test_local_persona_lookup_vs_recommendation_contrast() -> None:
    """서재 조회 질문 vs 도서 추천 질문의 대조 케이스를 명확하게 검증한다."""
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        librarian_agent_url=None,
    )
    tool_instance = ConsultLibrarianTool(settings=settings)

    # [조회성 질문] 추천 의도 없음 -> 스위칭 미발생
    res_lookup = await tool_instance.consult("내 서재에 경영학 책 있어?", librarian_id="cat")
    assert res_lookup.switch_to is None
    assert "골라주겠다냥" not in res_lookup.message

    # [추천 질문] 추천 의도 True + 경영학 도메인 True -> 슈빌로 스위칭 정상 발생
    res_rec = await tool_instance.consult("경영학 책 추천해줘", librarian_id="cat")
    assert res_rec.switch_to is not None
    assert res_rec.switch_to.id == "stork"
    assert "슈빌 사서" in res_rec.message



@pytest.mark.asyncio
async def test_consult_librarian_success_with_signals_and_switch_to(mocker: MockerFixture) -> None:
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        librarian_agent_url="http://localhost:8000",
        librarian_default_id="cat",
        librarian_http_timeout_seconds=20.0,
    )

    mock_client = mocker.MagicMock(spec=httpx.AsyncClient)
    mock_response = mocker.MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": "따뜻한 차 한 잔과 함께 마음을 달래보세요.",
        "signals": {
            "weather": {
                "weather": "비",
                "temperature": 18.5,
                "is_rainy": True,
                "confidence": 0.9,
            },
            "mood": "차분하고 아늑한",
            "genre_focus": ["에세이", "문학소설"],
        },
        "switch_to": {
            "id": "stork",
            "name": "황새 사서",
            "icon": "🪶",
            "genres": ["시", "에세이"],
        },
    }
    mock_client.post = AsyncMock(return_value=mock_response)

    tool_instance = ConsultLibrarianTool(settings=settings, http_client=mock_client)

    result = await tool_instance.consult(
        message="오늘 비가 오네요",
        session_id="sess-123",
        librarian_id="cat",
        latitude=37.5665,
        longitude=126.9780,
    )

    assert isinstance(result, LibrarianResponse)
    assert result.message == "따뜻한 차 한 잔과 함께 마음을 달래보세요."
    assert result.signals is not None
    assert result.signals.mood == "차분하고 아늑한"
    assert result.signals.genre_focus == ["에세이", "문학소설"]
    assert result.signals.weather is not None
    assert result.signals.weather.weather == "비"
    assert result.switch_to is not None
    assert result.switch_to.id == "stork"
    assert result.switch_to.name == "황새 사서"

    mock_client.post.assert_awaited_once_with(
        "http://localhost:8000/api/v1/chat",
        json={
            "message": "오늘 비가 오네요",
            "librarian_id": "cat",
            "session_id": "sess-123",
            "latitude": 37.5665,
            "longitude": 126.9780,
        },
        timeout=20.0,
    )


@pytest.mark.asyncio
async def test_consult_librarian_http_error_falls_back_to_local_persona(
    mocker: MockerFixture,
) -> None:
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        librarian_agent_url="http://localhost:8000",
    )

    mock_client = mocker.MagicMock(spec=httpx.AsyncClient)
    mock_response = mocker.MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_client.post = AsyncMock(return_value=mock_response)

    tool_instance = ConsultLibrarianTool(settings=settings, http_client=mock_client)

    result = await tool_instance.consult("고민이 있어요", librarian_id="cat")

    # 원격 500 에러 시 로컬 페르소나가 정상적으로 따뜻한 답변을 생성
    assert "마음이 몽글몽글" in result.message
    assert result.signals is not None


@pytest.mark.asyncio
async def test_consult_librarian_connection_exception_falls_back_to_local_persona(
    mocker: MockerFixture,
) -> None:
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        librarian_agent_url="http://localhost:8000",
    )

    mock_client = mocker.MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    tool_instance = ConsultLibrarianTool(settings=settings, http_client=mock_client)

    result = await tool_instance.consult("경영학 책 추천해줘", librarian_id="cat")

    # 연결 실패 시 로컬 엔진이 슈빌 사서 스위칭 제안 생성
    assert result.switch_to is not None
    assert result.switch_to.id == "stork"
    assert "슈빌 사서" in result.message



@pytest.mark.asyncio
async def test_consult_librarian_as_tool_execution_with_callback_and_signals(
    mocker: MockerFixture,
) -> None:
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        librarian_agent_url="http://localhost:8000",
    )
    mock_client = mocker.MagicMock(spec=httpx.AsyncClient)
    mock_response = mocker.MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": "안녕냥! 오늘도 좋은 하루 보내라냥.",
        "signals": {
            "mood": "포근한",
            "genre_focus": ["동화", "힐링"],
        },
        "switch_to": {
            "id": "stork",
            "name": "황새 사서",
        },
    }
    mock_client.post = AsyncMock(return_value=mock_response)

    tool_instance = ConsultLibrarianTool(settings=settings, http_client=mock_client)

    captured_responses: list[LibrarianResponse] = []

    def on_res(res: LibrarianResponse) -> None:
        captured_responses.append(res)

    tool_func = tool_instance.as_tool(
        session_id="sess-abc",
        librarian_id="cat",
        latitude=37.5,
        longitude=127.0,
        on_response=on_res,
    )

    result = await tool_func(message="사서님 안녕!")

    assert "안녕냥! 오늘도 좋은 하루 보내라냥." in result
    assert "[사서 분석 정보]" in result
    assert "포커스 장르: 동화, 힐링" in result
    assert "사용자 무드/분위기: 포근한" in result
    assert len(captured_responses) == 1
    assert captured_responses[0].switch_to is not None
    assert captured_responses[0].switch_to.id == "stork"

