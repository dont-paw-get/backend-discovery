"""FastAPI 의존성 주입 지점. 테스트에서 이 함수들을 오버라이드해 실제 인프라를 대체한다."""

from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status
from tavily import AsyncTavilyClient

from discovery.application.genre_classifier_service import GenreClassifierService
from discovery.application.librarian_service import LibrarianService
from discovery.application.orchestrator_service import OrchestratorService
from discovery.core.cloudwatch_metrics import CloudWatchMetricsPublisher
from discovery.core.config import get_settings
from discovery.domain.orchestrator.tools.book_metadata_client import BookMetadataClient
from discovery.domain.orchestrator.tools.librarian_tool import ConsultLibrarianTool
from discovery.domain.orchestrator.tools.library_tool import SearchMyLibraryTool
from discovery.domain.orchestrator.tools.recommend_tool import RecommendBooksTool
from discovery.infrastructure.cache.book_metadata_cache import BookMetadataCache
from discovery.infrastructure.cache.chat_session_store import ChatSessionStore
from discovery.infrastructure.cache.genre_classifier_cache import GenreClassifierCache
from discovery.infrastructure.search.book_search_tool import BookSearchTool
from discovery.infrastructure.search.result_cache import SearchResultCache
from discovery.infrastructure.search.usage_limiter import SearchUsageLimiter


def get_now() -> datetime:
    """현재 시각. `datetime.now()` 직접 호출 대신 이 의존성을 통해 주입받는다.

    AGENTS.md 테스트 원칙: 제어 불가능한 값(현재 시각)은 DI로 받아 결정론적으로 테스트한다.
    """
    return datetime.now(UTC)


def get_boto_session(request: Request) -> Any:
    """CLIAR-282: `main.py` lifespan에서 생성한 프로세스 공유 `boto3.Session`.

    `BedrockModel`(Strands)이 매 요청마다 새 세션/커넥션 풀을 만들던 것을 피해
    TCP/TLS 핸드셰이크 반복 비용을 줄인다. `app.state.boto_session`이 없으면(예:
    lifespan을 안 타는 일부 테스트 컨텍스트) None을 반환해 하위 호환을 유지한다.
    """
    return getattr(request.app.state, "boto_session", None)


def require_authorization_header(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    """Authorization 헤더 존재 검증 (Presence Check).

    헤더가 누락되었거나 공백만 있는 경우 401 Unauthorized 예외를 발생시킨다.
    """
    if not authorization or not authorization.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is required",
        )
    return authorization.strip()


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
    cloudwatch_publisher = CloudWatchMetricsPublisher(
        enabled=settings.enable_cloudwatch_metrics,
        region_name=settings.aws_region,
    )
    return BookSearchTool(
        tavily_client=tavily_client,
        cache=cache,
        usage_limiter=usage_limiter,
        now=get_now,
        cloudwatch_publisher=cloudwatch_publisher,
    )


def get_book_metadata_client(request: Request) -> BookMetadataClient:
    """CLIAR-237: 추천 도서 페이지수를 알라딘 실조회로 검증하는 backend-book 서지 조회
    클라이언트. CLIAR-282 Task 5: Redis 캐시(`BookMetadataCache`)를 배선해 동일
    제목·저자 재조회 시 알라딘 외부 HTTP 호출을 건너뛴다."""
    settings = get_settings()
    cache = BookMetadataCache(
        request.app.state.redis, ttl_seconds=settings.book_metadata_cache_ttl_seconds
    )
    return BookMetadataClient(settings=settings, cache=cache)


def get_genre_classifier_service(
    request: Request,
    boto_session: Any = Depends(get_boto_session),
) -> GenreClassifierService:
    """도서 표준 장르 분류 서비스. CLIAR-282 Task 5: Redis 캐시(`GenreClassifierCache`)를
    배선해 동일 ISBN 재분류 시 Bedrock LLM 호출을 건너뛴다."""
    settings = get_settings()
    cache = GenreClassifierCache(
        request.app.state.redis, ttl_seconds=settings.genre_classifier_cache_ttl_seconds
    )
    return GenreClassifierService(settings=settings, boto_session=boto_session, cache=cache)


def get_recommend_books_tool(
    book_search_tool: BookSearchTool = Depends(get_book_search_tool),
    book_metadata_client: BookMetadataClient = Depends(get_book_metadata_client),
    genre_classifier_service: GenreClassifierService = Depends(get_genre_classifier_service),
    boto_session: Any = Depends(get_boto_session),
) -> RecommendBooksTool:
    """도서 추천 에이전트 로컬 도구."""
    settings = get_settings()
    return RecommendBooksTool(
        book_search_tool=book_search_tool,
        settings=settings,
        book_metadata_client=book_metadata_client,
        genre_classifier_service=genre_classifier_service,
        boto_session=boto_session,
    )


def get_consult_librarian_tool() -> ConsultLibrarianTool:
    """사서 에이전트 HTTP 스텁/원격 호출 도구."""
    settings = get_settings()
    return ConsultLibrarianTool(settings=settings)


def get_search_my_library_tool() -> SearchMyLibraryTool:
    """서재 도서 조회/검색 HTTP 도구."""
    settings = get_settings()
    return SearchMyLibraryTool(settings=settings)


def get_cloudwatch_metrics_publisher() -> CloudWatchMetricsPublisher:
    """CLIAR-276: 기존 Prometheus/Grafana/Loki 관측 스택과 독립적인 CloudWatch 커스텀
    메트릭(비용/토큰/캐시 히트율) 발행기. `enable_cloudwatch_metrics=False`(기본값)이면
    발행 메서드가 즉시 반환하는 no-op이 된다."""
    settings = get_settings()
    return CloudWatchMetricsPublisher(
        enabled=settings.enable_cloudwatch_metrics,
        region_name=settings.aws_region,
    )


def get_orchestrator_service(
    session_store: ChatSessionStore = Depends(get_chat_session_store),
    recommend_tool: RecommendBooksTool = Depends(get_recommend_books_tool),
    librarian_tool: ConsultLibrarianTool = Depends(get_consult_librarian_tool),
    library_tool: SearchMyLibraryTool = Depends(get_search_my_library_tool),
    cloudwatch_publisher: CloudWatchMetricsPublisher = Depends(get_cloudwatch_metrics_publisher),
    boto_session: Any = Depends(get_boto_session),
) -> OrchestratorService:
    """오케스트레이터 에이전트 서비스."""
    settings = get_settings()
    return OrchestratorService(
        session_store=session_store,
        settings=settings,
        recommend_tool=recommend_tool,
        librarian_tool=librarian_tool,
        library_tool=library_tool,
        cloudwatch_publisher=cloudwatch_publisher,
        boto_session=boto_session,
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
