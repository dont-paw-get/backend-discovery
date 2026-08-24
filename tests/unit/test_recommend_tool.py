"""RecommendBooksTool 단위 테스트.

실제 AWS/Bedrock/Tavily 호출 없이 mocker로 에이전트와 도구를 모킹하여
추천 에이전트 호출 및 텍스트 반환 동작을 검증한다.
"""

from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from discovery.core.config import Settings
from discovery.domain.orchestrator.tools.recommend_tool import RecommendBooksTool


@pytest.mark.asyncio
async def test_recommend_tool_calls_create_librarian_agent(mocker: MockerFixture) -> None:
    mock_search_tool = mocker.MagicMock()
    mock_search_as_tool = mocker.MagicMock()
    mock_search_tool.as_tool.return_value = mock_search_as_tool

    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        librarian_model_id="anthropic.claude-3-haiku-20240307-v1:0",
        aws_region="us-east-1",
    )

    mock_agent = mocker.MagicMock()
    mock_result = mocker.MagicMock()
    mock_result.message = {
        "role": "assistant",
        "content": [{"text": "### 📖 지구 끝의 온실\n- **저자**: 김초엽"}],
    }
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)

    mock_create_librarian = mocker.patch(
        "discovery.domain.orchestrator.tools.recommend_tool.create_librarian_agent",
        return_value=mock_agent,
    )

    tool_instance = RecommendBooksTool(
        book_search_tool=mock_search_tool,
        settings=settings,
    )

    result_text = await tool_instance.recommend(query="SF 소설 추천해줘")

    assert result_text == "### 📖 지구 끝의 온실\n- **저자**: 김초엽"

    mock_create_librarian.assert_called_once_with(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        region_name="us-east-1",
        tools=[mock_search_as_tool],
    )
    mock_agent.invoke_async.assert_awaited_once_with(prompt="SF 소설 추천해줘")


@pytest.mark.asyncio
async def test_recommend_tool_as_tool_execution(mocker: MockerFixture) -> None:
    mock_search_tool = mocker.MagicMock()
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    tool_instance = RecommendBooksTool(
        book_search_tool=mock_search_tool,
        settings=settings,
    )
    tool_instance.recommend = AsyncMock(return_value="추천 도서입니다.")  # type: ignore[method-assign]

    tool_func = tool_instance.as_tool()

    # Strands @tool로 데코레이트된 함수 실행 검증
    result = await tool_func(query="인문학 책 추천")

    assert result == "추천 도서입니다."
    tool_instance.recommend.assert_awaited_once_with("인문학 책 추천")
