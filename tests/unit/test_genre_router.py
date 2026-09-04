from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from discovery.api.deps import get_genre_classifier_service
from discovery.api.schemas.genre import (
    BookClassificationRequest,
    BookClassificationResponse,
    StandardGenre,
)
from discovery.application.genre_classifier_service import GenreClassifierService
from discovery.core.config import Settings
from discovery.main import create_app


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    # CLIAR-282 Task 5: get_genre_classifier_service가 캐시 배선을 위해
    # request.app.state.redis를 참조하므로, lifespan을 태우지 않는 이 테스트
    # 클라이언트에서도 최소한의 mock을 채워둔다(422 검증 테스트가 실제 Redis 연결
    # 없이도 의존성 해석 단계를 통과할 수 있게 함).
    app.state.redis = MagicMock()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_classify_genre_success(app: FastAPI, client: AsyncClient) -> None:
    """정상 요청 시 200 OK와 함께 분류된 장르 응답을 반환한다."""
    mock_settings = Settings(
        redis_url="redis://localhost:6379/0",
        llm_provider="mock",
        internal_api_token="test-token",
        tavily_api_key="test-key",
    )
    app.dependency_overrides[get_genre_classifier_service] = lambda: GenreClassifierService(
        settings=mock_settings
    )

    payload = {
        "isbn": "COMPUTER_IT",
    }
    response = await client.post("/api/v1/classify-genre", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["genre"] == StandardGenre.COMPUTER_IT.value
    assert data["confidence"] == 1.0


@pytest.mark.asyncio
async def test_classify_genre_with_numeric_isbn_success(
    app: FastAPI, client: AsyncClient
) -> None:
    """숫자 ISBN 요청 시 200 OK와 함께 분류된 장르 응답을 반환한다."""
    mock_settings = Settings(
        redis_url="redis://localhost:6379/0",
        llm_provider="mock",
        internal_api_token="test-token",
        tavily_api_key="test-key",
    )
    app.dependency_overrides[get_genre_classifier_service] = lambda: GenreClassifierService(
        settings=mock_settings
    )

    payload = {
        "isbn": "9788966263769",
    }
    response = await client.post("/api/v1/classify-genre", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["genre"] == StandardGenre.NONE.value
    assert data["confidence"] == 1.0


@pytest.mark.asyncio
async def test_classify_genre_custom_mock_service(app: FastAPI, client: AsyncClient) -> None:
    """Mock 서비스 주입 시 지정된 BookClassificationResponse가 반환된다."""

    class DummyGenreService:
        async def classify_genre(
            self, request: BookClassificationRequest
        ) -> BookClassificationResponse:
            return BookClassificationResponse(
                genre=StandardGenre.SCIENCE_FICTION,
                confidence=0.97,
            )

    app.dependency_overrides[get_genre_classifier_service] = lambda: DummyGenreService()

    payload = {
        "isbn": "9788934972464",
    }
    response = await client.post("/api/v1/classify-genre", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["genre"] == "SCIENCE_FICTION"
    assert data["confidence"] == 0.97


@pytest.mark.asyncio
async def test_classify_genre_validation_error_missing_isbn(client: AsyncClient) -> None:
    """isbn 필드가 누락되었을 때 422 Unprocessable Entity를 반환한다."""
    payload: dict[str, str] = {}
    response = await client.post("/api/v1/classify-genre", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_classify_genre_validation_error_empty_isbn(client: AsyncClient) -> None:
    """isbn 필드가 빈 문자열일 때 422 Unprocessable Entity를 반환한다."""
    payload = {
        "isbn": "",
    }
    response = await client.post("/api/v1/classify-genre", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_classify_genre_validation_error_whitespace_isbn(client: AsyncClient) -> None:
    """isbn 필드가 공백 문자열일 때 422 Unprocessable Entity를 반환한다."""
    payload = {
        "isbn": "   ",
    }
    response = await client.post("/api/v1/classify-genre", json=payload)
    assert response.status_code == 422
