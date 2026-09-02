"""위기/자해 대응 안전 게이트(Safety Gate) 단위 테스트."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from discovery.core.config import Settings
from discovery.domain.orchestrator.safety_gate import (
    CAT_CRISIS_RESPONSE,
    STORK_CRISIS_RESPONSE,
    evaluate_safety_gate,
    is_crisis_message,
)


@pytest.mark.parametrize(
    "msg",
    [
        "너무 힘들어서 죽고 싶어요",
        "자살하고 싶다",
        "자해 충동이 들어요",
        "살기 싫어 진짜",
        "목숨을 끊고 싶어",
        "세상을 떠나고 싶어",
        "생을 마감하고 싶다",
        "다 귀찮고 죽어버리고 싶어",
        "옥상에서 뛰어내리고 싶어",
    ],
)
def test_is_crisis_message_detects_crisis(msg: str) -> None:
    assert is_crisis_message(msg) is True


@pytest.mark.parametrize(
    "msg",
    [
        "안녕하세요",
        "재미있는 SF 소설 추천해줘",
        "자살론 책 추천해줘",
        "자살가게 책 내용 알려줘",
        "자살 토끼 그림책 찾아줘",
        "오늘 날씨 어때?",
        "우울할 때 읽기 좋은 소설 있어?",
    ],
)
def test_is_crisis_message_excludes_normal_and_book_queries(msg: str) -> None:
    assert is_crisis_message(msg) is False


def test_evaluate_safety_gate_returns_persona_responses() -> None:
    cat_res = evaluate_safety_gate("죽고 싶어요", librarian_id="cat")
    assert cat_res == CAT_CRISIS_RESPONSE
    assert "109" in cat_res
    assert "1577-0199" in cat_res
    assert "다냥" in cat_res

    stork_res = evaluate_safety_gate("죽고 싶어요", librarian_id="stork")
    assert stork_res == STORK_CRISIS_RESPONSE
    assert "109" in stork_res
    assert "1577-0199" in stork_res
    assert "드립니다" in stork_res

    none_res = evaluate_safety_gate("좋은 책 추천해줘", librarian_id="cat")
    assert none_res is None


@pytest.mark.asyncio
async def test_orchestrator_chat_bypasses_llm_on_crisis() -> None:
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
        session_id="sess-crisis",
        message="너무 힘들어서 죽고 싶어요",
    )

    # Agent should not be built or invoked
    service._build_agent.assert_not_called()
    assert response_text == CAT_CRISIS_RESPONSE
    assert "109" in response_text
    assert switch_to is None
    assert signals is None
    assert library_books is None
    assert mock_session_store.append_turn.await_count == 2


@pytest.mark.asyncio
async def test_orchestrator_stream_chat_bypasses_llm_on_crisis() -> None:
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
        session_id="sess-crisis-stream",
        message="스스로 목숨을 끊고 싶습니다",
    ):
        chunks.append(chunk)

    service._build_agent.assert_not_called()
    full_text = "".join(chunks)
    assert full_text == STORK_CRISIS_RESPONSE
    assert "109" in full_text
    assert mock_session_store.append_turn.await_count == 2
