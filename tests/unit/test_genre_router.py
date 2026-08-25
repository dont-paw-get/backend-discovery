from collections.abc import AsyncGenerator

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
        "title": "클린 아키텍처",
        "author": "로버트 C. 마틴",
        "raw_category": "국내도서 > 컴퓨터/모바일 > 프로그래밍",
    }
    response = await client.post("/api/v1/classify-genre", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["genre"] == StandardGenre.COMPUTER_IT.value
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
        "title": "듄",
        "author": "프랭크 허버트",
        "raw_category": "소설",
    }
    response = await client.post("/api/v1/classify-genre", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["genre"] == "SCIENCE_FICTION"
    assert data["confidence"] == 0.97


@pytest.mark.asyncio
async def test_classify_genre_validation_error_missing_title(client: AsyncClient) -> None:
    """title 필드가 누락되었을 때 422 Unprocessable Entity를 반환한다."""
    payload = {
        "author": "저자명만 있음",
        "raw_category": "카테고리만 있음",
    }
    response = await client.post("/api/v1/classify-genre", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_classify_genre_validation_error_empty_title(client: AsyncClient) -> None:
    """title 필드가 빈 문자열일 때 422 Unprocessable Entity를 반환한다."""
    payload = {
        "title": "",
        "author": "저자명",
    }
    response = await client.post("/api/v1/classify-genre", json=payload)
    assert response.status_code == 422
