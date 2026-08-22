"""BookSearchTool의 비용 방어 로직(캐시, 사용량 제한, graceful 폴백)을 mocker로 검증한다.

AGENTS.md 테스트 원칙: 반환값을 우선 검증한다. Tavily 실제 호출은 발생시키지 않는다
(AsyncTavilyClient 자체를 mocker로 대체).
"""

from datetime import UTC, datetime

import pytest
from pytest_mock import MockerFixture

from discovery.infrastructure.search.book_search_tool import (
    NO_RESULTS,
    TAVILY_SEARCH_DEPTH,
    BookSearchTool,
)


def _fixed_now() -> datetime:
    return datetime(2026, 8, 21, 12, 0, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_search_books_returns_cached_result_without_calling_tavily(
    mocker: MockerFixture,
) -> None:
    tavily_client = mocker.AsyncMock()
    cache = mocker.AsyncMock()
    cache.get.return_value = [{"title": "캐시된 결과"}]
    usage_limiter = mocker.AsyncMock()

    tool = BookSearchTool(tavily_client, cache, usage_limiter, now=_fixed_now)

    results = await tool.search_books("비 오는 날 소설")

    assert results == [{"title": "캐시된 결과"}]
    tavily_client.search.assert_not_called()
    usage_limiter.increment.assert_not_called()


@pytest.mark.asyncio
async def test_search_books_calls_tavily_with_basic_depth_on_cache_miss(
    mocker: MockerFixture,
) -> None:
    tavily_client = mocker.AsyncMock()
    tavily_client.search.return_value = {"results": [{"title": "새 결과"}]}
    cache = mocker.AsyncMock()
    cache.get.return_value = None
    usage_limiter = mocker.AsyncMock()
    usage_limiter.is_limit_exceeded.return_value = False

    tool = BookSearchTool(tavily_client, cache, usage_limiter, now=_fixed_now)

    results = await tool.search_books("따뜻한 소설")

    assert results == [{"title": "새 결과"}]
    tavily_client.search.assert_called_once_with("따뜻한 소설", search_depth=TAVILY_SEARCH_DEPTH)
    assert TAVILY_SEARCH_DEPTH == "basic"


@pytest.mark.asyncio
async def test_search_books_caches_result_after_successful_search(
    mocker: MockerFixture,
) -> None:
    tavily_client = mocker.AsyncMock()
    tavily_client.search.return_value = {"results": [{"title": "새 결과"}]}
    cache = mocker.AsyncMock()
    cache.get.return_value = None
    usage_limiter = mocker.AsyncMock()
    usage_limiter.is_limit_exceeded.return_value = False

    tool = BookSearchTool(tavily_client, cache, usage_limiter, now=_fixed_now)

    await tool.search_books("따뜻한 소설")

    cache.set.assert_called_once_with("따뜻한 소설", [{"title": "새 결과"}])


@pytest.mark.asyncio
async def test_search_books_increments_usage_only_on_actual_tavily_call(
    mocker: MockerFixture,
) -> None:
    tavily_client = mocker.AsyncMock()
    tavily_client.search.return_value = {"results": []}
    cache = mocker.AsyncMock()
    cache.get.return_value = None
    usage_limiter = mocker.AsyncMock()
    usage_limiter.is_limit_exceeded.return_value = False

    tool = BookSearchTool(tavily_client, cache, usage_limiter, now=_fixed_now)

    await tool.search_books("질의")

    usage_limiter.increment.assert_called_once_with(now=_fixed_now())


@pytest.mark.asyncio
async def test_search_books_skips_tavily_when_monthly_limit_exceeded(
    mocker: MockerFixture,
) -> None:
    tavily_client = mocker.AsyncMock()
    cache = mocker.AsyncMock()
    cache.get.return_value = None
    usage_limiter = mocker.AsyncMock()
    usage_limiter.is_limit_exceeded.return_value = True

    tool = BookSearchTool(tavily_client, cache, usage_limiter, now=_fixed_now)

    results = await tool.search_books("질의")

    assert results == NO_RESULTS
    tavily_client.search.assert_not_called()


@pytest.mark.asyncio
async def test_search_books_falls_back_gracefully_when_tavily_raises(
    mocker: MockerFixture,
) -> None:
    tavily_client = mocker.AsyncMock()
    tavily_client.search.side_effect = RuntimeError("Tavily API 오류(크레딧 소진 등)")
    cache = mocker.AsyncMock()
    cache.get.return_value = None
    usage_limiter = mocker.AsyncMock()
    usage_limiter.is_limit_exceeded.return_value = False

    tool = BookSearchTool(tavily_client, cache, usage_limiter, now=_fixed_now)

    results = await tool.search_books("질의")

    assert results == NO_RESULTS
    usage_limiter.increment.assert_not_called()
    cache.set.assert_not_called()


@pytest.mark.asyncio
async def test_search_books_handles_unexpected_response_shape(mocker: MockerFixture) -> None:
    tavily_client = mocker.AsyncMock()
    tavily_client.search.return_value = "예상치 못한 응답 형태"
    cache = mocker.AsyncMock()
    cache.get.return_value = None
    usage_limiter = mocker.AsyncMock()
    usage_limiter.is_limit_exceeded.return_value = False

    tool = BookSearchTool(tavily_client, cache, usage_limiter, now=_fixed_now)

    results = await tool.search_books("질의")

    assert results == NO_RESULTS


def test_as_tool_returns_strands_tool_with_search_books_name(mocker: MockerFixture) -> None:
    tavily_client = mocker.AsyncMock()
    cache = mocker.AsyncMock()
    usage_limiter = mocker.AsyncMock()

    tool = BookSearchTool(tavily_client, cache, usage_limiter, now=_fixed_now)
    strands_tool = tool.as_tool()

    assert strands_tool.tool_spec["name"] == "search_books"
    assert "query" in strands_tool.tool_spec["inputSchema"]["json"]["properties"]
