"""추천 에이전트를 오케스트레이터의 도구로 감싸는 로컬 도구."""

from typing import Any

from strands import tool

from discovery.application.librarian_service import extract_text_from_message
from discovery.core.config import Settings
from discovery.domain.librarian.agent import create_librarian_agent
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

    async def recommend(self, query: str) -> str:
        """추천 에이전트를 생성하여 도서 추천 및 웹 검색을 수행하고 결과를 반환한다."""
        agent = create_librarian_agent(
            model_id=self._settings.librarian_model_id,
            region_name=self._settings.aws_region,
            tools=[self._book_search_tool.as_tool()],
        )
        result = await agent.invoke_async(prompt=query)
        return extract_text_from_message(result.message)

    def as_tool(self) -> Any:
        """Strands 오케스트레이터 에이전트에 등록할 @tool 함수를 반환한다."""

        @tool(name="recommend_books")
        async def recommend_books_tool(query: str) -> str:
            """사용자의 상황, 관심사, 장르 또는 요청에 맞는 도서를 웹 검색 기반으로 추천하고
            상세히 안내합니다.

            Args:
                query: 도서 추천을 위한 구체적인 검색어 또는 사용자의 요구사항
                    (예: '비 오는 날 읽기 좋은 소설', 'SF 입문작').
            """
            return await self.recommend(query)

        return recommend_books_tool
