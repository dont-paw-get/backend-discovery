"""RecommendBooksTool 단위 테스트.

실제 AWS/Bedrock/Tavily 호출 없이 mocker로 에이전트와 도구를 모킹하여
추천 에이전트 호출, count 인자 전달/clamp 및 텍스트 반환 동작을 검증한다.
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

    result_text = await tool_instance.recommend(query="SF 소설 추천해줘", count=1)

    assert result_text == "### 📖 지구 끝의 온실\n- **저자**: 김초엽"

    mock_create_librarian.assert_called_once_with(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        region_name="us-east-1",
        librarian_id=None,
        tools=[mock_search_as_tool],
        enable_prompt_caching=False,
    )
    expected_prompt = "SF 소설 추천해줘\n\n[요청] 반드시 1권의 도서만 추천해주세요."
    mock_agent.invoke_async.assert_awaited_once_with(prompt=expected_prompt)


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

    # Strands @tool로 데코레이트된 함수 실행 검증 (기본값 count=2 및 명시적 count=3)
    result_default = await tool_func(query="인문학 책 추천")
    assert result_default == "추천 도서입니다."
    tool_instance.recommend.assert_awaited_with(
        query="인문학 책 추천", count=2, librarian_id=None, session_id=None
    )

    result_custom = await tool_func(query="소설 3권 추천", count=3)
    assert result_custom == "추천 도서입니다."
    tool_instance.recommend.assert_awaited_with(
        query="소설 3권 추천", count=3, librarian_id=None, session_id=None
    )


@pytest.mark.asyncio
async def test_recommend_tool_truncates_surplus_books(mocker: MockerFixture) -> None:
    # 하위 에이전트가 2권을 생성했으나 count=1을 요청한 경우 1권만 반환되는지 결과 검증
    mock_search_tool = mocker.MagicMock()
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    mock_agent = mocker.MagicMock()
    two_books_text = (
        "요청하신 도서입니다.\n\n"
        "### 📖 불편한 편의점\n- **저자**: 김호연\n\n"
        "### 📖 달러구트 꿈 백화점\n- **저자**: 이미예"
    )
    mock_result = mocker.MagicMock()
    mock_result.message = {
        "role": "assistant",
        "content": [{"text": two_books_text}],
    }
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)

    mocker.patch(
        "discovery.domain.orchestrator.tools.recommend_tool.create_librarian_agent",
        return_value=mock_agent,
    )

    tool_instance = RecommendBooksTool(
        book_search_tool=mock_search_tool,
        settings=settings,
    )

    result_text = await tool_instance.recommend(query="책 1권 추천해줘", count=1)

    assert "### 📖 불편한 편의점" in result_text
    assert "### 📖 달러구트 꿈 백화점" not in result_text
    assert result_text.count("### 📖") == 1
