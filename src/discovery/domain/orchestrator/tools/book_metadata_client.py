"""도서 서지 정보(페이지수) 검증을 위한 backend-book 알라딘 조회 클라이언트.

CLIAR-237: 추천 에이전트(LLM+Tavily 웹검색)가 생성한 페이지수는 부정확하거나
근사치("약 300쪽")일 수 있다. `backend-book`이 이미 보유한 알라딘 실조회 API로
검증을 수행해 정확한 값으로 덮어쓴다.

CLIAR-237 후속(2026-09-02): 최초 설계는 LLM이 생성한 ISBN 내부 주석
(`<!-- isbn: ... -->`)으로 `GET /api/v1/books/search?isbn=...`를 호출하는 방식이었으나,
LLM이 ISBN 자체를 못 찾아 주석을 생략하는 사례가 dev 실측에서 빈번하게 확인되어
`GET /api/v1/books/search/by-title-author`(제목·저자 교집합 검색)로 전환했다.

CLIAR-237 재수정(2026-09-02 실측): 두 가지가 추가로 확인됐다.
1. 두 엔드포인트 모두 무인증 호출 시 401(`UNAUTHORIZED`)을 반환한다 → 사용자 Bearer
   토큰을 반드시 패스스루해야 한다.
2. `by-title-author`는 ISBN은 반환하지만 목록 검색만 수행하여 `totalPages`가 항상
   null이다. 반면 `GET /api/v1/books/search?isbn=...`(ISBN 상세 조회)는 같은 책에
   `totalPages`를 정상 반환한다(사피엔스 ISBN 9788934972464 실측: by-title-author=null,
   isbn 조회=648).
따라서 `fetch_by_title_author`는 "제목·저자 → ISBN(by-title-author) → 페이지수
(search?isbn=)"의 2단 조회로 페이지수를 확보한다. `fetch_total_pages`는 이 2단 조회의
2단계로 재사용된다.

이 클라이언트는 LLM에게 노출되는 Strands `@tool`이 아니라, 도메인 도구
(`RecommendBooksTool`)가 추천 카드 조립 후 내부적으로 호출하는 순수 HTTP 클라이언트다.
"""

import logging
import re

import httpx

from discovery.core.config import Settings
from discovery.domain.orchestrator.book_metadata_response import (
    BookMetadataSearchResponse,
    BookSearchByTitleAuthorResponse,
)
from discovery.infrastructure.cache.book_metadata_cache import BookMetadataCache

logger = logging.getLogger(__name__)


def clean_title_for_search(title: str) -> str:
    """알라딘 교집합 검색 성공률을 높이기 위해 제목에서 부제 및 불필요한 기호를 정제한다."""
    if not title:
        return ""
    # 콜론(:), 대시(-), 슬래시(/) 기준 앞부분 메인 타이틀만 추출
    cleaned = re.split(r"[:\-\/]", title)[0].strip()
    # 괄호와 괄호 내부 내용 제거 (예: (개정판), [양장] 등)
    cleaned = re.sub(r"[\(\[\<].*?[\)\]\>]", "", cleaned).strip()
    return cleaned if cleaned else title.strip()


def clean_author_for_search(author: str) -> str:
    """알라딘 교집합 검색 성공률을 높이기 위해
    저자명에서 대표 저자 1인만 추출하고 수식어를 제거한다.
    """
    if not author:
        return ""
    # 쉼표(,), '외', '및', 슬래시(/), '&' 기준 첫 번째 대표 저자 추출
    first_author = re.split(r"[,/&]|(?:\s+외\b)|(?:\s+및\b)", author)[0].strip()
    # '지음', '저', '글', '원작' 등 불필요한 역할 수식어 제거
    first_author = re.sub(r"\s*(?:지음|저자|저|글|원작)$", "", first_author).strip()
    return first_author if first_author else author.strip()


def _build_auth_headers(auth_token: str | None) -> dict[str, str]:
    """Authorization 헤더 딕셔너리를 만든다.

    `backend-book`의 서지 조회 API는 무인증 호출 시 401을 반환하므로(dev 실측 확인),
    사용자 Bearer 토큰을 반드시 전달해야 한다. `auth_token`이 없으면 빈 헤더를 반환한다
    (호출부는 401 → None graceful degradation으로 흡수).
    """
    headers = {"Accept": "application/json"}
    if auth_token and auth_token.strip():
        token = auth_token.strip()
        headers["Authorization"] = token if token.startswith("Bearer ") else f"Bearer {token}"
    return headers


class BookMetadataClient:
    """`backend-book`의 알라딘 서지 조회 API를 호출해 페이지수를 검증하는 클라이언트."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
        cache: BookMetadataCache | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client
        self._cache = cache

    async def _get(
        self, url: str, params: dict[str, str], auth_token: str | None
    ) -> httpx.Response | None:
        """공통 GET 실행 헬퍼. 예외는 삼키고 `None`을 반환한다(graceful degradation)."""
        headers = _build_auth_headers(auth_token)
        timeout = self._settings.book_metadata_timeout_seconds
        if self._http_client is not None:
            return await self._http_client.get(
                url, params=params, headers=headers, timeout=timeout
            )
        async with httpx.AsyncClient() as client:
            return await client.get(url, params=params, headers=headers, timeout=timeout)

    async def fetch_total_pages(self, isbn: str, auth_token: str | None = None) -> int | None:
        """ISBN으로 정확한 총 페이지 수를 조회한다(`GET /api/v1/books/search?isbn=...`).

        이 엔드포인트는 ISBN 상세 조회(알라딘 ItemLookup)까지 수행하므로 `totalPages`가
        채워진다(제목·저자 검색 엔드포인트는 목록 검색만 하여 `totalPages`가 null인 것과
        대비됨 — dev 실측 확인, 2026-09-02).

        네트워크 오류, 타임아웃, 4xx/5xx(무인증 401 포함), 응답 파싱 실패 등 어떤
        이유로든 조회에 실패하면 예외를 전파하지 않고 `None`을 반환한다
        (graceful degradation).

        Args:
            isbn: 10자리 또는 13자리 숫자 ISBN.
            auth_token: 사용자 Bearer 토큰(라우터에서 패스스루). 미전달 시 401로 None.

        Returns:
            알라딘/서재 데이터에서 확인된 총 페이지 수. 조회 실패 또는 정보 없음이면 `None`.
        """
        if not isbn or not isbn.strip():
            return None

        base = self._settings.book_metadata_api_url.rstrip("/")
        url = f"{base}/api/v1/books/search"
        params = {"isbn": isbn.strip()}

        try:
            response = await self._get(url, params, auth_token)
            if response is None or response.status_code != 200:
                logger.warning(
                    "Book metadata API returned status %s for isbn=%s",
                    response.status_code if response is not None else "N/A",
                    isbn,
                )
                return None

            data = response.json()
            parsed = BookMetadataSearchResponse.model_validate(data)
            return parsed.total_pages
        except Exception:
            logger.warning(
                "Failed to fetch book metadata for isbn=%s (falling back to None)",
                isbn,
                exc_info=True,
            )
            return None

    async def fetch_by_title_author(
        self, title: str, author: str, auth_token: str | None = None
    ) -> int | None:
        """제목·저자로 알라딘 교집합 검색을 수행해 총 페이지 수를 조회한다.

        2단 조회(dev 실측 기반, 2026-09-02):
        `GET /api/v1/books/search/by-title-author`는 교집합 도서의 ISBN은 반환하지만
        목록 검색만 수행하여 `totalPages`가 항상 null이다. 따라서 여기서 얻은 ISBN으로
        `fetch_total_pages`(`GET /api/v1/books/search?isbn=...`, ISBN 상세 조회)를 재호출해
        정확한 페이지수를 확보한다. 만약 by-title-author가 예외적으로 `totalPages`를
        직접 채워주면(향후 backend-book 개선 시) 재조회 없이 그 값을 그대로 쓴다.

        네트워크 오류, 타임아웃, 4xx/5xx(무인증 401 포함), 응답 파싱 실패, 검색 결과
        없음(`book` 필드 생략) 등 어떤 이유로든 조회에 실패하면 예외를 전파하지 않고
        `None`을 반환한다(graceful degradation).

        Args:
            title: 도서 제목.
            author: 저자명.
            auth_token: 사용자 Bearer 토큰(라우터에서 패스스루). 미전달 시 401로 None.

        Returns:
            검증된 총 페이지 수. 조회 실패 또는 검색 결과 없음이면 `None`.
        """
        if not title or not title.strip() or not author or not author.strip():
            return None

        base = self._settings.book_metadata_api_url.rstrip("/")
        url = f"{base}/api/v1/books/search/by-title-author"
        params = {"title": title.strip(), "author": author.strip()}

        try:
            response = await self._get(url, params, auth_token)
            if response is None or response.status_code != 200:
                logger.warning(
                    "Book search-by-title-author API returned status %s for title=%s",
                    response.status_code if response is not None else "N/A",
                    title,
                )
                return None

            data = response.json()
            parsed = BookSearchByTitleAuthorResponse.model_validate(data)

            # 1) by-title-author가 페이지수를 직접 주면 그대로 사용(향후 개선 대비).
            if parsed.total_pages is not None:
                return parsed.total_pages

            # 2) 페이지수가 null이면(현재 기본 동작), 얻은 ISBN으로 상세 조회 재시도.
            isbn = parsed.isbn
            if isbn:
                return await self.fetch_total_pages(isbn, auth_token=auth_token)
            return None
        except Exception:
            logger.warning(
                "Failed to fetch book metadata for title=%s, author=%s (falling back to None)",
                title,
                author,
                exc_info=True,
            )
            return None

    async def fetch_isbn_and_pages(
        self, title: str, author: str, auth_token: str | None = None
    ) -> tuple[str | None, int | None]:
        """제목·저자로 알라딘 교집합 검색을 수행해 ISBN과 총 페이지 수를 함께 조회한다.

        CLIAR-282: 추천 도서 장르를 결정론적으로 보강하기 위해 `GenreClassifierService`에
        넘길 ISBN이 필요해졌다. `fetch_by_title_author`(페이지수만 반환)와 동일한
        HTTP 조회를 수행하지만 ISBN도 함께 반환한다는 점만 다르다(하위 호환을 위해
        기존 메서드는 그대로 유지하고 별도 메서드로 분리).

        CLIAR-282 Task 5: `cache`가 배선되어 있으면 제목·저자로 먼저 캐시를 조회한다.
        Hit 시 알라딘 HTTP 호출 없이 즉시 반환한다(dev 실측으로 확인된 1.3~5.3초 지연을
        수 ms로 단축). Miss 시 기존 2단 조회를 그대로 수행하고, 조회에 성공한 경우에만
        결과를 캐시에 저장한다(실패로 `(None, None)`이 나온 경우는 캐싱하지 않음 —
        일시적 네트워크 오류를 TTL 기간 내내 실패로 고정시키지 않기 위함).

        네트워크 오류, 타임아웃, 4xx/5xx(무인증 401 포함), 응답 파싱 실패, 검색 결과
        없음 등 어떤 이유로든 조회에 실패하면 예외를 전파하지 않고 `(None, None)`을
        반환한다(graceful degradation).

        Args:
            title: 도서 제목.
            author: 저자명.
            auth_token: 사용자 Bearer 토큰(라우터에서 패스스루). 미전달 시 401로 (None, None).

        Returns:
            `(isbn, total_pages)` 튜플. 조회 실패 또는 검색 결과 없음이면 각각 `None`.
        """
        if not title or not title.strip() or not author or not author.strip():
            return (None, None)

        if self._cache is not None:
            cached = await self._cache.get(title, author)
            if cached is not None:
                return cached

        isbn, pages_from_step1 = await self._fetch_isbn_step1(title, author, auth_token)
        result: tuple[str | None, int | None]
        if isbn is None:
            result = (None, None)
        elif pages_from_step1 is not None:
            # by-title-author가 페이지수를 직접 주면 그대로 사용(향후 개선 대비).
            result = (isbn, pages_from_step1)
        else:
            pages = await self.fetch_total_pages(isbn, auth_token=auth_token)
            result = (isbn, pages)

        if self._cache is not None and result != (None, None):
            await self._cache.set(title, author, result[0], result[1])

        return result

    async def fetch_isbn_only(
        self, title: str, author: str, auth_token: str | None = None
    ) -> str | None:
        """제목·저자로 알라딘 교집합 검색을 수행해 ISBN만 조회한다(1단계 조회 전용).

        CLIAR-282 병렬화: "ISBN 확보"만 먼저 끝내면 그 ISBN을 필요로 하는 "페이지수
        2단계 조회"와 "장르 분류 LLM 호출"이 서로 의존성이 없어져 동시에 실행할 수
        있다. `RecommendBooksTool._verify_page_counts`가 이 메서드로 먼저 ISBN을
        모두 확보한 뒤, 페이지수 조회와 장르 분류를 `asyncio.gather`로 함께 실행해
        후처리 구간을 단축한다.

        `by-title-author`가 `totalPages`를 예외적으로 직접 채워주는 경우(향후
        backend-book 개선 대비)에도 이 메서드는 ISBN만 반환한다 — 그 값이 필요하면
        `fetch_isbn_and_pages`(캐시 포함 전체 조회)를 사용한다.

        네트워크 오류, 타임아웃, 4xx/5xx(무인증 401 포함), 응답 파싱 실패, 검색 결과
        없음 등 어떤 이유로든 조회에 실패하면 예외를 전파하지 않고 `None`을 반환한다
        (graceful degradation).

        Args:
            title: 도서 제목.
            author: 저자명.
            auth_token: 사용자 Bearer 토큰(라우터에서 패스스루). 미전달 시 401로 `None`.

        Returns:
            ISBN. 조회 실패 또는 검색 결과 없음이면 `None`.
        """
        isbn, _ = await self._fetch_isbn_step1(title, author, auth_token)
        return isbn

    async def get_cached_isbn_and_pages(
        self, title: str, author: str
    ) -> tuple[str | None, int | None] | None:
        """캐시에서 (ISBN, 페이지수)를 조회한다. 캐시가 없거나 미스면 `None`.

        CLIAR-282 병렬화: `RecommendBooksTool`이 책 단위로 캐시 히트/미스를 먼저
        판단해, 히트한 책은 HTTP 호출 없이 즉시 값을 쓰고 미스한 책만 1단계 ISBN
        확보 후 "페이지수 조회"와 "장르 분류"를 병렬 실행하도록 조율하는 데 쓰인다.
        """
        if self._cache is None:
            return None
        return await self._cache.get(title, author)

    async def cache_isbn_and_pages(
        self, title: str, author: str, isbn: str | None, total_pages: int | None
    ) -> None:
        """(ISBN, 페이지수)를 캐시에 저장한다. 캐시가 배선되지 않았으면 아무 동작도 하지 않는다.

        호출부(`RecommendBooksTool`)가 조회 성공 여부를 이미 판단했으므로, 이 메서드는
        무조건 저장한다(`fetch_isbn_and_pages`처럼 실패 시 캐싱을 막는 판단은 호출부 책임).
        """
        if self._cache is None:
            return
        await self._cache.set(title, author, isbn, total_pages)

    async def _fetch_isbn_step1(
        self, title: str, author: str, auth_token: str | None
    ) -> tuple[str | None, int | None]:
        """`by-title-author` 1단계 조회만 수행한다. `(isbn, total_pages)`를 반환하되
        `total_pages`는 이 엔드포인트가 예외적으로 직접 채워준 경우에만 값이 있다
        (현재 기본 동작은 `None` — 2단계 `fetch_total_pages` 재조회가 필요함을 뜻함).
        """
        if not title or not title.strip() or not author or not author.strip():
            return (None, None)

        base = self._settings.book_metadata_api_url.rstrip("/")
        url = f"{base}/api/v1/books/search/by-title-author"
        search_title = clean_title_for_search(title)
        search_author = clean_author_for_search(author)
        params = {"title": search_title, "author": search_author}

        try:
            response = await self._get(url, params, auth_token)
            if response is None or response.status_code != 200:
                logger.warning(
                    "Book search-by-title-author API returned status %s for title=%s "
                    "(searched as '%s')",
                    response.status_code if response is not None else "N/A",
                    title,
                    search_title,
                )
                return (None, None)

            data = response.json()
            parsed = BookSearchByTitleAuthorResponse.model_validate(data)
            return (parsed.isbn, parsed.total_pages)
        except Exception:
            logger.warning(
                "Failed to fetch isbn for title=%s, author=%s (falling back to None)",
                title,
                author,
                exc_info=True,
            )
            return (None, None)

