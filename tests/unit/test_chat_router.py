"""/chat API 라우터 단위 테스트.

FastAPI 의존성 주입 오버라이드를 통해 OrchestratorService를 Mock으로 대체하고,
JSON 응답, 스트리밍 응답, 유효성 검사(Pydantic)를 검증한다.
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from discovery.api.deps import get_orchestrator_service
from discovery.main import app


@pytest.mark.asyncio
async def test_chat_json_response() -> None:
    mock_service = MagicMock()
    mock_service.chat = AsyncMock(return_value="추천해드리는 도서는 '어린 왕자'입니다.")

    app.dependency_overrides[get_orchestrator_service] = lambda: mock_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat",
                json={"session_id": "sess-test-1", "message": "동화책 추천해줘"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "sess-test-1"
        assert data["message"] == "추천해드리는 도서는 '어린 왕자'입니다."
        mock_service.chat.assert_awaited_once_with(
            session_id="sess-test-1", message="동화책 추천해줘"
        )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_generates_session_id_if_empty() -> None:
    mock_service = MagicMock()
    mock_service.chat = AsyncMock(return_value="답변입니다.")

    app.dependency_overrides[get_orchestrator_service] = lambda: mock_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat",
                json={"message": "질문"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["session_id"]) > 0
        assert data["message"] == "답변입니다."
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_accepts_null_session_id() -> None:
    mock_service = MagicMock()
    mock_service.chat = AsyncMock(return_value="답변입니다.")

    app.dependency_overrides[get_orchestrator_service] = lambda: mock_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat",
                json={"session_id": None, "message": "질문"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["session_id"]) > 0
        assert data["message"] == "답변입니다."
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_streaming_response() -> None:
    async def fake_stream_chat(session_id: str, message: str) -> AsyncGenerator[str, None]:
        chunks = ["사서 ", "추천 ", "도서입니다."]
        for chunk in chunks:
            yield chunk

    mock_service = MagicMock()
    mock_service.stream_chat = fake_stream_chat

    app.dependency_overrides[get_orchestrator_service] = lambda: mock_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat",
                json={"session_id": "sess-stream-1", "message": "질문", "stream": True},
            )

        assert response.status_code == 200
        assert response.text == "사서 추천 도서입니다."
        assert response.headers.get("x-session-id") == "sess-stream-1"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_validation_error_on_empty_message() -> None:
    mock_service = MagicMock()
    app.dependency_overrides[get_orchestrator_service] = lambda: mock_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat",
                json={"session_id": "sess-1", "message": ""},
            )

        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
