"""core/cloudwatch_metrics.py — CloudWatch 커스텀 메트릭 발행 검증.

boto3는 mock으로 대체해 실제 AWS 호출 없이 검증한다. 핵심 검증 대상:
- `enabled=False`이면 boto3 클라이언트를 생성하지도, `put_metric_data`를 호출하지도 않음
  (플래그 OFF 시 기존 동작에 전혀 영향이 없어야 함 — CLIAR-276 격리 원칙).
- `enabled=True`이면 올바른 네임스페이스·메트릭 이름·차원으로 발행됨.
- 발행 중 예외가 나도 전파되지 않음(graceful degradation).
"""

from unittest.mock import MagicMock

import pytest

from discovery.core.cloudwatch_metrics import NAMESPACE, CloudWatchMetricsPublisher


@pytest.mark.asyncio
async def test_disabled_publisher_never_creates_boto3_client(mocker: MagicMock) -> None:
    boto3_client = mocker.patch("discovery.core.cloudwatch_metrics.boto3.client")
    publisher = CloudWatchMetricsPublisher(enabled=False)

    await publisher.publish_usage(
        model_id="global.anthropic.claude-sonnet-5",
        cost_usd=0.018,
        input_tokens=1000,
        output_tokens=1000,
    )
    await publisher.publish_search_cache_event(hit=True)

    boto3_client.assert_not_called()


@pytest.mark.asyncio
async def test_publish_usage_sends_expected_metric_data(mocker: MagicMock) -> None:
    mock_client = mocker.MagicMock()
    mocker.patch("discovery.core.cloudwatch_metrics.boto3.client", return_value=mock_client)

    publisher = CloudWatchMetricsPublisher(enabled=True)
    await publisher.publish_usage(
        model_id="global.anthropic.claude-sonnet-5",
        cost_usd=0.018,
        input_tokens=1000,
        output_tokens=500,
        cache_read_tokens=200,
    )

    mock_client.put_metric_data.assert_called_once()
    call_kwargs = mock_client.put_metric_data.call_args.kwargs
    assert call_kwargs["Namespace"] == NAMESPACE
    metric_names = {m["MetricName"] for m in call_kwargs["MetricData"]}
    assert metric_names == {"InputTokens", "OutputTokens", "CacheReadTokens", "BedrockCostUSD"}
    for metric in call_kwargs["MetricData"]:
        assert metric["Dimensions"] == [
            {"Name": "Model", "Value": "global.anthropic.claude-sonnet-5"}
        ]


@pytest.mark.asyncio
async def test_publish_usage_omits_cost_metric_when_cost_is_none(mocker: MagicMock) -> None:
    mock_client = mocker.MagicMock()
    mocker.patch("discovery.core.cloudwatch_metrics.boto3.client", return_value=mock_client)

    publisher = CloudWatchMetricsPublisher(enabled=True)
    await publisher.publish_usage(
        model_id="unknown-model",
        cost_usd=None,
        input_tokens=100,
        output_tokens=50,
    )

    call_kwargs = mock_client.put_metric_data.call_args.kwargs
    metric_names = {m["MetricName"] for m in call_kwargs["MetricData"]}
    assert "BedrockCostUSD" not in metric_names


@pytest.mark.asyncio
async def test_publish_search_cache_event_hit_and_miss(mocker: MagicMock) -> None:
    mock_client = mocker.MagicMock()
    mocker.patch("discovery.core.cloudwatch_metrics.boto3.client", return_value=mock_client)

    publisher = CloudWatchMetricsPublisher(enabled=True)
    await publisher.publish_search_cache_event(hit=True)
    await publisher.publish_search_cache_event(hit=False)

    assert mock_client.put_metric_data.call_count == 2
    first_call = mock_client.put_metric_data.call_args_list[0].kwargs
    second_call = mock_client.put_metric_data.call_args_list[1].kwargs
    assert first_call["MetricData"][0]["MetricName"] == "SearchCacheHit"
    assert second_call["MetricData"][0]["MetricName"] == "SearchCacheMiss"


@pytest.mark.asyncio
async def test_publish_failure_is_swallowed_and_does_not_raise(mocker: MagicMock) -> None:
    mock_client = mocker.MagicMock()
    mock_client.put_metric_data.side_effect = RuntimeError("network unreachable")
    mocker.patch("discovery.core.cloudwatch_metrics.boto3.client", return_value=mock_client)

    publisher = CloudWatchMetricsPublisher(enabled=True)
    # 예외가 여기서 전파되지 않아야 한다(사용자 요청 흐름을 깨지 않음).
    await publisher.publish_usage(
        model_id="global.anthropic.claude-sonnet-5",
        cost_usd=0.01,
        input_tokens=10,
        output_tokens=10,
    )


@pytest.mark.asyncio
async def test_client_is_created_lazily_only_when_enabled(mocker: MagicMock) -> None:
    """enabled=True라도 실제 발행 메서드를 호출하기 전에는 클라이언트를 만들지 않는다."""
    boto3_client = mocker.patch("discovery.core.cloudwatch_metrics.boto3.client")
    CloudWatchMetricsPublisher(enabled=True)

    boto3_client.assert_not_called()


# --- CLIAR-276 확장: 레이턴시(RequestLatencyMs / TimeToFirstByteMs) 발행 검증 ---


@pytest.mark.asyncio
async def test_disabled_publisher_publish_latency_is_noop(mocker: MagicMock) -> None:
    boto3_client = mocker.patch("discovery.core.cloudwatch_metrics.boto3.client")
    publisher = CloudWatchMetricsPublisher(enabled=False)

    await publisher.publish_latency(model_id="global.anthropic.claude-sonnet-5", total_ms=1234.5)

    boto3_client.assert_not_called()


@pytest.mark.asyncio
async def test_publish_latency_sends_total_and_ttfb(mocker: MagicMock) -> None:
    mock_client = mocker.MagicMock()
    mocker.patch("discovery.core.cloudwatch_metrics.boto3.client", return_value=mock_client)

    publisher = CloudWatchMetricsPublisher(enabled=True)
    await publisher.publish_latency(
        model_id="global.anthropic.claude-sonnet-5", total_ms=4200.12, ttfb_ms=350.5
    )

    mock_client.put_metric_data.assert_called_once()
    call_kwargs = mock_client.put_metric_data.call_args.kwargs
    assert call_kwargs["Namespace"] == NAMESPACE
    metrics_by_name = {m["MetricName"]: m for m in call_kwargs["MetricData"]}
    assert metrics_by_name.keys() == {"RequestLatencyMs", "TimeToFirstByteMs"}
    assert metrics_by_name["RequestLatencyMs"]["Value"] == 4200.12
    assert metrics_by_name["RequestLatencyMs"]["Unit"] == "Milliseconds"
    assert metrics_by_name["TimeToFirstByteMs"]["Value"] == 350.5
    for metric in call_kwargs["MetricData"]:
        assert metric["Dimensions"] == [
            {"Name": "Model", "Value": "global.anthropic.claude-sonnet-5"}
        ]


@pytest.mark.asyncio
async def test_publish_latency_omits_ttfb_when_not_streaming(mocker: MagicMock) -> None:
    mock_client = mocker.MagicMock()
    mocker.patch("discovery.core.cloudwatch_metrics.boto3.client", return_value=mock_client)

    publisher = CloudWatchMetricsPublisher(enabled=True)
    await publisher.publish_latency(model_id="global.anthropic.claude-sonnet-5", total_ms=999.0)

    call_kwargs = mock_client.put_metric_data.call_args.kwargs
    metric_names = {m["MetricName"] for m in call_kwargs["MetricData"]}
    assert metric_names == {"RequestLatencyMs"}


@pytest.mark.asyncio
async def test_publish_latency_failure_is_swallowed_and_does_not_raise(
    mocker: MagicMock,
) -> None:
    mock_client = mocker.MagicMock()
    mock_client.put_metric_data.side_effect = RuntimeError("network unreachable")
    mocker.patch("discovery.core.cloudwatch_metrics.boto3.client", return_value=mock_client)

    publisher = CloudWatchMetricsPublisher(enabled=True)
    await publisher.publish_latency(model_id="global.anthropic.claude-sonnet-5", total_ms=100.0)
