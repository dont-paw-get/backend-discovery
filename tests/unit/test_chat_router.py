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
    mock_service.chat = AsyncMock(
        return_value=("추천해드리는 도서는 '어린 왕자'입니다.", None, None, None)
    )

    app.dependency_overrides[get_orchestrator_service] = lambda: mock_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat",
                json={
                    "session_id": "sess-test-1",
                    "message": "동화책 추천해줘",
                    "latitude": 37.5665,
                    "longitude": 126.9780,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "sess-test-1"
        assert data["message"] == "추천해드리는 도서는 '어린 왕자'입니다."
        assert data["switch_to"] is None
        assert data["signals"] is None
        assert data["library_books"] is None
        mock_service.chat.assert_awaited_once_with(
            session_id="sess-test-1",
            message="동화책 추천해줘",
            librarian_id=None,
            latitude=37.5665,
            longitude=126.9780,
            auth_token=None,
        )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_json_response_with_library_books() -> None:
    from discovery.api.schemas.chat import LibraryBookCard

    mock_service = MagicMock()
    mock_books = [
        LibraryBookCard(
            book_id=101,
            title="성공하는 인생의 비밀",
            author="이수진",
            reading_status="READING",
            progress=88,
        )
    ]
    mock_service.chat = AsyncMock(
        return_value=(
            "서재에 읽고 계신 책이 한 권 있습니다.",
            None,
            None,
            mock_books,
        )
    )

    app.dependency_overrides[get_orchestrator_service] = lambda: mock_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat",
                json={"session_id": "sess-test-lib", "message": "내 서재 책 보여줘"},
                headers={"Authorization": "Bearer token-123"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["library_books"] is not None
        assert len(data["library_books"]) == 1
        assert data["library_books"][0]["book_id"] == 101
        assert data["library_books"][0]["title"] == "성공하는 인생의 비밀"
        assert data["library_books"][0]["progress"] == 88
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_passes_authorization_header() -> None:
    mock_service = MagicMock()
    mock_service.chat = AsyncMock(
        return_value=("서재에 살인자의 기억법이 있습니다.", None, None, None)
    )

    app.dependency_overrides[get_orchestrator_service] = lambda: mock_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat",
                json={
                    "session_id": "sess-test-auth",
                    "message": "내 서재 책 있어?",
                },
                headers={"Authorization": "Bearer jwt-token-xyz"},
            )

        assert response.status_code == 200
        mock_service.chat.assert_awaited_once_with(
            session_id="sess-test-auth",
            message="내 서재 책 있어?",
            librarian_id=None,
            latitude=None,
            longitude=None,
            auth_token="Bearer jwt-token-xyz",
        )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_json_response_with_switch_to() -> None:
    from discovery.api.schemas.chat import SwitchToSuggestion

    mock_service = MagicMock()
    mock_service.chat = AsyncMock(
        return_value=(
            "황새 사서에게 안내해 드릴게요.",
            SwitchToSuggestion(id="stork", name="황새 사서", icon="🪶", genres=["시"]),
            None,
            None,
        )
    )

    app.dependency_overrides[get_orchestrator_service] = lambda: mock_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat",
                json={"session_id": "sess-test-stork", "message": "시 읽고 싶어"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "sess-test-stork"
        assert data["message"] == "황새 사서에게 안내해 드릴게요."
        assert data["switch_to"] is not None
        assert data["switch_to"]["id"] == "stork"
        assert data["switch_to"]["name"] == "황새 사서"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_generates_session_id_if_empty() -> None:
    mock_service = MagicMock()
    mock_service.chat = AsyncMock(return_value=("답변입니다.", None, None, None))

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
    mock_service.chat = AsyncMock(return_value=("답변입니다.", None, None, None))

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
    from discovery.domain.orchestrator.librarian_response import (
        LibrarianSignals,
        SwitchToSuggestion,
        WeatherSignal,
    )

    async def fake_stream_chat(
        session_id: str,
        message: str,
        librarian_id: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        auth_token: str | None = None,
    ) -> AsyncGenerator[str, None]:
        chunks = ["사서 ", "추천 ", "도서입니다."]
        for chunk in chunks:
            yield chunk

    mock_signals = LibrarianSignals(
        weather=WeatherSignal(condition="clear", temperature=27.5, description="맑음"),
        time_of_day="day",
        mood="cozy",
        genre_focus=["소설", "에세이"],
    )
    mock_switch_to = SwitchToSuggestion(id="stork", name="황새 사서", icon="🪶")

    mock_service = MagicMock()
    mock_service.stream_chat = fake_stream_chat
    mock_service.get_initial_meta = AsyncMock(return_value=(mock_signals, mock_switch_to))

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
        assert response.headers.get("x-signals") is not None
        assert response.headers.get("x-switch-to") is not None
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


@pytest.mark.asyncio
async def test_chat_validation_accepts_up_to_2000_chars() -> None:
    mock_service = MagicMock()
    mock_service.chat = AsyncMock(return_value=("2000자 정상 처리 응답입니다.", None, None, None))
    app.dependency_overrides[get_orchestrator_service] = lambda: mock_service

    long_message = "가" * 2000
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat",
                json={"session_id": "sess-long-2000", "message": long_message},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "2000자 정상 처리 응답입니다."
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_validation_error_on_exceeding_2000_chars() -> None:
    mock_service = MagicMock()
    app.dependency_overrides[get_orchestrator_service] = lambda: mock_service

    too_long_message = "가" * 2001
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat",
                json={"session_id": "sess-too-long", "message": too_long_message},
            )

        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cors_expose_headers_configured() -> None:
    mock_service = MagicMock()
    mock_service.chat = AsyncMock(return_value=("CORS 응답입니다.", None, None, None))
    app.dependency_overrides[get_orchestrator_service] = lambda: mock_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat",
                json={"message": "안녕"},
                headers={"Origin": "http://localhost:5173"},
            )

        assert response.status_code == 200
        exposed = response.headers.get("access-control-expose-headers", "")
        exposed_list = [h.strip() for h in exposed.split(",")]
        assert "X-Session-Id" in exposed_list
        assert "X-Signals" in exposed_list
        assert "X-Switch-To" in exposed_list
        assert "X-Library-Books" in exposed_list
    finally:
        app.dependency_overrides.clear()




