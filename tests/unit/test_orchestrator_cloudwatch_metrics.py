"""OrchestratorService의 CLIAR-276 CloudWatch 비용/토큰 메트릭 배선 검증.

- `cloudwatch_publisher`가 주어지면 `accumulated_usage`를 읽어 `publish_usage`가
  fire-and-forget으로 호출된다(응답 흐름을 기다리지 않음, `asyncio.sleep(0)`으로 스케줄된
  태스크를 한 스텝 진행시켜 검증한다).
- `cloudwatch_publisher=None`(기존 테스트 전부가 이 경로)이면 CloudWatch 관련 코드가
  전혀 호출되지 않는다 — 이는 `test_orchestrator_service.py`의 기존 45건이 이 인자를
  주지 않고도 그대로 통과함으로써 이미 검증된다(회귀 없음).
- 기존 `log_agent_metrics` 로그 호출은 CloudWatch 배선 여부와 무관하게 그대로 유지된다.
"""

import asyncio
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

    mock_publisher = mocker.MagicMock()
    mock_publisher.publish_usage = AsyncMock()

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=_build_settings(),
        cloudwatch_publisher=mock_publisher,
    )

    await service.chat(session_id="sess-cw-1", message="도서 추천해줘")
    # fire-and-forget 태스크가 실행될 기회를 준다.
    await asyncio.sleep(0)
    await asyncio.sleep(0)

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

    mock_publisher = mocker.MagicMock()
    mock_publisher.publish_usage = AsyncMock()

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=_build_settings(),
        cloudwatch_publisher=mock_publisher,
    )

    await service.chat(session_id="sess-cw-2", message="안녕")
    await asyncio.sleep(0)

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

    mock_publisher = mocker.MagicMock()
    mock_publisher.publish_usage = AsyncMock()

    service = OrchestratorService(
        session_store=mock_session_store,
        settings=_build_settings(),
        cloudwatch_publisher=mock_publisher,
    )

    async for _ in service.stream_chat(session_id="sess-cw-3", message="추천해줘"):
        pass
    await asyncio.sleep(0)
    await asyncio.sleep(0)

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
    await asyncio.sleep(0)

    assert response == "응답"
