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

    response = await service.chat(session_id="sess-orch-1", message="도서 추천해줘")

    assert response == "안녕하세요! 오케스트레이터 응답입니다."

    mock_session_store.get_history.assert_awaited_once_with("sess-orch-1")
    mock_create_agent.assert_called_once_with(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        region_name="us-east-1",
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
async def test_orchestrator_service_stream_chat(mocker: MockerFixture) -> None:
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
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
