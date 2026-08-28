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

    # 1. 고양이 사서에게 SF/경영 질문 -> 황새 사서로 switch_to 생성
    result_sf = await tool_instance.consult("SF 우주 소설과 경영학 책 추천해줘", librarian_id="cat")
    assert result_sf.switch_to is not None
    assert result_sf.switch_to.id == "stork"
    assert "황새 사서" in result_sf.message

    # 2. 황새 사서에게 시/에세이 질문 -> 고양이 사서로 switch_to 생성
    result_poem = await tool_instance.consult(
        "따뜻한 시집과 힐링 에세이 추천해주세요", librarian_id="stork"
    )
    assert result_poem.switch_to is not None
    assert result_poem.switch_to.id == "cat"
    assert "고양이 사서" in result_poem.message

    # 3. 고양이 사서에게 "슈빌 사서" 호칭만 입력 -> 황새 사서로 switch_to 생성
    result_shoebill = await tool_instance.consult("슈빌 사서", librarian_id="cat")
    assert result_shoebill.switch_to is not None
    assert result_shoebill.switch_to.id == "stork"
    assert "황새 사서" in result_shoebill.message


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

    # 연결 실패 시 로컬 엔진이 황새 사서 스위칭 제안 생성
    assert result.switch_to is not None
    assert result.switch_to.id == "stork"
    assert "황새 사서" in result.message


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

