"""Tavily 기반 도서 웹 검색 도구. Strands `@tool`로 감싸 추천 에이전트에 연결한다.

비용 방어 4가지(.harness/PLAN.md Task 2):
1. `search_depth`는 항상 "basic"으로 고정한다(호출부에 노출하지 않음. advanced는
   크레딧을 2배 소모한다).
2. Redis에 검색 결과를 캐싱한다(TTL 기본 1일). 캐시 히트 시 Tavily를 호출하지 않는다.
3. 월간 호출 카운터가 상한(기본 900, 무료 1,000 크레딧의 안전 마진)을 넘으면 Tavily
   호출을 스킵하고 "검색 결과 없음"을 반환해 에이전트가 LLM 자체 지식으로 답변하게
   한다(캐시 히트는 카운트하지 않는다).
4. Tavily 호출이 어떤 이유로든 실패하면(인증 오류, 크레딧 소진, 타임아웃, 네트워크
   오류 등) 예외를 도구 밖으로 전파하지 않고 "검색 결과 없음"으로 graceful 폴백한다.
   원인은 로그로만 남긴다.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

from strands import tool
from tavily import AsyncTavilyClient

from discovery.infrastructure.search.result_cache import SearchResultCache
from discovery.infrastructure.search.usage_limiter import SearchUsageLimiter

logger = logging.getLogger(__name__)

TAVILY_SEARCH_DEPTH = "basic"  # advanced는 절대 쓰지 않는다(크레딧 2배 소모).
NO_RESULTS: list[dict[str, Any]] = []


class BookSearchTool:
    """도서 추천을 위한 웹 검색 도구. 인스턴스 상태(캐시·카운터·클라이언트)를 갖는다."""

    def __init__(
        self,
        tavily_client: AsyncTavilyClient,
        cache: SearchResultCache,
        usage_limiter: SearchUsageLimiter,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._tavily_client = tavily_client
        self._cache = cache
        self._usage_limiter = usage_limiter
        self._now = now

    async def search_books(self, query: str) -> list[dict[str, Any]]:
        """자연어 질의로 도서 후보를 웹에서 검색한다.

        캐시 히트 시 Tavily를 호출하지 않는다. 월간 사용량 상한을 넘었거나 Tavily
        호출이 실패하면 빈 목록을 반환한다 — 이 경우 에이전트는 자신의 사전 지식만
        으로 답변해야 한다. 이 메서드는 `@tool`로 감싸지 않은 순수 구현이라 단위
        테스트에서 직접 호출하기 쉽다(`as_tool()`이 감싸는 대상).
        """
        cached = await self._cache.get(query)
        if cached is not None:
            return cached

        now = self._now()
        if await self._usage_limiter.is_limit_exceeded(now=now):
            logger.warning("Tavily monthly usage limit exceeded, skipping search: %r", query)
            return NO_RESULTS

        try:
            response = await self._tavily_client.search(query, search_depth=TAVILY_SEARCH_DEPTH)
        except Exception:
            logger.exception("Tavily search failed, falling back to no results: %r", query)
            return NO_RESULTS

        await self._usage_limiter.increment(now=now)

        raw_results = response.get("results", []) if isinstance(response, dict) else NO_RESULTS
        results: list[dict[str, Any]] = cast(list[dict[str, Any]], raw_results)
        await self._cache.set(query, results)
        return results

    def as_tool(self) -> Any:
        """Strands `Agent(tools=[...])`에 등록할 `@tool` 래퍼를 반환한다."""

        @tool(name="search_books")
        async def search_books_tool(query: str) -> list[dict[str, Any]]:
            """자연어 질의로 도서 후보를 웹에서 검색한다.

            Args:
                query: 도서 추천을 위한 검색 질의(예: "비 오는 날 읽기 좋은 따뜻한 소설").
            """
            results: list[dict[str, Any]] = await self.search_books(query)
            return results

        return search_books_tool
