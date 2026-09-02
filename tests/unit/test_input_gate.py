"""결정론적 비정상 입력 게이트(Input Gate) 단위 테스트."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from discovery.api.schemas.chat import ChatRequest
from discovery.core.config import Settings
from discovery.domain.orchestrator.input_gate import (
    InvalidInputType,
    detect_invalid_input_type,
    evaluate_input_gate,
)


@pytest.mark.parametrize(
    "msg",
    [
        "ㅁㄴㅇㄹ",
        "ㅋㅋㅋㅋ",
        "ㅠㅠ",
        "ㅇㅇ",
        "ㄱㄴㄷㄹ",
        "ㅏㅑㅓㅕ",
    ],
)
def test_detect_jamo_only(msg: str) -> None:
    assert detect_invalid_input_type(msg) == InvalidInputType.JAMO_ONLY


@pytest.mark.parametrize(
    "msg",
    [
        "12345",
        "0000",
        "98765",
        " 123 456 ",
    ],
)
def test_detect_digits_only(msg: str) -> None:
    assert detect_invalid_input_type(msg) == InvalidInputType.DIGITS_ONLY


@pytest.mark.parametrize(
    "msg",
    [
        "😊📚",
        "🐱✨",
        "👍",
        "🔥📖✨",
    ],
)
def test_detect_emoji_only(msg: str) -> None:
    assert detect_invalid_input_type(msg) == InvalidInputType.EMOJI_ONLY


@pytest.mark.parametrize(
    "msg",
    [
        "안녕하세요",
        "1등 추천 도서 알려줘",
        "책 추천해줘 😊",
        "1984 조지 오웰",
        "82년생 김지영",
    ],
)
def test_detect_normal_messages_none(msg: str) -> None:
    assert detect_invalid_input_type(msg) is None


def test_evaluate_input_gate_persona_responses() -> None:
    cat_jamo = evaluate_input_gate("ㅁㄴㅇㄹ", librarian_id="cat")
    assert cat_jamo is not None
    assert "냥" in cat_jamo

    stork_digits = evaluate_input_gate("12345", librarian_id="stork")
    assert stork_digits is not None
    assert "두둥" in stork_digits

    normal = evaluate_input_gate("안녕", librarian_id="cat")
    assert normal is None


def test_chat_request_blank_message_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(message="   ")

    with pytest.raises(ValidationError):
        ChatRequest(message="")


@pytest.mark.asyncio
async def test_orchestrator_chat_bypasses_llm_on_invalid_input() -> None:
    from discovery.application.orchestrator_service import OrchestratorService

    mock_session_store = MagicMock()
    mock_session_store.get_session_meta = AsyncMock(return_value={"librarian_id": "cat"})
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.append_turn = AsyncMock()

    settings = Settings(
        llm_provider="mock",
        orchestrator_model_id="test-model",
    )
    service = OrchestratorService(
        session_store=mock_session_store,
        settings=settings,
    )
    service._build_agent = MagicMock()  # type: ignore[method-assign]

    response_text, switch_to, signals, library_books, recommended_books = await service.chat(
        session_id="sess-invalid",
        message="ㅁㄴㅇㄹ",
    )

    service._build_agent.assert_not_called()
    assert response_text is not None
    assert "냥" in response_text
    assert switch_to is None
    assert signals is None
    assert library_books is None
    assert mock_session_store.append_turn.await_count == 2


@pytest.mark.asyncio
async def test_orchestrator_stream_chat_bypasses_llm_on_invalid_input() -> None:
    from discovery.application.orchestrator_service import OrchestratorService

    mock_session_store = MagicMock()
    mock_session_store.get_session_meta = AsyncMock(return_value={"librarian_id": "stork"})
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.append_turn = AsyncMock()

    settings = Settings(
        llm_provider="mock",
        orchestrator_model_id="test-model",
    )
    service = OrchestratorService(
        session_store=mock_session_store,
        settings=settings,
    )
    service._build_agent = MagicMock()  # type: ignore[method-assign]

    chunks = []
    async for chunk in service.stream_chat(
        session_id="sess-invalid-stream",
        message="12345",
    ):
        chunks.append(chunk)

    service._build_agent.assert_not_called()
    full_text = "".join(chunks)
    assert "두둥" in full_text
    assert mock_session_store.append_turn.await_count == 2
