"""서재 도서 CRUD 서비스(backend-book)와 HTTP로 통신하는 서재 검색 도구."""

import logging
from collections.abc import Callable
from typing import Any

import httpx
from strands import tool

from discovery.core.config import Settings
from discovery.domain.orchestrator.library_response import (
    LibraryBookItem,
    LibraryBooksResponse,
)

logger = logging.getLogger(__name__)

READING_STATUS_KO = {
    "READING": "읽는 중",
    "COMPLETED": "완독",
    "WISH": "읽고 싶은 책",
    "PAUSED": "잠시 멈춤",
    "STOPPED": "중단",
}


class LibraryAuthError(Exception):
    """서재 API(backend-book)가 인증 실패(401)를 반환했을 때 발생하는 예외.

    LLM 도구 실행 경로를 거치면 예외 정보가 보존되지 않을 수 있으므로,
    `on_auth_failed` 콜백을 통해 서비스 레이어에 직접 신호를 전달하는 데 사용한다.
    """


def format_books_for_llm(books: list[LibraryBookItem], query: str = "") -> str:
    """조회된 서재 도서 목록을 LLM이 분석하기 쉬운 정형 텍스트로 포맷팅한다."""
    if not books:
        if query:
            return f"사용자의 서재에서 '{query}' 관련 도서를 찾지 못했습니다."
        return "사용자의 서재에 등록된 도서가 없습니다."

    lines: list[str] = [f"[내 서재 도서 목록] (총 {len(books)}권)"]
    for idx, b in enumerate(books, start=1):
        status_text = READING_STATUS_KO.get(b.reading_status or "", b.reading_status or "미설정")
        progress_text = f"{b.progress}%" if b.progress is not None else "정보 없음"
        lines.append(f"{idx}. 제목: {b.title}")
        if b.author:
            lines.append(f"   - 저자: {b.author}")
        if b.genre:
            lines.append(f"   - 장르: {b.genre}")
        lines.append(f"   - 독서 상태: {status_text} (진행률: {progress_text})")

    return "\n".join(lines)


class SearchMyLibraryTool:
    """사용자의 서재 도서 목록을 조회하고 검색/필터링하는 도구."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client

    async def search(
        self,
        query: str = "",
        author: str | None = None,
        reading_status: str | None = None,
        auth_token: str | None = None,
    ) -> list[LibraryBookItem]:
        # 라우터 수준에서 require_authorization_header로 401 차단되지만,
        # 도구 직접 호출 등에서의 심층 방어(Defense in Depth)를 위해
        # 안전하게 빈 리스트 반환을 보존한다.
        if not auth_token:
            logger.warning("auth_token is missing for search_my_library.")
            return []

        base = self._settings.library_api_url.rstrip("/")
        url = f"{base}/api/v1/library/books"

        params: dict[str, Any] = {
            "page": 0,
            "size": 100,
        }
        if author:
            params["author"] = author.strip()

        token_header = (
            auth_token if auth_token.startswith("Bearer ") else f"Bearer {auth_token}"
        )
        headers = {
            "Authorization": token_header,
            "Accept": "application/json",
        }

        timeout = self._settings.library_http_timeout_seconds
        logger.info("Calling Library API at %s with params: %s", url, params)

        try:
            if self._http_client is not None:
                response = await self._http_client.get(
                    url, params=params, headers=headers, timeout=timeout
                )
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        url, params=params, headers=headers, timeout=timeout
                    )

            logger.info("Library API response status: %d", response.status_code)
            if response.status_code == 200:
                data = response.json()
                logger.debug("Library API raw payload: %s", data)
                parsed = LibraryBooksResponse.model_validate(data)
                books = parsed.books
                logger.info("Parsed %d books from Library API", len(books))

                # query가 주어지면 제목, 저자, 장르 부분 일치 필터링
                if query and query.strip():
                    q_lower = query.strip().lower()
                    books = [
                        b
                        for b in books
                        if (b.title and q_lower in b.title.lower())
                        or (b.author and q_lower in b.author.lower())
                        or (b.genre and q_lower in b.genre.lower())
                    ]

                # reading_status 필터링
                if reading_status and reading_status.strip():
                    st_upper = reading_status.strip().upper()
                    books = [
                        b
                        for b in books
                        if b.reading_status and b.reading_status.upper() == st_upper
                    ]

                return books

            if response.status_code == 401:
                # 위조/만료된 토큰: backend-book이 인증 실패를 명확히 알려준 경우.
                # 빈 리스트로 조용히 흡수하지 않고 별도 예외로 알려 라우터가 401을
                # 클라이언트에 전달할 수 있게 한다 (ADR 0007 2.2절).
                logger.warning("Library API returned 401 (invalid/expired token)")
                raise LibraryAuthError("Library API authentication failed")

            logger.warning(
                "Library API returned status %d: %s", response.status_code, response.text
            )
            return []
        except LibraryAuthError:
            raise
        except Exception:
            logger.exception("Failed to connect to Library API at %s", url)
            return []

    def as_tool(
        self,
        auth_token: str | None = None,
        on_books_fetched: Callable[[list[LibraryBookItem]], None] | None = None,
        on_auth_failed: Callable[[], None] | None = None,
    ) -> Any:
        """Strands 오케스트레이터 에이전트에 등록할 @tool 함수를 반환한다.

        인증 토큰은 서비스 레이어에서 클로저로 주입되어
        LLM은 검색 키워드 및 조건만 인자로 전달한다 (IDOR 방지).
        조회된 도서 목록은 on_books_fetched 콜백을 통해 서비스 레이어로 안전하게 수집된다.
        backend-book이 401(인증 실패)을 반환하면 on_auth_failed 콜백으로 서비스
        레이어에 신호를 전달한다 — LLM 에이전트 루프를 거치면 예외 정보가 보존되지
        않을 수 있으므로 콜백으로 직접 알린다.
        """

        @tool(name="search_my_library")
        async def search_my_library_tool(
            query: str = "",
            author: str = "",
            reading_status: str = "",
        ) -> str:
            """로그인한 사용자의 서재에 등록된 도서 목록을 검색하거나 조회합니다.

            사용자가 내 서재에 특정 도서/작가의 책이 있는지 묻거나, 내가 읽고 있는 책,
            완독한 책 목록을 확인하려 할 때, 또는 내 서재 도서를 기반으로 새로운 책을
            추천받으려 할 때 먼저 호출합니다.

            Args:
                query: 검색할 도서 제목, 저자명, 장르 또는 키워드
                    (예: '살인자의 기억법', 'SF', '김영하').
                author: 특정 저자명으로 필터링할 경우 (선택, 예: '김영하').
                reading_status: 독서 상태 필터 (선택,
                    'READING'=읽는중, 'COMPLETED'=완독, 'WISH'=읽고싶은책).
            """
            try:
                books = await self.search(
                    query=query,
                    author=author or None,
                    reading_status=reading_status or None,
                    auth_token=auth_token,
                )
            except LibraryAuthError:
                if on_auth_failed is not None:
                    try:
                        on_auth_failed()
                    except Exception:
                        logger.exception("Failed to execute on_auth_failed callback")
                return "인증 정보가 유효하지 않아 서재를 조회할 수 없습니다."

            if on_books_fetched is not None and books:
                try:
                    on_books_fetched(books)
                except Exception:
                    logger.exception("Failed to execute on_books_fetched callback")
            return format_books_for_llm(books, query=query)

        return search_my_library_tool
