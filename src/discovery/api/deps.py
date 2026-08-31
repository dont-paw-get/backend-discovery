"""FastAPI 의존성 주입 지점. 테스트에서 이 함수들을 오버라이드해 실제 인프라를 대체한다."""

from datetime import UTC, datetime

from fastapi import Depends, Request
from tavily import AsyncTavilyClient

from discovery.application.genre_classifier_service import GenreClassifierService
from discovery.application.librarian_service import LibrarianService
from discovery.application.orchestrator_service import OrchestratorService
from discovery.core.config import get_settings
from discovery.domain.orchestrator.tools.librarian_tool import ConsultLibrarianTool
from discovery.domain.orchestrator.tools.library_tool import SearchMyLibraryTool
from discovery.domain.orchestrator.tools.recommend_tool import RecommendBooksTool
from discovery.infrastructure.cache.chat_session_store import ChatSessionStore
from discovery.infrastructure.search.book_search_tool import BookSearchTool
from discovery.infrastructure.search.result_cache import SearchResultCache
from discovery.infrastructure.search.usage_limiter import SearchUsageLimiter


def get_now() -> datetime:
    """현재 시각. `datetime.now()` 직접 호출 대신 이 의존성을 통해 주입받는다.

    AGENTS.md 테스트 원칙: 제어 불가능한 값(현재 시각)은 DI로 받아 결정론적으로 테스트한다.
    """
    return datetime.now(UTC)


def get_chat_session_store(request: Request) -> ChatSessionStore:
    """app.state.redis(lifespan에서 생성)를 사용하는 대화 세션 스토어."""
    settings = get_settings()
    return ChatSessionStore(
        request.app.state.redis,
        max_turns=settings.chat_history_max_turns,
        ttl_seconds=settings.chat_session_ttl_seconds,
    )


def get_book_search_tool(request: Request) -> BookSearchTool:
    """Tavily 도서 웹 검색 도구."""
    settings = get_settings()
    cache = SearchResultCache(
        request.app.state.redis, ttl_seconds=settings.tavily_cache_ttl_seconds
    )
    usage_limiter = SearchUsageLimiter(
        request.app.state.redis, monthly_limit=settings.tavily_monthly_credit_limit
    )
    tavily_client = AsyncTavilyClient(api_key=settings.tavily_api_key)
    return BookSearchTool(
        tavily_client=tavily_client,
        cache=cache,
        usage_limiter=usage_limiter,
        now=get_now,
    )


def get_recommend_books_tool(
    book_search_tool: BookSearchTool = Depends(get_book_search_tool),
) -> RecommendBooksTool:
    """도서 추천 에이전트 로컬 도구."""
    settings = get_settings()
    return RecommendBooksTool(
        book_search_tool=book_search_tool,
        settings=settings,
    )


def get_consult_librarian_tool() -> ConsultLibrarianTool:
    """사서 에이전트 HTTP 스텁/원격 호출 도구."""
    settings = get_settings()
    return ConsultLibrarianTool(settings=settings)


def get_search_my_library_tool() -> SearchMyLibraryTool:
    """서재 도서 조회/검색 HTTP 도구."""
    settings = get_settings()
    return SearchMyLibraryTool(settings=settings)


def get_orchestrator_service(
    session_store: ChatSessionStore = Depends(get_chat_session_store),
    recommend_tool: RecommendBooksTool = Depends(get_recommend_books_tool),
    librarian_tool: ConsultLibrarianTool = Depends(get_consult_librarian_tool),
    library_tool: SearchMyLibraryTool = Depends(get_search_my_library_tool),
) -> OrchestratorService:
    """오케스트레이터 에이전트 서비스."""
    settings = get_settings()
    return OrchestratorService(
        session_store=session_store,
        settings=settings,
        recommend_tool=recommend_tool,
        librarian_tool=librarian_tool,
        library_tool=library_tool,
    )


def get_librarian_service(
    session_store: ChatSessionStore = Depends(get_chat_session_store),
    book_search_tool: BookSearchTool = Depends(get_book_search_tool),
) -> LibrarianService:
    """추천 에이전트 서비스 (기존 호환 및 단독 사용)."""
    settings = get_settings()
    return LibrarianService(
        session_store=session_store,
        book_search_tool=book_search_tool,
        settings=settings,
    )


def get_genre_classifier_service() -> GenreClassifierService:
    """도서 표준 장르 분류 서비스."""
    settings = get_settings()
    return GenreClassifierService(settings=settings)
