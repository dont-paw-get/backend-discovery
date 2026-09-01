"""OrchestratorService 단위 테스트.

실제 AWS/Redis/외부 서비스 호출 없이 mocker로 세션 스토어와 에이전트 동작을 모킹하여
히스토리 주입, 도구 주입, 에이전트 실행, 턴 저장 순서 및 스트리밍 동작을 검증한다.
"""

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from discovery.application.orchestrator_service import OrchestratorService
from discovery.core.config import Settings
from discovery.domain.orchestrator.librarian_response import (
    LibrarianResponse,
    LibrarianSignals,
    SwitchToSuggestion,
    WeatherSignal,
)


@pytest.mark.asyncio
async def test_orchestrator_service_chat(mocker: MockerFixture) -> None:
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(
        return_value=[{"role": "user", "content": "이전 대화"}]
    )
    mock_session_store.get_session_meta = AsyncMock(return_value={})
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.append_turn = AsyncMock()

    mock_tool = mocker.MagicMock()

    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        orchestrator_model_id="anthropic.claude-3-haiku-20240307-v1:0",
        aws_region="us-east-1",
    )

    mock_agent = mocker.MagicMock()
    mock_result = mocker.MagicMock()
    mock_result.message = {
        "role": "assistant",
        "content": [{"text": "안녕하세요! 오케스트레이터 응답입니다."}],
    }
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)

    mock_create_agent = mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=settings,
        tools=[mock_tool],
    )

    response, switch_to, signals, library_books = await service.chat(
        session_id="sess-orch-1", message="도서 추천해줘"
    )

    assert response == "안녕하세요! 오케스트레이터 응답입니다."
    assert switch_to is None
    assert signals is None
    assert library_books is None

    mock_session_store.get_history.assert_awaited_once_with("sess-orch-1")
    mock_create_agent.assert_called_once_with(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        region_name="us-east-1",
        librarian_id="cat",
        tools=[mock_tool],
        messages=[{"role": "user", "content": [{"text": "이전 대화"}]}],
    )
    mock_agent.invoke_async.assert_awaited_once_with(prompt="도서 추천해줘")

    assert mock_session_store.append_turn.await_count == 2
    mock_session_store.append_turn.assert_has_awaits(
        [
            mocker.call("sess-orch-1", {"role": "user", "content": "도서 추천해줘"}),
            mocker.call(
                "sess-orch-1",
                {"role": "assistant", "content": "안녕하세요! 오케스트레이터 응답입니다."},
            ),
        ]
    )


@pytest.mark.asyncio
async def test_orchestrator_service_chat_with_coordinates_and_switch_to(
    mocker: MockerFixture,
) -> None:
    from discovery.domain.orchestrator.librarian_response import LibrarianResponse

    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.get_session_meta = AsyncMock(
        return_value={"librarian_id": "cat", "latitude": 37.5, "longitude": 127.0}
    )
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.append_turn = AsyncMock()

    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    mock_librarian_tool = mocker.MagicMock()
    mock_recommend_tool = mocker.MagicMock()

    # 사서 도구가 호출되었을 때 switch_to를 포함하는 LibrarianResponse를 발생시키는 시뮬레이션
    def fake_as_tool(**kwargs: Any) -> Any:
        on_response = kwargs.get("on_response")

        async def fake_tool_func(message: str) -> str:
            if on_response:
                on_response(
                    LibrarianResponse(
                        message="황새 사서에게 안내해 드릴게요.",
                        switch_to={"id": "stork", "name": "황새 사서", "genres": ["시"]},
                    )
                )
            return "황새 사서에게 안내해 드릴게요."

        return fake_tool_func

    mock_librarian_tool.as_tool.side_effect = fake_as_tool

    mock_agent = mocker.MagicMock()
    mock_result = mocker.MagicMock()
    mock_result.message = {
        "role": "assistant",
        "content": [{"text": "사서님의 추천입니다: 황새 사서에게 안내해 드릴게요."}],
    }

    async def fake_invoke(prompt: str) -> Any:
        # tool 실행 트리거
        tool_fn = mock_librarian_tool.as_tool.call_args[1]["on_response"]
        tool_fn(
            LibrarianResponse(
                message="황새 사서에게 안내해 드릴게요.",
                switch_to={"id": "stork", "name": "황새 사서", "genres": ["시"]},
            )
        )
        return mock_result

    mock_agent.invoke_async.side_effect = fake_invoke

    mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=settings,
        recommend_tool=mock_recommend_tool,
        librarian_tool=mock_librarian_tool,
    )

    response, switch_to, signals, library_books = await service.chat(
        session_id="sess-switch-1",
        message="시 추천해줘",
        latitude=37.5665,
        longitude=126.9780,
    )

    assert "사서님의 추천입니다" in response
    assert switch_to is not None
    assert switch_to.id == "stork"
    assert switch_to.name == "황새 사서"
    assert library_books is None

    # 좌표 저장 및 사서 switch_to 갱신 확인
    mock_session_store.update_session_meta.assert_has_awaits(
        [
            mocker.call("sess-switch-1", latitude=37.5665, longitude=126.9780),
            mocker.call("sess-switch-1", librarian_id="stork"),
        ]
    )


@pytest.mark.asyncio
async def test_orchestrator_service_stream_chat(mocker: MockerFixture) -> None:
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.get_session_meta = AsyncMock(return_value={})
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.append_turn = AsyncMock()

    mock_tool = mocker.MagicMock()

    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    async def fake_stream_async(prompt: str) -> Any:
        events = [
            {"data": "안녕"},
            {"data": "하세요! "},
            {"data": "도움을 드릴게요."},
        ]
        for e in events:
            yield e

    mock_agent = mocker.MagicMock()
    mock_agent.stream_async = fake_stream_async

    mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=settings,
        tools=[mock_tool],
    )

    chunks: list[str] = []
    async for chunk in service.stream_chat(session_id="sess-orch-2", message="안녕"):
        chunks.append(chunk)

    assert "".join(chunks) == "안녕하세요! 도움을 드릴게요."

    mock_session_store.get_history.assert_awaited_once_with("sess-orch-2")
    assert mock_session_store.append_turn.await_count == 2
    mock_session_store.append_turn.assert_has_awaits(
        [
            mocker.call("sess-orch-2", {"role": "user", "content": "안녕"}),
            mocker.call(
                "sess-orch-2",
                {"role": "assistant", "content": "안녕하세요! 도움을 드릴게요."},
            ),
        ]
    )


def test_extract_fallback_text() -> None:
    from discovery.application.orchestrator_service import extract_fallback_text

    # 1. messages에 toolResult가 있는 경우
    mock_agent = MagicMock()
    mock_agent.messages = [
        {"role": "user", "content": [{"text": "추천해줘"}]},
        {
            "role": "assistant",
            "content": [{"toolUse": {"name": "recommend_books", "toolUseId": "call_1"}}],
        },
        {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": "call_1",
                        "content": [{"text": "### 📖 불편한 편의점\n- **저자**: 김호연"}],
                    }
                }
            ],
        },
    ]

    result = extract_fallback_text(mock_agent)
    assert result == "### 📖 불편한 편의점\n- **저자**: 김호연"

    # 2. messages가 비어있는 경우
    mock_empty_agent = MagicMock()
    mock_empty_agent.messages = []
    assert extract_fallback_text(mock_empty_agent) == ""


@pytest.mark.asyncio
async def test_orchestrator_service_stream_chat_uses_fallback_when_empty(
    mocker: MockerFixture,
) -> None:
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.get_session_meta = AsyncMock(return_value={})
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.append_turn = AsyncMock()

    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    async def fake_empty_stream_async(prompt: str) -> Any:
        # 텍스트 이벤트 없이 다른 이벤트만 발생하는 시나리오
        yield {"init_event_loop": True}

    mock_agent = MagicMock()
    mock_agent.stream_async = fake_empty_stream_async
    mock_agent.messages = [
        {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "content": [{"text": "### 📖 폴백 도서 추천"}],
                    }
                }
            ],
        }
    ]

    mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=settings,
    )

    chunks: list[str] = []
    async for chunk in service.stream_chat(session_id="sess-orch-fb", message="책 추천"):
        chunks.append(chunk)

    assert "".join(chunks) == "### 📖 폴백 도서 추천"
    mock_session_store.append_turn.assert_has_awaits(
        [
            mocker.call("sess-orch-fb", {"role": "user", "content": "책 추천"}),
            mocker.call(
                "sess-orch-fb",
                {"role": "assistant", "content": "### 📖 폴백 도서 추천"},
            ),
        ]
    )


@pytest.mark.asyncio
async def test_orchestrator_service_stream_chat_appends_tool_result_when_intro_only(
    mocker: MockerFixture,
) -> None:
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.get_session_meta = AsyncMock(return_value={})
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.append_turn = AsyncMock()

    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    async def fake_intro_stream_async(prompt: str) -> Any:
        yield {"data": "추천해 드리겠습니다."}

    mock_agent = MagicMock()
    mock_agent.stream_async = fake_intro_stream_async
    mock_agent.messages = [
        {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "content": [{"text": "### 📖 불편한 편의점\n- **저자**: 김호연"}],
                    }
                }
            ],
        }
    ]

    mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=settings,
    )

    chunks: list[str] = []
    async for chunk in service.stream_chat(session_id="sess-orch-intro", message="책 추천"):
        chunks.append(chunk)

    expected = "추천해 드리겠습니다.\n\n### 📖 불편한 편의점\n- **저자**: 김호연"
    assert "".join(chunks) == expected
    mock_session_store.append_turn.assert_has_awaits(
        [
            mocker.call("sess-orch-intro", {"role": "user", "content": "책 추천"}),
            mocker.call(
                "sess-orch-intro",
                {"role": "assistant", "content": expected},
            ),
        ]
    )


@pytest.mark.asyncio
async def test_orchestrator_service_chat_with_library_tool(mocker: MockerFixture) -> None:
    from discovery.domain.orchestrator.library_response import LibraryBookItem

    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.get_session_meta = AsyncMock(return_value={"librarian_id": "cat"})
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.append_turn = AsyncMock()

    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    mock_library_tool = mocker.MagicMock()
    mock_book_item = LibraryBookItem(
        book_id=101,
        title="살인자의 기억법",
        author="김영하",
        reading_status="READING",
        progress=50,
    )

    def fake_library_as_tool(**kwargs: Any) -> Any:
        on_books = kwargs.get("on_books_fetched")

        async def fake_tool_func(*args: Any, **tool_kwargs: Any) -> str:
            if on_books:
                on_books([mock_book_item])
            return "서재 도서 조회 완료"

        return fake_tool_func

    mock_library_tool.as_tool.side_effect = fake_library_as_tool

    mock_agent = mocker.MagicMock()
    mock_result = mocker.MagicMock()
    mock_result.message = {
        "role": "assistant",
        "content": [{"text": "서재에 살인자의 기억법이 있습니다냥 🐾"}],
    }

    async def fake_invoke(prompt: str) -> Any:
        # LLM 실행 중 도구 호출 시뮬레이션
        tool_fn = mock_library_tool.as_tool.call_args[1]["on_books_fetched"]
        tool_fn([mock_book_item])
        return mock_result

    mock_agent.invoke_async.side_effect = fake_invoke

    mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=settings,
        library_tool=mock_library_tool,
    )

    response, switch_to, signals, library_books = await service.chat(
        session_id="sess-lib-1",
        message="내 서재 책 있어?",
        auth_token="Bearer test-jwt-xyz",
    )

    assert "살인자의 기억법이 있습니다냥" in response
    assert library_books is not None
    assert len(library_books) == 1
    assert library_books[0].book_id == 101
    assert library_books[0].title == "살인자의 기억법"
    assert library_books[0].progress == 50


@pytest.mark.asyncio
async def test_orchestrator_service_chat_hybrid_recommendation_populates_library_books(
    mocker: MockerFixture,
) -> None:
    """[1차 구현 알려진 동작 회귀 테스트]
    복합 추천(서재 도서 조회 → 도서 추천 연쇄) 시나리오에서도 search_my_library가 호출되면
    1차 구현 사양에 따라 library_books가 채워져 반환됨을 명시 검증한다.
    (추후 2차 과제에서 '추천 턴 시 카드 억제' 구현 시 이 테스트를 분기/갱신함).
    """
    from discovery.domain.orchestrator.library_response import LibraryBookItem

    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.get_session_meta = AsyncMock(return_value={"librarian_id": "cat"})
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.append_turn = AsyncMock()

    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    mock_library_tool = mocker.MagicMock()
    mock_book_item = LibraryBookItem(
        book_id=202,
        title="클린 아키텍처",
        author="로버트 마틴",
        reading_status="COMPLETED",
        progress=100,
    )

    def fake_library_as_tool(**kwargs: Any) -> Any:
        on_books = kwargs.get("on_books_fetched")

        async def fake_tool_func(*args: Any, **tool_kwargs: Any) -> str:
            if on_books:
                on_books([mock_book_item])
            return "서재 도서 조회 완료"

        return fake_tool_func

    mock_library_tool.as_tool.side_effect = fake_library_as_tool

    mock_agent = mocker.MagicMock()
    mock_result = mocker.MagicMock()
    mock_result.message = {
        "role": "assistant",
        "content": [
            {
                "text": (
                    "서재에 있는 클린 아키텍처와 비슷한 책을 추천해드린다냥!\n\n"
                    "### 📖 리팩터링 2판\n- **저자**: 마틴 파울러"
                )
            }
        ],
    }

    async def fake_invoke(prompt: str) -> Any:
        tool_fn = mock_library_tool.as_tool.call_args[1]["on_books_fetched"]
        tool_fn([mock_book_item])
        return mock_result

    mock_agent.invoke_async.side_effect = fake_invoke

    mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=settings,
        library_tool=mock_library_tool,
    )

    response, switch_to, signals, library_books = await service.chat(
        session_id="sess-hybrid-1",
        message="내 서재에 있는 책이랑 비슷한 새로운 책 추천해줘",
        auth_token="Bearer test-jwt-xyz",
    )

    assert "리팩터링 2판" in response
    # 1차 구현에서는 도구가 호출되었으므로 library_books가 채워져 있음 (알려진 1차 동작)
    assert library_books is not None
    assert len(library_books) == 1
    assert library_books[0].book_id == 202


@pytest.mark.asyncio
async def test_orchestrator_service_chat_handles_bedrock_exception_gracefully_for_cat(
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.get_session_meta = AsyncMock(return_value={"librarian_id": "cat"})
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.append_turn = AsyncMock()

    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    mock_agent = mocker.MagicMock()
    # Bedrock AccessDeniedException 시뮬레이션
    mock_agent.invoke_async = AsyncMock(
        side_effect=RuntimeError("AccessDeniedException explicit deny")
    )

    mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=settings,
    )

    with caplog.at_level(logging.ERROR):
        response, switch_to, signals, library_books = await service.chat(
            session_id="sess-err-cat",
            message="책 추천해줘",
        )

    assert "냥냥... 서재 책장을 정리하던 중에 통신 연결이 잠시 끊겼다냥 🐾" in response
    assert library_books is None
    assert "[BEDROCK_FALLBACK]" in caplog.text
    mock_session_store.append_turn.assert_has_awaits(
        [
            mocker.call("sess-err-cat", {"role": "user", "content": "책 추천해줘"}),
            mocker.call("sess-err-cat", {"role": "assistant", "content": response}),
        ]
    )


@pytest.mark.asyncio
async def test_orchestrator_service_chat_handles_bedrock_exception_gracefully_for_stork(
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.get_session_meta = AsyncMock(return_value={"librarian_id": "stork"})
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.append_turn = AsyncMock()

    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    mock_agent = mocker.MagicMock()
    mock_agent.invoke_async = AsyncMock(side_effect=RuntimeError("ThrottlingException rate limit"))

    mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=settings,
    )

    with caplog.at_level(logging.ERROR):
        response, switch_to, signals, library_books = await service.chat(
            session_id="sess-err-stork",
            message="경제 서적 추천해줘",
        )

    assert "두둥! 서재 사서실 통신에 일시적인 장애가 발생했습니다 🪶" in response
    assert library_books is None
    assert "[BEDROCK_FALLBACK]" in caplog.text
    mock_session_store.append_turn.assert_has_awaits(
        [
            mocker.call("sess-err-stork", {"role": "user", "content": "경제 서적 추천해줘"}),
            mocker.call("sess-err-stork", {"role": "assistant", "content": response}),
        ]
    )


@pytest.mark.asyncio
async def test_orchestrator_service_stream_chat_handles_bedrock_exception_gracefully_for_cat(
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.get_session_meta = AsyncMock(return_value={"librarian_id": "cat"})
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.append_turn = AsyncMock()

    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    from collections.abc import AsyncGenerator

    async def fake_failing_stream(prompt: str) -> AsyncGenerator[dict[str, str], None]:
        raise RuntimeError("AccessDeniedException on Bedrock stream")
        yield {"data": "test"}

    mock_agent = mocker.MagicMock()
    mock_agent.stream_async = fake_failing_stream

    mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=settings,
    )

    chunks: list[str] = []
    with caplog.at_level(logging.ERROR):
        async for chunk in service.stream_chat(session_id="sess-stream-err", message="추천해줘"):
            chunks.append(chunk)

    full_output = "".join(chunks)
    assert "냥냥... 서재 책장을 정리하던 중에 통신 연결이 잠시 끊겼다냥 🐾" in full_output
    assert "[BEDROCK_FALLBACK]" in caplog.text
    mock_session_store.append_turn.assert_has_awaits(
        [
            mocker.call("sess-stream-err", {"role": "user", "content": "추천해줘"}),
            mocker.call("sess-stream-err", {"role": "assistant", "content": full_output}),
        ]
    )


@pytest.mark.asyncio
async def test_orchestrator_service_stream_chat_handles_midstream_exception_gracefully_for_stork(
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.get_session_meta = AsyncMock(return_value={"librarian_id": "stork"})
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.append_turn = AsyncMock()

    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    from collections.abc import AsyncGenerator

    async def fake_mid_failing_stream(prompt: str) -> AsyncGenerator[dict[str, str], None]:
        yield {"data": "추천을 준비하던 중..."}
        raise RuntimeError("Bedrock connection timeout midstream")

    mock_agent = mocker.MagicMock()
    mock_agent.stream_async = fake_mid_failing_stream

    mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=settings,
    )

    chunks: list[str] = []
    with caplog.at_level(logging.ERROR):
        async for chunk in service.stream_chat(
            session_id="sess-stream-mid-err",
            message="추천해줘",
        ):
            chunks.append(chunk)

    full_output = "".join(chunks)
    assert "추천을 준비하던 중..." in full_output
    assert "두둥! 서재 사서실 통신에 일시적인 장애가 발생했습니다 🪶" in full_output
    assert "[BEDROCK_FALLBACK]" in caplog.text


@pytest.mark.asyncio
async def test_get_initial_meta_handles_timeout_gracefully(
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_session_meta = AsyncMock(return_value={"librarian_id": "cat"})
    mock_session_store.update_session_meta = AsyncMock()

    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        initial_meta_timeout_seconds=0.01,
    )

    import asyncio

    async def slow_consult(*args: Any, **kwargs: Any) -> Any:
        await asyncio.sleep(0.1)
        return MagicMock()

    mock_librarian_tool = mocker.MagicMock()
    mock_librarian_tool.consult = slow_consult

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=settings,
        librarian_tool=mock_librarian_tool,
    )

    with caplog.at_level(logging.WARNING):
        signals, switch_to = await service.get_initial_meta(
            session_id="sess-timeout",
            message="추천해줘",
        )

    assert signals is None
    assert switch_to is None
    assert "[INITIAL_META_TIMEOUT]" in caplog.text


@pytest.mark.asyncio
async def test_get_initial_meta_handles_exception_gracefully(
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_session_meta = AsyncMock(return_value={"librarian_id": "cat"})
    mock_session_store.update_session_meta = AsyncMock()

    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        initial_meta_timeout_seconds=1.5,
    )

    mock_librarian_tool = mocker.MagicMock()
    mock_librarian_tool.consult = AsyncMock(side_effect=RuntimeError("Connection refused"))

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=settings,
        librarian_tool=mock_librarian_tool,
    )

    with caplog.at_level(logging.WARNING):
        signals, switch_to = await service.get_initial_meta(
            session_id="sess-err",
            message="추천해줘",
        )

    assert signals is None
    assert switch_to is None
    assert "[INITIAL_META_FALLBACK]" in caplog.text


@pytest.mark.asyncio
async def test_get_initial_meta_returns_signals_and_switch_to_on_success(
    mocker: MockerFixture,
) -> None:
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_session_meta = AsyncMock(return_value={"librarian_id": "cat"})
    mock_session_store.update_session_meta = AsyncMock()

    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        initial_meta_timeout_seconds=1.5,
    )

    mock_signals = LibrarianSignals(
        weather=WeatherSignal(weather="비", is_rainy=True),
        mood="Reflective",
    )
    mock_switch_to = SwitchToSuggestion(id="stork", name="황새 사서", genres=["비즈니스"])
    mock_res = LibrarianResponse(
        message="안내",
        signals=mock_signals,
        switch_to=mock_switch_to,
    )

    mock_librarian_tool = mocker.MagicMock()
    mock_librarian_tool.consult = AsyncMock(return_value=mock_res)

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=settings,
        librarian_tool=mock_librarian_tool,
    )

    signals, switch_to = await service.get_initial_meta(
        session_id="sess-ok",
        message="추천해줘",
    )

    assert signals == mock_signals
    assert switch_to == mock_switch_to


