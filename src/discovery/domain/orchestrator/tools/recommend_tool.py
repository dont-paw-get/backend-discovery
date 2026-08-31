"""추천 에이전트를 오케스트레이터의 도구로 감싸는 로컬 도구."""

from typing import Any

from strands import tool

from discovery.core.config import Settings
from discovery.domain.librarian.agent import create_librarian_agent
from discovery.domain.librarian.post_processor import (
    extract_text_from_message,
    truncate_books_by_count,
)
from discovery.infrastructure.search.book_search_tool import BookSearchTool


class RecommendBooksTool:
    """도서 추천 에이전트를 오케스트레이터의 Agent-as-a-Tool로 실행하는 도구."""

    def __init__(
        self,
        book_search_tool: BookSearchTool,
        settings: Settings,
    ) -> None:
        self._book_search_tool = book_search_tool
        self._settings = settings

    async def recommend(
        self,
        query: str,
        count: int = 2,
        librarian_id: str | None = None,
    ) -> str:
        """추천 에이전트를 생성하여 도서 추천 및 웹 검색을 수행하고 결과를 반환한다.

        - `count`는 1~5 범위로 clamp하여 생성량을 유도한다.
        - 반환 지점에서 `truncate_books_by_count` 순수 함수를 호출하여
          초과분을 결정론적으로 잘라낸다.
        """
        clamped_count = max(1, min(count, 5))
        agent = create_librarian_agent(
            model_id=self._settings.librarian_model_id,
            region_name=self._settings.aws_region,
            librarian_id=librarian_id,
            tools=[self._book_search_tool.as_tool()],
        )
        prompt = f"{query}\n\n[요청] 반드시 {clamped_count}권의 도서만 추천해주세요."
        result = await agent.invoke_async(prompt=prompt)
        raw_text = extract_text_from_message(result.message)
        return truncate_books_by_count(raw_text, count=clamped_count)

    def as_tool(self, librarian_id: str | None = None) -> Any:
        """Strands 오케스트레이터 에이전트에 등록할 @tool 함수를 반환한다."""

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
            )

        return recommend_books_tool
