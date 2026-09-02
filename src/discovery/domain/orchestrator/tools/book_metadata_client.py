"""도서 서지 정보(페이지수) 검증을 위한 backend-book 알라딘 조회 클라이언트.

CLIAR-237: 추천 에이전트(LLM+Tavily 웹검색)가 생성한 페이지수는 부정확하거나
근사치("약 300쪽")일 수 있다. `backend-book`이 이미 보유한 알라딘 실조회 API
(`GET /api/v1/books/search?isbn=...`)로 ISBN 기반 검증을 수행해 정확한 값으로
덮어쓴다.

이 클라이언트는 LLM에게 노출되는 Strands `@tool`이 아니라, 서비스 레이어
(`OrchestratorService`)가 추천 카드 조립 후 내부적으로 호출하는 순수 HTTP 클라이언트다.
"""

import logging

import httpx

from discovery.core.config import Settings
from discovery.domain.orchestrator.book_metadata_response import BookMetadataSearchResponse

logger = logging.getLogger(__name__)


class BookMetadataClient:
    """ISBN으로 `backend-book`의 알라딘 서지 조회 API를 호출해 페이지수를 검증하는 클라이언트."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client

    async def fetch_total_pages(self, isbn: str) -> int | None:
        """ISBN으로 정확한 총 페이지 수를 조회한다.

        네트워크 오류, 타임아웃, 4xx/5xx, 응답 파싱 실패 등 어떤 이유로든 조회에
        실패하면 예외를 전파하지 않고 `None`을 반환한다(graceful degradation) —
        호출부는 이 경우 기존 LLM 생성값 또는 `None`을 그대로 유지해야 한다.

        Args:
            isbn: 10자리 또는 13자리 숫자 ISBN.

        Returns:
            알라딘/서재 데이터에서 확인된 총 페이지 수. 조회 실패 또는 정보 없음이면 `None`.
        """
        if not isbn or not isbn.strip():
            return None

        base = self._settings.book_metadata_api_url.rstrip("/")
        url = f"{base}/api/v1/books/search"
        params = {"isbn": isbn.strip()}
        timeout = self._settings.book_metadata_timeout_seconds

        try:
            if self._http_client is not None:
                response = await self._http_client.get(url, params=params, timeout=timeout)
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, params=params, timeout=timeout)

            if response.status_code != 200:
                logger.warning(
                    "Book metadata API returned status %d for isbn=%s",
                    response.status_code,
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
