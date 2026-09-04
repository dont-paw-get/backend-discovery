"""도서 표준 장르 분류 애플리케이션 서비스.

Claude 3 Haiku(Bedrock) 또는 Mock 분류기를 활용하여 도서 메타데이터를
ERD 표준 16개 장르 체계로 분류한다.
"""

import logging
from typing import Any

from strands import Agent
from strands.models import BedrockModel

from discovery.api.schemas.genre import (
    BookClassificationRequest,
    BookClassificationResponse,
    StandardGenre,
)
from discovery.core.config import Settings
from discovery.domain.genre.classifier import (
    GENRE_CLASSIFIER_SYSTEM_PROMPT,
    build_classification_prompt,
    match_standard_genre,
    parse_classification_response,
)
from discovery.infrastructure.cache.genre_classifier_cache import GenreClassifierCache

logger = logging.getLogger(__name__)


def _extract_text_from_message(message: Any) -> str:
    """AgentResult.message에서 텍스트 콘텐츠를 안전하게 추출한다."""
    if isinstance(message, dict):
        content = message.get("content", [])
        if isinstance(content, list):
            return "".join(
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and "text" in b and isinstance(b["text"], str)
            )
    return ""


class GenreClassifierService:
    """도서 표준 장르 분류를 수행하는 애플리케이션 서비스."""

    def __init__(
        self,
        settings: Settings,
        boto_session: Any = None,
        cache: GenreClassifierCache | None = None,
    ) -> None:
        self._settings = settings
        self._boto_session = boto_session
        self._cache = cache

    def _classify_mock(self, request: BookClassificationRequest) -> BookClassificationResponse:
        """테스트 및 로컬 mock 환경을 위한 결정론적 규칙 기반 분류."""
        # 1. ISBN 문자열 매칭 (테스트 편의성)
        if request.isbn:
            matched = match_standard_genre(request.isbn)
            if matched:
                return BookClassificationResponse(genre=matched, confidence=1.0)

        # 2. 매칭되지 않을 경우 기본값 NONE
        return BookClassificationResponse(genre=StandardGenre.NONE, confidence=1.0)

    async def classify_genre(
        self, request: BookClassificationRequest
    ) -> BookClassificationResponse:
        """도서 ISBN 정보를 기반으로 ERD 표준 16개 장르 중 1개로 분류한다.

        CLIAR-282 Task 5: `cache`가 배선되어 있고 ISBN이 제공되면 먼저 캐시를 조회한다.
        Hit 시 Bedrock LLM 호출 없이 즉시 반환한다. Miss 시 기존 분류를 수행하고,
        결과가 `NONE`이 아닌 경우에만 캐시에 저장한다(불확실한 `NONE` 결과를 TTL
        기간 내내 고정시키지 않기 위함).
        """
        if self._cache is not None and request.isbn:
            cached = await self._cache.get(request.isbn)
            if cached is not None:
                genre_str, confidence = cached
                matched = match_standard_genre(genre_str)
                if matched is not None:
                    return BookClassificationResponse(genre=matched, confidence=confidence)

        response = await self._classify_genre_uncached(request)

        if self._cache is not None and request.isbn and response.genre != StandardGenre.NONE:
            await self._cache.set(request.isbn, response.genre.value, response.confidence)

        return response

    async def _classify_genre_uncached(
        self, request: BookClassificationRequest
    ) -> BookClassificationResponse:
        """캐시를 거치지 않고 실제 분류(mock 또는 Bedrock LLM)를 수행한다."""
        if self._settings.llm_provider == "mock":
            return self._classify_mock(request)

        try:
            model_kwargs: dict[str, Any] = {"model_id": self._settings.genre_classifier_model_id}
            if self._boto_session is not None:
                model_kwargs["boto_session"] = self._boto_session
            else:
                model_kwargs["region_name"] = self._settings.aws_region
            model = BedrockModel(**model_kwargs)
            agent = Agent(
                model=model,
                system_prompt=GENRE_CLASSIFIER_SYSTEM_PROMPT,
            )

            prompt = build_classification_prompt(isbn=request.isbn)

            result = await agent.invoke_async(prompt=prompt)
            raw_text = _extract_text_from_message(result.message)
            return parse_classification_response(raw_text)

        except Exception as exc:
            logger.error("LLM 장르 분류 중 오류 발생: %s", exc, exc_info=True)
            # 안전 fallback: 오류 발생 시에도 500 에러 대신 'NONE' 장르 반환
            return BookClassificationResponse(genre=StandardGenre.NONE, confidence=0.0)
