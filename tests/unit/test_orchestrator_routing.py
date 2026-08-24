"""오케스트레이터 라우팅 및 Agent-as-a-Tool E2E 위임 단위 테스트.

도서 추천 요청(recommend_books)과 사서 상담 요청(consult_librarian)의 두 가지 경로에 대해
오케스트레이터의 도구 배선 및 위임 흐름이 올바르게 동작하는지 검증한다.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from discovery.application.orchestrator_service import OrchestratorService
from discovery.core.config import Settings
from discovery.domain.orchestrator.tools.librarian_tool import (
    LIBRARIAN_UNAVAILABLE_MESSAGE,
    ConsultLibrarianTool,
)
from discovery.domain.orchestrator.tools.recommend_tool import RecommendBooksTool


@pytest.mark.asyncio
async def test_orchestrator_routes_to_recommend_books_tool(mocker: MockerFixture) -> None:
    # 1. RecommendBooksTool Mock
    mock_search_tool = MagicMock()
    mock_search_tool.as_tool.return_value = MagicMock()
    mock_recommend_tool = RecommendBooksTool(
        book_search_tool=mock_search_tool,
        settings=Settings(
            redis_url="redis://localhost:6379",
            internal_api_token="token",
            tavily_api_key="key",
        ),
    )
    mock_recommend_tool.recommend = AsyncMock(  # type: ignore[method-assign]
        return_value=(
            "### 📖 달러구트 꿈 백화점\n"
            "- **저자**: 이미예\n"
            "- **추천 이유**: 따뜻한 힐링 소설"
        )
    )

    # 2. ConsultLibrarianTool Mock
    mock_librarian_tool = ConsultLibrarianTool(
        settings=Settings(
            redis_url="redis://localhost:6379",
            internal_api_token="token",
            tavily_api_key="key",
            librarian_agent_url=None,
        )
    )

    # 3. SessionStore & Agent Mock
    mock_session_store = MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.append_turn = AsyncMock()

    mock_agent = MagicMock()
    mock_result = MagicMock()
    mock_result.message = {
        "role": "assistant",
        "content": [
            {
                "text": (
                    "추천해드리는 도서입니다:\n\n"
                    "### 📖 달러구트 꿈 백화점\n"
                    "- **저자**: 이미예\n"
                    "- **추천 이유**: 따뜻한 힐링 소설"
                )
            }
        ],
    }
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)

    mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=Settings(
            redis_url="redis://localhost:6379",
            internal_api_token="token",
            tavily_api_key="key",
        ),
        tools=[mock_recommend_tool.as_tool(), mock_librarian_tool.as_tool()],
    )

    # 도서 추천 질의 실행
    response = await service.chat(session_id="test-sess", message="따뜻한 힐링 소설 추천해줘")

    assert "달러구트 꿈 백화점" in response
    mock_agent.invoke_async.assert_awaited_once_with(prompt="따뜻한 힐링 소설 추천해줘")
    assert mock_session_store.append_turn.await_count == 2


@pytest.mark.asyncio
async def test_orchestrator_routes_to_consult_librarian_stub(mocker: MockerFixture) -> None:
    mock_recommend_tool = MagicMock(spec=RecommendBooksTool)
    mock_recommend_tool.as_tool.return_value = MagicMock()

    # 사서 에이전트 URL이 미설정된 상태의 ConsultLibrarianTool
    librarian_tool = ConsultLibrarianTool(
        settings=Settings(
            redis_url="redis://localhost:6379",
            internal_api_token="token",
            tavily_api_key="key",
            librarian_agent_url=None,
        )
    )

    mock_session_store = MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.append_turn = AsyncMock()

    # 오케스트레이터가 consult_librarian 도구의 준비 중 결과를 바탕으로 사용자에게 안내하는 시나리오
    mock_agent = MagicMock()
    mock_result = MagicMock()
    mock_result.message = {
        "role": "assistant",
        "content": [
            {
                "text": (
                    f"{LIBRARIAN_UNAVAILABLE_MESSAGE} "
                    "대신 원하시는 주제의 도서를 바로 추천해드릴까요?"
                )
            }
        ],
    }
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)

    mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=Settings(
            redis_url="redis://localhost:6379",
            internal_api_token="token",
            tavily_api_key="key",
        ),
        tools=[mock_recommend_tool.as_tool(), librarian_tool.as_tool()],
    )

    response = await service.chat(session_id="test-sess-2", message="사서님과 이야기하고 싶어요")

    assert LIBRARIAN_UNAVAILABLE_MESSAGE in response
    mock_agent.invoke_async.assert_awaited_once_with(prompt="사서님과 이야기하고 싶어요")
    assert mock_session_store.append_turn.await_count == 2
