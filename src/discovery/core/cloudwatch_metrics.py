"""AWS CloudWatch 커스텀 메트릭 발행 — 기존 Prometheus/Grafana/Loki 관측 스택과 완전히
독립된 경로 (CLIAR-276).

**격리 원칙 (`.harness/DECISIONS.md`, `.harness/PLAN.md` CLIAR-276 참고)**:
- 기존 `core/metrics.py`(Prometheus `/metrics`)·`core/tracing.py`·`core/observability.py`는
  이 모듈이 일절 수정하지 않는다. 이 모듈은 완전히 새로운 파일이며, 기존 모듈을 import하지
  않는다(반대로 이 모듈도 기존 모듈에서 import되지 않음 — 단방향 의존 없음, 완전 분리).
- CloudWatch 네임스페이스(`DPYB/Discovery/LLM`)는 Prometheus 메트릭 이름공간과 물리적으로
  분리되어 있어 이름 충돌이 원천적으로 불가능하다.
- 기본값 OFF(`Settings.enable_cloudwatch_metrics = False`)로 두어, 켜기 전에는 이 모듈의
  코드 경로 자체가 전혀 실행되지 않는다(호출부에서 플래그를 먼저 확인).
- 발행 실패가 사용자 요청을 절대 깨지 않는다 — 예외는 로그로만 남기고 삼킨다
  (`book_metadata_client.py`의 graceful degradation 선례와 동일한 방식).
- `boto3` CloudWatch 클라이언트는 동기(sync) API이므로 이벤트 루프를 블로킹하지 않도록
  `asyncio.to_thread`로 감싸 별도 스레드에서 실행한다.

**발행 메트릭** (네임스페이스 `DPYB/Discovery/LLM`, 차원은 `Model`만 사용해 카디널리티를
낮게 유지한다 — 세션ID 등 고카디널리티 값은 차원에 절대 넣지 않는다):
- `RequestLatencyMs`: 요청 전체 소요 시간 (밀리초).
- `TimeToFirstByteMs`: 스트리밍 응답 시 첫 번째 텍스트 청크 수신까지의 시간 (밀리초, TTFT).
- `BedrockCostUSD`: 요청 1건의 추정 비용(USD).
- `InputTokens` / `OutputTokens` / `CacheReadTokens` / `CacheWriteTokens`: 토큰 사용량.
- `SearchCacheHit` / `SearchCacheMiss`: Tavily 검색 결과 캐시(Redis) 히트/미스 카운트.
"""

import asyncio
import logging
from typing import Any

import boto3

logger = logging.getLogger(__name__)

NAMESPACE = "DPYB/Discovery/LLM"


def _metric_data(
    metric_name: str, value: float, *, unit: str, model_id: str | None
) -> dict[str, Any]:
    dimensions = [{"Name": "Model", "Value": model_id}] if model_id else []
    return {
        "MetricName": metric_name,
        "Value": value,
        "Unit": unit,
        "Dimensions": dimensions,
    }


class CloudWatchMetricsPublisher:
    """CloudWatch `PutMetricData`로 LLM 비용·토큰·캐시 메트릭을 발행한다.

    `enabled=False`(기본값)이면 모든 발행 메서드가 즉시 반환하는 no-op이 되어, 이
    클라이언트를 생성하는 것 자체도 AWS 자격증명/네트워크를 요구하지 않는다
    (boto3 클라이언트는 실제 발행이 필요한 시점에 지연 생성한다).
    """

    def __init__(self, *, enabled: bool, region_name: str | None = None) -> None:
        self._enabled = enabled
        self._region_name = region_name
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = boto3.client("cloudwatch", region_name=self._region_name)
        return self._client

    async def _put_metric_data(self, metric_data: list[dict[str, Any]]) -> None:
        """`PutMetricData`를 별도 스레드에서 실행한다. 실패는 로그로만 남기고 삼킨다."""
        if not self._enabled or not metric_data:
            return
        try:
            await asyncio.to_thread(
                self._get_client().put_metric_data,
                Namespace=NAMESPACE,
                MetricData=metric_data,
            )
        except Exception:
            logger.warning(
                "Failed to publish CloudWatch metrics (namespace=%s), continuing without it",
                NAMESPACE,
                exc_info=True,
            )

    async def publish_usage(
        self,
        *,
        model_id: str,
        cost_usd: float | None,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> None:
        """요청 1건의 Bedrock 비용·토큰 사용량을 CloudWatch에 발행한다.

        `cost_usd`가 `None`이면(단가 테이블에 없는 모델) 비용 메트릭은 발행하지 않고
        토큰 메트릭만 발행한다.
        """
        if not self._enabled:
            return

        metric_data = [
            _metric_data("InputTokens", float(input_tokens), unit="Count", model_id=model_id),
            _metric_data("OutputTokens", float(output_tokens), unit="Count", model_id=model_id),
        ]
        if cache_read_tokens:
            metric_data.append(
                _metric_data(
                    "CacheReadTokens", float(cache_read_tokens), unit="Count", model_id=model_id
                )
            )
        if cache_write_tokens:
            metric_data.append(
                _metric_data(
                    "CacheWriteTokens", float(cache_write_tokens), unit="Count", model_id=model_id
                )
            )
        if cost_usd is not None:
            metric_data.append(
                _metric_data("BedrockCostUSD", cost_usd, unit="None", model_id=model_id)
            )

        await self._put_metric_data(metric_data)

    async def publish_search_cache_event(self, *, hit: bool) -> None:
        """Tavily 검색 결과 캐시(Redis)의 히트/미스 이벤트 1건을 CloudWatch에 발행한다."""
        if not self._enabled:
            return

        metric_name = "SearchCacheHit" if hit else "SearchCacheMiss"
        metric_data = [_metric_data(metric_name, 1.0, unit="Count", model_id=None)]
        await self._put_metric_data(metric_data)

    async def publish_latency(
        self,
        *,
        model_id: str,
        total_ms: float,
        ttfb_ms: float | None = None,
    ) -> None:
        """요청 1건의 지연시간(전체 시간, 스트리밍 시 TTFT)을 CloudWatch에 발행한다.

        `ttfb_ms`는 스트리밍 응답(`stream_chat`)에서 첫 청크가 도착했을 때만 전달하며,
        동기 호출(`chat`)에서는 전달하지 않는다.
        """
        if not self._enabled:
            return

        metric_data = [
            _metric_data(
                "RequestLatencyMs",
                float(total_ms),
                unit="Milliseconds",
                model_id=model_id,
            )
        ]
        if ttfb_ms is not None:
            metric_data.append(
                _metric_data(
                    "TimeToFirstByteMs",
                    float(ttfb_ms),
                    unit="Milliseconds",
                    model_id=model_id,
                )
            )
        await self._put_metric_data(metric_data)
