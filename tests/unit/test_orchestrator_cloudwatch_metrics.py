"""OrchestratorService의 CLIAR-276 CloudWatch 비용/토큰 메트릭 배선 검증.

- `cloudwatch_publisher`가 주어지면 `accumulated_usage`를 읽어 `publish_usage`가
  직접 `await`되어 호출된다. 이전에는 `asyncio.create_task` fire-and-forget 방식을
  썼으나, FastAPI 요청 코루틴이 응답 반환 직후 종료되며 던져둔 태스크가 실행 기회를
  얻지 못하고 소실되는 문제가 dev 실측(2026-09-04)으로 확인되어 직접 대기 방식으로
  전환했다. 이 테스트는 그 전환된 동작(await 완료 후 반환)을 검증한다.
- `cloudwatch_publisher=None`(기존 테스트 전부가 이 경로)이면 CloudWatch 관련 코드가
  전혀 호출되지 않는다 — 이는 `test_orchestrator_service.py`의 기존 45건이 이 인자를
  주지 않고도 그대로 통과함으로써 이미 검증된다(회귀 없음).
- 기존 `log_agent_metrics` 로그 호출은 CloudWatch 배선 여부와 무관하게 그대로 유지된다.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from discovery.application.orchestrator_service import OrchestratorService
from discovery.core.config import Settings


def _build_settings(**overrides: Any) -> Settings:
    return Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        orchestrator_model_id="global.anthropic.claude-sonnet-5",
        aws_region="us-east-1",
        **overrides,
    )


def _build_mock_publisher(mocker: MockerFixture) -> Any:
    pub = mocker.MagicMock()
    pub.publish_usage = AsyncMock()
    pub.publish_latency = AsyncMock()
    pub.publish_search_cache_event = AsyncMock()
    return pub


@pytest.mark.asyncio
async def test_chat_publishes_cloudwatch_usage_metrics_when_publisher_given(
    mocker: MockerFixture,
) -> None:
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.get_session_meta = AsyncMock(return_value={})
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.append_turn = AsyncMock()

    mock_metrics = MagicMock()
    mock_metrics.get_summary.return_value = {
        "accumulated_usage": {
            "inputTokens": 1000,
            "outputTokens": 500,
            "cacheReadInputTokens": 100,
        }
    }
    mock_result = MagicMock()
    mock_result.message = {"role": "assistant", "content": [{"text": "응답"}]}
    mock_result.metrics = mock_metrics

    mock_agent = mocker.MagicMock()
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)
    mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    mock_publisher = _build_mock_publisher(mocker)

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=_build_settings(),
        cloudwatch_publisher=mock_publisher,
    )

    await service.chat(session_id="sess-cw-1", message="도서 추천해줘")

    mock_publisher.publish_usage.assert_awaited_once_with(
        model_id="global.anthropic.claude-sonnet-5",
        cost_usd=pytest.approx(1000 / 1000 * 0.003 + 500 / 1000 * 0.015 + 100 / 1000 * 0.0003),
        input_tokens=1000,
        output_tokens=500,
        cache_read_tokens=100,
        cache_write_tokens=0,
    )


@pytest.mark.asyncio
async def test_chat_does_not_touch_publisher_when_metrics_summary_missing(
    mocker: MockerFixture,
) -> None:
    """도구 없이 result.metrics 자체가 없는 경우에도 예외 없이 안전하게 스킵된다."""
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.get_session_meta = AsyncMock(return_value={})
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.append_turn = AsyncMock()

    mock_result = MagicMock()
    mock_result.message = {"role": "assistant", "content": [{"text": "응답"}]}
    mock_result.metrics = None

    mock_agent = mocker.MagicMock()
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)
    mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    mock_publisher = _build_mock_publisher(mocker)

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=_build_settings(),
        cloudwatch_publisher=mock_publisher,
    )

    await service.chat(session_id="sess-cw-2", message="안녕")

    mock_publisher.publish_usage.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_chat_publishes_cloudwatch_usage_metrics(mocker: MockerFixture) -> None:
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_session_meta = AsyncMock(return_value={"librarian_id": "cat"})
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.append_turn = AsyncMock()

    mock_metrics = MagicMock()
    mock_metrics.get_summary.return_value = {
        "accumulated_usage": {"inputTokens": 200, "outputTokens": 100}
    }
    mock_result_obj = MagicMock()
    mock_result_obj.metrics = mock_metrics

    async def fake_stream_async(prompt: str) -> Any:
        yield {"data": "청크"}
        yield {"result": mock_result_obj}

    mock_agent = mocker.MagicMock()
    mock_agent.stream_async = fake_stream_async
    mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    mock_publisher = _build_mock_publisher(mocker)

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=_build_settings(),
        cloudwatch_publisher=mock_publisher,
    )

    async for _ in service.stream_chat(session_id="sess-cw-3", message="추천해줘"):
        pass

    mock_publisher.publish_usage.assert_awaited_once_with(
        model_id="global.anthropic.claude-sonnet-5",
        cost_usd=pytest.approx(200 / 1000 * 0.003 + 100 / 1000 * 0.015),
        input_tokens=200,
        output_tokens=100,
        cache_read_tokens=0,
        cache_write_tokens=0,
    )


@pytest.mark.asyncio
async def test_chat_without_cloudwatch_publisher_does_not_raise(mocker: MockerFixture) -> None:
    """cloudwatch_publisher=None(기존 호출부 전부)이면 CloudWatch 관련 코드가 전혀
    실행되지 않고 정상적으로 응답이 반환된다 — 기존 동작 무변화 보증."""
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.get_session_meta = AsyncMock(return_value={})
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.append_turn = AsyncMock()

    mock_metrics = MagicMock()
    mock_metrics.get_summary.return_value = {"accumulated_usage": {"inputTokens": 10}}
    mock_result = MagicMock()
    mock_result.message = {"role": "assistant", "content": [{"text": "응답"}]}
    mock_result.metrics = mock_metrics

    mock_agent = mocker.MagicMock()
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)
    mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=_build_settings(),
    )

    response, *_ = await service.chat(session_id="sess-cw-4", message="안녕")

    assert response == "응답"


# --- CLIAR-276 확장: 레이턴시(RequestLatencyMs / TimeToFirstByteMs) 배선 검증 ---


@pytest.mark.asyncio
async def test_chat_publishes_cloudwatch_latency_metrics(mocker: MockerFixture) -> None:
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.get_session_meta = AsyncMock(return_value={})
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.append_turn = AsyncMock()

    mock_result = MagicMock()
    mock_result.message = {"role": "assistant", "content": [{"text": "응답"}]}
    mock_result.metrics = None

    mock_agent = mocker.MagicMock()
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)
    mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    mock_publisher = _build_mock_publisher(mocker)

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=_build_settings(),
        cloudwatch_publisher=mock_publisher,
    )

    await service.chat(session_id="sess-cw-5", message="안녕")

    mock_publisher.publish_latency.assert_awaited_once()
    call_kwargs = mock_publisher.publish_latency.call_args.kwargs
    assert call_kwargs["model_id"] == "global.anthropic.claude-sonnet-5"
    assert isinstance(call_kwargs["total_ms"], float)
    # 동기 chat 경로는 스트리밍이 아니므로 ttfb_ms를 전달하지 않는다(기본값 None).
    assert call_kwargs.get("ttfb_ms") is None


@pytest.mark.asyncio
async def test_stream_chat_publishes_cloudwatch_latency_metrics_with_ttfb(
    mocker: MockerFixture,
) -> None:
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_session_meta = AsyncMock(return_value={"librarian_id": "cat"})
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.append_turn = AsyncMock()

    async def fake_stream_async(prompt: str) -> Any:
        yield {"data": "청크"}

    mock_agent = mocker.MagicMock()
    mock_agent.stream_async = fake_stream_async
    mocker.patch(
        "discovery.application.orchestrator_service.create_orchestrator_agent",
        return_value=mock_agent,
    )

    mock_publisher = _build_mock_publisher(mocker)

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=_build_settings(),
        cloudwatch_publisher=mock_publisher,
    )

    async for _ in service.stream_chat(session_id="sess-cw-6", message="추천해줘"):
        pass

    mock_publisher.publish_latency.assert_awaited_once()
    call_kwargs = mock_publisher.publish_latency.call_args.kwargs
    assert call_kwargs["model_id"] == "global.anthropic.claude-sonnet-5"
    assert isinstance(call_kwargs["total_ms"], float)
    assert isinstance(call_kwargs["ttfb_ms"], float)


@pytest.mark.asyncio
async def test_safety_gate_shortcircuit_does_not_publish_latency_metrics(
    mocker: MockerFixture,
) -> None:
    """안전 게이트로 조기 반환된 요청(LLM 미호출)은 레이턴시 메트릭 발행 대상에서
    제외된다 — 게이트 우회가 섞이면 p50/p90 통계가 왜곡되기 때문(계획 문서 참고)."""
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.get_session_meta = AsyncMock(return_value={})
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.append_turn = AsyncMock()

    mocker.patch(
        "discovery.application.orchestrator_service.evaluate_safety_gate",
        return_value="위기 대응 안내 문구",
    )

    mock_publisher = _build_mock_publisher(mocker)

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=_build_settings(),
        cloudwatch_publisher=mock_publisher,
    )

    await service.chat(session_id="sess-cw-7", message="자해하고 싶어")

    mock_publisher.publish_latency.assert_not_awaited()
    mock_publisher.publish_usage.assert_not_awaited()


@pytest.mark.asyncio
async def test_input_gate_shortcircuit_does_not_publish_latency_metrics(
    mocker: MockerFixture,
) -> None:
    """비정상 입력 게이트(자모/숫자/이모지)로 조기 반환된 요청 역시 레이턴시 메트릭
    발행 대상에서 제외된다."""
    mock_session_store = mocker.MagicMock()
    mock_session_store.get_history = AsyncMock(return_value=[])
    mock_session_store.get_session_meta = AsyncMock(return_value={})
    mock_session_store.update_session_meta = AsyncMock()
    mock_session_store.append_turn = AsyncMock()

    mocker.patch(
        "discovery.application.orchestrator_service.evaluate_input_gate",
        return_value="올바른 단어로 입력해달라냥🐾",
    )

    mock_publisher = _build_mock_publisher(mocker)

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=_build_settings(),
        cloudwatch_publisher=mock_publisher,
    )

    await service.chat(session_id="sess-cw-8", message="ㅎㅎㅎ")

    mock_publisher.publish_latency.assert_not_awaited()
    mock_publisher.publish_usage.assert_not_awaited()
