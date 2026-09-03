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
    sanitize_search_results,
)


def _fixed_now() -> datetime:
    return datetime(2026, 8, 21, 12, 0, 0, tzinfo=UTC)


def test_sanitize_search_results_strips_raw_content_and_unnecessary_fields() -> None:
    raw_results = [
        {
            "title": " 책 제목 1 ",
            "url": "https://example.com/book1",
            "content": "도서 설명 요약입니다.",
            "raw_content": "<html><body>거대한 원본 웹페이지 HTML 텍스트...</body></html>",
            "score": 0.95,
            "images": ["https://example.com/img1.jpg"],
        }
    ]

    sanitized = sanitize_search_results(raw_results)

    assert len(sanitized) == 1
    assert sanitized[0] == {
        "title": "책 제목 1",
        "url": "https://example.com/book1",
        "content": "도서 설명 요약입니다.",
    }
    assert "raw_content" not in sanitized[0]
    assert "score" not in sanitized[0]
    assert "images" not in sanitized[0]


def test_sanitize_search_results_truncates_long_content() -> None:
    long_text = "가" * 600
    raw_results = [
        {
            "title": "책 제목",
            "url": "https://example.com",
            "content": long_text,
        }
    ]

    sanitized = sanitize_search_results(raw_results, max_content_length=400)

    assert len(sanitized[0]["content"]) == 403  # 400 + "..."
    assert sanitized[0]["content"].endswith("...")
    assert sanitized[0]["content"].startswith("가" * 400)


def test_sanitize_search_results_limits_max_results() -> None:
    raw_results = [
        {"title": f"책 {i}", "url": f"https://example.com/{i}", "content": "내용"}
        for i in range(10)
    ]

    sanitized = sanitize_search_results(raw_results, max_results=5)

    assert len(sanitized) == 5
    assert sanitized[0]["title"] == "책 0"
    assert sanitized[4]["title"] == "책 4"


def test_sanitize_search_results_handles_invalid_or_none_values() -> None:
    raw_results = [
        "비정상 아이템",
        {"title": None, "url": None, "content": None},
        {"title": "정상 책", "url": "https://example.com", "content": "내용"},
    ]

    sanitized = sanitize_search_results(raw_results)

    assert len(sanitized) == 2
    assert sanitized[0] == {"title": "", "url": "", "content": ""}
    assert sanitized[1] == {"title": "정상 책", "url": "https://example.com", "content": "내용"}


@pytest.mark.asyncio
async def test_search_books_returns_cached_result_without_calling_tavily(
    mocker: MockerFixture,
) -> None:
    tavily_client = mocker.AsyncMock()
    cache = mocker.AsyncMock()
    cache.get.return_value = [{"title": "캐시된 결과", "url": "", "content": ""}]
    usage_limiter = mocker.AsyncMock()

    tool = BookSearchTool(tavily_client, cache, usage_limiter, now=_fixed_now)

    results = await tool.search_books("비 오는 날 소설")

    assert results == [{"title": "캐시된 결과", "url": "", "content": ""}]
    tavily_client.search.assert_not_called()
    usage_limiter.increment.assert_not_called()


@pytest.mark.asyncio
async def test_search_books_calls_tavily_with_basic_depth_on_cache_miss(
    mocker: MockerFixture,
) -> None:
    tavily_client = mocker.AsyncMock()
    tavily_client.search.return_value = {
        "results": [
            {
                "title": "새 결과",
                "url": "https://example.com",
                "content": "새 내용",
                "raw_content": "거대 HTML",
            }
        ]
    }
    cache = mocker.AsyncMock()
    cache.get.return_value = None
    usage_limiter = mocker.AsyncMock()
    usage_limiter.is_limit_exceeded.return_value = False

    tool = BookSearchTool(tavily_client, cache, usage_limiter, now=_fixed_now)

    results = await tool.search_books("따뜻한 소설")

    assert results == [{"title": "새 결과", "url": "https://example.com", "content": "새 내용"}]
    tavily_client.search.assert_called_once_with("따뜻한 소설", search_depth=TAVILY_SEARCH_DEPTH)
    assert TAVILY_SEARCH_DEPTH == "basic"


@pytest.mark.asyncio
async def test_search_books_caches_result_after_successful_search(
    mocker: MockerFixture,
) -> None:
    tavily_client = mocker.AsyncMock()
    tavily_client.search.return_value = {
        "results": [
            {
                "title": "새 결과",
                "url": "https://example.com",
                "content": "새 내용",
                "raw_content": "HTML",
            }
        ]
    }
    cache = mocker.AsyncMock()
    cache.get.return_value = None
    usage_limiter = mocker.AsyncMock()
    usage_limiter.is_limit_exceeded.return_value = False

    tool = BookSearchTool(tavily_client, cache, usage_limiter, now=_fixed_now)

    await tool.search_books("따뜻한 소설")

    expected_cached = [{"title": "새 결과", "url": "https://example.com", "content": "새 내용"}]
    cache.set.assert_called_once_with("따뜻한 소설", expected_cached)


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



# --- CLIAR-276: CloudWatch 검색 캐시 히트/미스 이벤트 발행 배선 검증 ---
# `cloudwatch_publisher=None`(위 12건 전체)이 기존 동작 무변화를 이미 보증하므로,
# 아래는 publisher가 주어졌을 때 정확히 hit/miss가 구분되어 발행되는지만 검증한다.


@pytest.mark.asyncio
async def test_search_books_publishes_cache_hit_event(mocker: MockerFixture) -> None:
    tavily_client = mocker.AsyncMock()
    cache = mocker.AsyncMock()
    cache.get.return_value = [{"title": "캐시된 결과", "url": "", "content": ""}]
    usage_limiter = mocker.AsyncMock()
    publisher = mocker.MagicMock()
    publisher.publish_search_cache_event = mocker.AsyncMock()

    tool = BookSearchTool(
        tavily_client, cache, usage_limiter, now=_fixed_now, cloudwatch_publisher=publisher
    )

    await tool.search_books("비 오는 날 소설")

    publisher.publish_search_cache_event.assert_awaited_once_with(hit=True)


@pytest.mark.asyncio
async def test_search_books_publishes_cache_miss_event(mocker: MockerFixture) -> None:
    tavily_client = mocker.AsyncMock()
    tavily_client.search.return_value = {"results": []}
    cache = mocker.AsyncMock()
    cache.get.return_value = None
    usage_limiter = mocker.AsyncMock()
    usage_limiter.is_limit_exceeded.return_value = False
    publisher = mocker.MagicMock()
    publisher.publish_search_cache_event = mocker.AsyncMock()

    tool = BookSearchTool(
        tavily_client, cache, usage_limiter, now=_fixed_now, cloudwatch_publisher=publisher
    )

    await tool.search_books("따뜻한 소설")

    publisher.publish_search_cache_event.assert_awaited_once_with(hit=False)


@pytest.mark.asyncio
async def test_search_books_without_publisher_does_not_raise(mocker: MockerFixture) -> None:
    """cloudwatch_publisher=None이면 캐시 이벤트 발행 코드가 전혀 실행되지 않는다."""
    tavily_client = mocker.AsyncMock()
    cache = mocker.AsyncMock()
    cache.get.return_value = [{"title": "캐시된 결과", "url": "", "content": ""}]
    usage_limiter = mocker.AsyncMock()

    tool = BookSearchTool(tavily_client, cache, usage_limiter, now=_fixed_now)

    results = await tool.search_books("비 오는 날 소설")

    assert results == [{"title": "캐시된 결과", "url": "", "content": ""}]
