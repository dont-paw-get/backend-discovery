"""OrchestratorService 단위 테스트.

실제 AWS/Redis/외부 서비스 호출 없이 mocker로 세션 스토어와 에이전트 동작을 모킹하여
히스토리 주입, 도구 주입, 에이전트 실행, 턴 저장 순서 및 스트리밍 동작을 검증한다.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from discovery.application.orchestrator_service import OrchestratorService
from discovery.core.config import Settings


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

    response, switch_to, signals = await service.chat(
        session_id="sess-orch-1", message="도서 추천해줘"
    )

    assert response == "안녕하세요! 오케스트레이터 응답입니다."
    assert switch_to is None
    assert signals is None

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

    response, switch_to, signals = await service.chat(
        session_id="sess-switch-1",
        message="시 추천해줘",
        latitude=37.5665,
        longitude=126.9780,
    )

    assert "사서님의 추천입니다" in response
    assert switch_to is not None
    assert switch_to.id == "stork"
    assert switch_to.name == "황새 사서"

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
    mock_library_tool.as_tool.return_value = mocker.MagicMock()

    mock_agent = mocker.MagicMock()
    mock_result = mocker.MagicMock()
    mock_result.message = {
        "role": "assistant",
        "content": [{"text": "서재에 살인자의 기억법이 있습니다냥 🐾"}],
    }
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)

    mock_create_agent = mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=settings,
        library_tool=mock_library_tool,
    )

    response, switch_to, signals = await service.chat(
        session_id="sess-lib-1",
        message="내 서재 책 있어?",
        auth_token="Bearer test-jwt-xyz",
    )

    assert "살인자의 기억법이 있습니다냥" in response
    mock_library_tool.as_tool.assert_called_once_with(auth_token="Bearer test-jwt-xyz")
    mock_create_agent.assert_called_once()
    assert mock_library_tool.as_tool.return_value in mock_create_agent.call_args[1]["tools"]
