"""ConsultLibrarianTool 단위 테스트.

실제 HTTP 통신 없이 httpx Mock으로 사서 에이전트 연동, URL 미설정 시 스텁 처리,
네트워크 오류 시 graceful 폴백을 검증한다.
"""

from unittest.mock import AsyncMock

import httpx
import pytest
from pytest_mock import MockerFixture

from discovery.core.config import Settings
from discovery.domain.orchestrator.tools.librarian_tool import (
    LIBRARIAN_UNAVAILABLE_MESSAGE,
    ConsultLibrarianTool,
)


@pytest.mark.asyncio
async def test_consult_librarian_url_none() -> None:
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        librarian_agent_url=None,
    )
    tool_instance = ConsultLibrarianTool(settings=settings)

    result = await tool_instance.consult("오늘 힘든 하루였어요")

    assert result == LIBRARIAN_UNAVAILABLE_MESSAGE


@pytest.mark.asyncio
async def test_consult_librarian_success(mocker: MockerFixture) -> None:
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        librarian_agent_url="http://localhost:8001",
    )

    mock_client = mocker.MagicMock(spec=httpx.AsyncClient)
    mock_response = mocker.MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "session_id": "sess-123",
        "message": "따뜻한 차 한 잔과 함께 마음을 달래보세요.",
    }
    mock_client.post = AsyncMock(return_value=mock_response)

    tool_instance = ConsultLibrarianTool(settings=settings, http_client=mock_client)

    result = await tool_instance.consult("오늘 힘든 하루였어요", session_id="sess-123")

    assert result == "따뜻한 차 한 잔과 함께 마음을 달래보세요."
    mock_client.post.assert_awaited_once_with(
        "http://localhost:8001/api/v1/chat",
        json={"message": "오늘 힘든 하루였어요", "session_id": "sess-123"},
        timeout=10.0,
    )


@pytest.mark.asyncio
async def test_consult_librarian_http_error(mocker: MockerFixture) -> None:
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        librarian_agent_url="http://localhost:8001",
    )

    mock_client = mocker.MagicMock(spec=httpx.AsyncClient)
    mock_response = mocker.MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_client.post = AsyncMock(return_value=mock_response)

    tool_instance = ConsultLibrarianTool(settings=settings, http_client=mock_client)

    result = await tool_instance.consult("고민이 있어요")

    assert result == LIBRARIAN_UNAVAILABLE_MESSAGE


@pytest.mark.asyncio
async def test_consult_librarian_connection_exception(mocker: MockerFixture) -> None:
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        librarian_agent_url="http://localhost:8001",
    )

    mock_client = mocker.MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    tool_instance = ConsultLibrarianTool(settings=settings, http_client=mock_client)

    result = await tool_instance.consult("고민이 있어요")

    assert result == LIBRARIAN_UNAVAILABLE_MESSAGE


@pytest.mark.asyncio
async def test_consult_librarian_as_tool_execution() -> None:
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        librarian_agent_url=None,
    )
    tool_instance = ConsultLibrarianTool(settings=settings)
    tool_func = tool_instance.as_tool()

    result = await tool_func(message="사서님 계신가요?")

    assert result == LIBRARIAN_UNAVAILABLE_MESSAGE
