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

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from strands import tool
from tavily import AsyncTavilyClient

from discovery.core.cloudwatch_metrics import CloudWatchMetricsPublisher
from discovery.infrastructure.search.result_cache import SearchResultCache
from discovery.infrastructure.search.usage_limiter import SearchUsageLimiter

logger = logging.getLogger(__name__)

# CLIAR-276: fire-and-forget 캐시 이벤트 발행 태스크가 완료 전 GC로 취소되지 않도록
# 강한 참조를 유지한다(orchestrator_service.py의 동일 패턴 참고).
_background_cache_event_tasks: set[asyncio.Task[None]] = set()

TAVILY_SEARCH_DEPTH = "basic"  # advanced는 절대 쓰지 않는다(크레딧 2배 소모).
NO_RESULTS: list[dict[str, Any]] = []
MAX_CONTENT_LENGTH = 400  # 도서 제목, 저자, 출판사, 쪽수 파악에 충분한 길이
MAX_SEARCH_RESULTS = 5  # 상위 검색 결과 최대 개수


def sanitize_search_results(
    raw_results: list[Any],
    *,
    max_content_length: int = MAX_CONTENT_LENGTH,
    max_results: int = MAX_SEARCH_RESULTS,
) -> list[dict[str, Any]]:
    """Tavily 원본 검색 결과에서 LLM 입력 토큰을 낭비하는 거대 필드(raw_content 등)를 제거하고,

    도서 추천에 필수적인 title, url, content만 정제하여 반환한다.
    """
    sanitized: list[dict[str, Any]] = []
    for item in raw_results[:max_results]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        content = str(item.get("content") or "").strip()
        if len(content) > max_content_length:
            content = content[:max_content_length].rstrip() + "..."
        sanitized.append({
            "title": title,
            "url": url,
            "content": content,
        })
    return sanitized


class BookSearchTool:
    """도서 추천을 위한 웹 검색 도구. 인스턴스 상태(캐시·카운터·클라이언트)를 갖는다."""

    def __init__(
        self,
        tavily_client: AsyncTavilyClient,
        cache: SearchResultCache,
        usage_limiter: SearchUsageLimiter,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        cloudwatch_publisher: CloudWatchMetricsPublisher | None = None,
    ) -> None:
        self._tavily_client = tavily_client
        self._cache = cache
        self._usage_limiter = usage_limiter
        self._now = now
        self._cloudwatch_publisher = cloudwatch_publisher

    def _publish_cache_event(self, *, hit: bool) -> None:
        """CLIAR-276: 검색 캐시 히트/미스 1건을 CloudWatch에 fire-and-forget으로 발행한다.

        `cloudwatch_publisher`가 없거나 비활성이면 아무 것도 하지 않는다(기존 동작 무변화).
        """
        publisher = self._cloudwatch_publisher
        if publisher is None:
            return

        async def _publish() -> None:
            try:
                await publisher.publish_search_cache_event(hit=hit)
            except Exception:
                logger.warning(
                    "[CLOUDWATCH_METRICS] Failed to publish search cache event", exc_info=True
                )

        task = asyncio.create_task(_publish())
        _background_cache_event_tasks.add(task)
        task.add_done_callback(_background_cache_event_tasks.discard)

    async def search_books(self, query: str) -> list[dict[str, Any]]:
        """자연어 질의로 도서 후보를 웹에서 검색한다.

        캐시 히트 시 Tavily를 호출하지 않는다. 월간 사용량 상한을 넘었거나 Tavily
        호출이 실패하면 빈 목록을 반환한다 — 이 경우 에이전트는 자신의 사전 지식만
        으로 답변해야 한다. 이 메서드는 `@tool`로 감싸지 않은 순수 구현이라 단위
        테스트에서 직접 호출하기 쉽다(`as_tool()`이 감싸는 대상).
        """
        cached = await self._cache.get(query)
        if cached is not None:
            self._publish_cache_event(hit=True)
            return cached
        self._publish_cache_event(hit=False)

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
        if isinstance(raw_results, list):
            results = sanitize_search_results(raw_results)
        else:
            results = NO_RESULTS
        await self._cache.set(query, results)
        return results

    def as_tool(self) -> Any:
        """Strands `Agent(tools=[...])`에 등록할 `@tool` 래퍼를 반환한다."""

        @tool(name="search_books")
        async def search_books_tool(query: str) -> list[dict[str, Any]]:
            """도서 추천 및 서지 정보 확인에 필요한 국내 출간 도서 정보
            (제목, 저자, 출판사, 쪽수/페이지수, 줄거리 등)를 웹에서 검색합니다.

            Args:
                query: 도서 검색을 위한 질의
                    (예: "비 오는 날 읽기 좋은 소설", "불편한 편의점 저자 쪽수 페이지수").
            """
            results: list[dict[str, Any]] = await self.search_books(query)
            return results

        return search_books_tool
