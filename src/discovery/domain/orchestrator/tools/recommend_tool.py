"""추천 에이전트를 오케스트레이터의 도구로 감싸는 로컬 도구."""

import asyncio
import re
import time
from typing import Any

from strands import tool

from discovery.core.config import Settings
from discovery.core.observability import log_agent_metrics
from discovery.domain.librarian.agent import create_librarian_agent
from discovery.domain.librarian.post_processor import (
    extract_text_from_message,
    parse_recommended_books_from_markdown,
    truncate_books_by_count,
)
from discovery.domain.orchestrator.tools.book_metadata_client import BookMetadataClient
from discovery.infrastructure.search.book_search_tool import BookSearchTool


class RecommendBooksTool:
    """도서 추천 에이전트를 오케스트레이터의 Agent-as-a-Tool로 실행하는 도구."""

    def __init__(
        self,
        book_search_tool: BookSearchTool,
        settings: Settings,
        book_metadata_client: BookMetadataClient | None = None,
    ) -> None:
        self._book_search_tool = book_search_tool
        self._settings = settings
        self._book_metadata_client = book_metadata_client

    async def recommend(
        self,
        query: str,
        count: int = 2,
        librarian_id: str | None = None,
        session_id: str | None = None,
        auth_token: str | None = None,
    ) -> str:
        """추천 에이전트를 생성하여 도서 추천 및 웹 검색을 수행하고 결과를 반환한다.

        - `count`는 1~5 범위로 clamp하여 생성량을 유도한다.
        - 반환 지점에서 `truncate_books_by_count` 순수 함수를 호출하여
          초과분을 결정론적으로 잘라낸다.
        - CLIAR-237 후속: 각 도서 블록에서 파싱한 제목/저자로 `backend-book`의
          제목·저자 교집합 검색 API(`GET /api/v1/books/search/by-title-author`)를
          호출하여 정확한 페이지수를 검증하고 마크다운의 `({페이지수}쪽)` 표기를
          덮어쓴다. 검증 실패(검색 결과 없음, 네트워크 오류 등) 시 LLM 생성값을
          그대로 유지한다(graceful degradation, 재시도 없음).
        - 하위 에이전트 실행 메트릭(Strands metrics 및 소요시간)을 수집하여 로깅한다.
        """
        start_time = time.perf_counter()
        clamped_count = max(1, min(count, 5))
        agent = create_librarian_agent(
            model_id=self._settings.librarian_model_id,
            region_name=self._settings.aws_region,
            librarian_id=librarian_id,
            tools=[self._book_search_tool.as_tool()],
            enable_prompt_caching=self._settings.enable_prompt_caching,
        )
        prompt = f"{query}\n\n[요청] 반드시 {clamped_count}권의 도서만 추천해주세요."
        result = await agent.invoke_async(prompt=prompt)
        raw_text = extract_text_from_message(result.message)
        truncated_text = truncate_books_by_count(raw_text, count=clamped_count)
        processed_text = await self._verify_page_counts(truncated_text, auth_token=auth_token)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        metrics_summary = (
            result.metrics.get_summary()
            if hasattr(result, "metrics") and result.metrics
            else None
        )
        log_agent_metrics(
            phase="recommend_agent",
            session_id=session_id or "unknown",
            librarian_id=librarian_id,
            mode="sync",
            message_length=len(query),
            metrics_summary=metrics_summary,
            direct_metrics={"total_duration_ms": duration_ms},
        )
        return processed_text

    async def _verify_page_counts(self, markdown: str, auth_token: str | None = None) -> str:
        """마크다운의 각 `### 📖` 도서 블록에서 제목/저자를 추출해 페이지수를 검증하고,
        검증된 값으로 `({페이지수}쪽)` 표기를 덮어쓴다.

        `book_metadata_client`가 배선되지 않았거나 제목/저자를 파싱할 수 있는 블록이
        하나도 없으면 원본을 그대로 반환한다. `auth_token`은 backend-book 서지 조회
        API가 요구하는 사용자 인증 토큰으로, `fetch_by_title_author`까지 패스스루된다.
        """
        if self._book_metadata_client is None:
            return markdown

        parsed = parse_recommended_books_from_markdown(markdown)
        author_by_title: dict[str, str] = {
            b["title"]: author for b in parsed if (author := b.get("author"))
        }
        if not author_by_title:
            return markdown

        titles = list(author_by_title.keys())
        verified_pages = await asyncio.gather(
            *(
                self._book_metadata_client.fetch_by_title_author(
                    t, author_by_title[t], auth_token=auth_token
                )
                for t in titles
            )
        )
        page_by_title = {
            title: pages for title, pages in zip(titles, verified_pages, strict=True) if pages
        }

        if not page_by_title:
            return markdown

        for title, verified_page in page_by_title.items():
            markdown = _replace_page_count_for_title(markdown, title, verified_page)
        return markdown

    def as_tool(
        self,
        librarian_id: str | None = None,
        session_id: str | None = None,
        auth_token: str | None = None,
    ) -> Any:
        """Strands 오케스트레이터 에이전트에 등록할 @tool 함수를 반환한다.

        `auth_token`은 서비스 레이어에서 클로저로 주입되어(LLM 인자로 노출하지 않음),
        페이지수 검증 시 backend-book 서지 조회 API 호출에 사용된다.
        """

        @tool(name="recommend_books")
        async def recommend_books_tool(query: str, count: int = 2) -> str:
            """사용자의 상황, 관심사, 장르, 요청 권수에 맞는 도서를 웹 검색 기반으로 추천하고
            상세히 안내합니다.

            Args:
                query: 도서 추천을 위한 구체적인 검색어 또는 사용자의 요구사항
                    (예: '비 오는 날 읽기 좋은 힐링 소설', 'SF 입문작').
                count: 추천할 도서 권수 (기본값: 2, 1~5권 범위).
            """
            return await self.recommend(
                query=query,
                count=count,
                librarian_id=librarian_id,
                session_id=session_id,
                auth_token=auth_token,
            )

        return recommend_books_tool


def _replace_page_count_for_title(markdown: str, title: str, verified_page: int) -> str:
    """지정된 도서 제목의 저자 줄에 있는 `({N}쪽)` 표기를 검증된 페이지수로 교체한다.

    저자 줄에 쪽수 표기가 없으면(LLM이 생략했거나 근사치 표현을 프롬프트 지침에 따라
    쓰지 않은 경우) 새로 추가한다.
    """
    block_pattern = re.compile(
        r"(### 📖\s*" + re.escape(title) + r"\s*\n-\s*\*\*저자\*\*:\s*)(.+?)(\s*\n)"
    )

    def _replace(match: re.Match[str]) -> str:
        prefix, author_segment, suffix = match.group(1), match.group(2), match.group(3)
        # 기존 "(N쪽)" 또는 "(약 N쪽)" 등 근사치 표현을 제거하고 검증된 값으로 교체.
        author_only = re.sub(r"\s*\([^)]*쪽\)\s*$", "", author_segment).strip()
        return f"{prefix}{author_only} ({verified_page}쪽){suffix}"

    return block_pattern.sub(_replace, markdown, count=1)
