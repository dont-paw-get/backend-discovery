"""LibrarianService 단위 테스트.

실제 AWS/Redis/Tavily 호출 없이 mocker로 세션 스토어와 에이전트 동작을 모킹하여
히스토리 주입, 에이전트 실행, 턴 저장 순서 및 스트리밍 동작을 검증한다.
"""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from discovery.application.librarian_service import (
    LibrarianService,
    extract_chunk_from_event,
    extract_text_from_message,
    format_history_for_strands,
)
from discovery.core.config import Settings


def test_extract_chunk_from_event() -> None:
    # 1. TextStreamEvent data
    assert extract_chunk_from_event({"data": "안녕"}) == "안녕"
    # 2. contentBlockDelta
    assert (
        extract_chunk_from_event({"contentBlockDelta": {"delta": {"text": "하세요"}}})
        == "하세요"
    )
    # 3. delta text
    assert extract_chunk_from_event({"delta": {"text": "!"}}) == "!"
    # 4. non-text events
    assert extract_chunk_from_event({"other": 123}) == ""
    assert extract_chunk_from_event(None) == ""


def test_format_history_for_strands() -> None:
    history = [
        {"role": "user", "content": "책 추천해줘"},
        {"role": "assistant", "content": "어떤 장르를 좋아하시나요?"},
    ]
    strands_messages = format_history_for_strands(history)

    assert strands_messages == [
        {"role": "user", "content": [{"text": "책 추천해줘"}]},
        {"role": "assistant", "content": [{"text": "어떤 장르를 좋아하시나요?"}]},
    ]


def test_extract_text_from_message() -> None:
    message = {
        "role": "assistant",
        "content": [{"text": "추천 도서는 "}, {"text": "어린왕자입니다."}],
    }
    assert extract_text_from_message(message) == "추천 도서는 어린왕자입니다."
    assert extract_text_from_message(None) == ""
    assert extract_text_from_message({}) == ""


@pytest.mark.asyncio
async def test_librarian_service_chat(mocker: MockerFixture) -> None:
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(
        return_value=[{"role": "user", "content": "이전 질문"}]
    )
    mock_session_store.append_turn = AsyncMock()

    mock_search_tool = mocker.MagicMock()
    mock_tool = mocker.MagicMock()
    mock_search_tool.as_tool.return_value = mock_tool

    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        librarian_model_id="anthropic.claude-3-haiku-20240307-v1:0",
        aws_region="us-east-1",
    )

    mock_agent = mocker.MagicMock()
    mock_result = mocker.MagicMock()
    mock_result.message = {
        "role": "assistant",
        "content": [{"text": "추천 도서 목록입니다."}],
    }
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)

    mock_create_agent = mocker.patch(
        "discovery.application.librarian_service.create_librarian_agent",
        return_value=mock_agent,
    )

    service = LibrarianService(
        session_store=mock_session_store,
        book_search_tool=mock_search_tool,
        settings=settings,
    )

    response = await service.chat(session_id="sess-123", message="SF 소설 추천해줘")

    assert response == "추천 도서 목록입니다."

    mock_session_store.get_history.assert_awaited_once_with("sess-123")
    mock_create_agent.assert_called_once_with(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        region_name="us-east-1",
        tools=[mock_tool],
        messages=[{"role": "user", "content": [{"text": "이전 질문"}]}],
    )
    mock_agent.invoke_async.assert_awaited_once_with(prompt="SF 소설 추천해줘")

    assert mock_session_store.append_turn.await_count == 2
    mock_session_store.append_turn.assert_has_awaits(
        [
            mocker.call("sess-123", {"role": "user", "content": "SF 소설 추천해줘"}),
            mocker.call("sess-123", {"role": "assistant", "content": "추천 도서 목록입니다."}),
        ]
    )


@pytest.mark.asyncio
async def test_librarian_service_stream_chat(mocker: MockerFixture) -> None:
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.append_turn = AsyncMock()

    mock_search_tool = mocker.MagicMock()
    mock_tool = mocker.MagicMock()
    mock_search_tool.as_tool.return_value = mock_tool

    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    async def fake_stream_async(prompt: str) -> Any:
        events = [
            {"data": "안녕"},
            {"data": "하세요! "},
            {"other_event": 123},
            {"data": "추천드립니다."},
        ]
        for e in events:
            yield e

    mock_agent = mocker.MagicMock()
    mock_agent.stream_async = fake_stream_async

    mocker.patch(
        "discovery.application.librarian_service.create_librarian_agent",
        return_value=mock_agent,
    )

    service = LibrarianService(
        session_store=mock_session_store,
        book_search_tool=mock_search_tool,
        settings=settings,
    )

    chunks: list[str] = []
    async for chunk in service.stream_chat(session_id="sess-456", message="동화책 추천해줘"):
        chunks.append(chunk)

    assert "".join(chunks) == "안녕하세요! 추천드립니다."

    mock_session_store.get_history.assert_awaited_once_with("sess-456")
    assert mock_session_store.append_turn.await_count == 2
    mock_session_store.append_turn.assert_has_awaits(
        [
            mocker.call("sess-456", {"role": "user", "content": "동화책 추천해줘"}),
            mocker.call(
                "sess-456",
                {"role": "assistant", "content": "안녕하세요! 추천드립니다."},
            ),
        ]
    )
