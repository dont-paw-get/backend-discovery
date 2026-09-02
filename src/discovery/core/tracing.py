"""OpenTelemetry 분산 트레이싱 초기화.

설계 요약
---------
- `OTEL_EXPORTER_OTLP_ENDPOINT`(또는 `_TRACES_ENDPOINT`)가 설정된 경우에만 OTLP
  HTTP/protobuf exporter를 BatchSpanProcessor로 연결한다. 미설정이면 exporter
  없이 TracerProvider만 세팅하므로 Collector가 없는 로컬에서도 정상 실행된다.
- 샘플러/서비스명/리소스 속성은 표준 OTel 환경변수(`OTEL_TRACES_SAMPLER`,
  `OTEL_TRACES_SAMPLER_ARG`, `OTEL_SERVICE_NAME`, `OTEL_RESOURCE_ATTRIBUTES`)로
  제어한다. SDK 기본 동작을 그대로 활용한다.
- 전파는 W3C Trace Context(+baggage). 다른 backend가 보낸 `traceparent`를
  FastAPI 자동 계측이 이어받아 동일 Trace로 연결한다. 직접 헤더를 파싱하지 않는다.
- 자동 계측: FastAPI(서버 span, health probe 제외), redis, botocore(=Bedrock 포함),
  httpx(사서/서재 API 및 Tavily SDK 내부 호출).
- Strands Agent는 전역 TracerProvider를 자동 인식해 agent/cycle/tool/model span을
  스스로 생성한다. 다만 Strands tracer는 프롬프트·응답 원문을 span event/attribute에
  넣으므로, exporter 앞단에 `_SanitizingSpanExporter`를 두어 민감 내용을 제거하고
  구조/메트릭 정보만 내보낸다 (AI observability는 metadata 중심).
- exporter 전송 실패는 BatchSpanProcessor 백그라운드 스레드에서 흡수되어 요청
  처리에 영향을 주지 않는다.
- `opentelemetry-instrument` wrapper 없이 기존 uvicorn 실행 방식을 유지한다.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from typing import Any

from opentelemetry import trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = logging.getLogger(__name__)

_DEFAULT_SERVICE_NAME = "backend-discovery"

# Kubernetes probe 및 Prometheus 스크레이핑 경로 — 트레이싱 대상에서 제외 (부분 문자열/정규식 매칭).
_EXCLUDED_URLS = "health,healthz,readyz,livez,metrics"

# --- 민감 정보 스크러빙 정책 -------------------------------------------------

# Strands / 기타 계측이 span attribute로 실어보내는 프롬프트·본문류 키.
_SENSITIVE_SPAN_ATTRS = frozenset(
    {
        "system_prompt",
        "gen_ai.prompt",
        "gen_ai.completion",
        "gen_ai.input.messages",
        "gen_ai.output.messages",
        "gen_ai.system.message",
        "gen_ai.system_instructions",
        "gen_ai.tool.definitions",
        "gen_ai.agent.tools",
        "gen_ai.tool.call.arguments",
        "gen_ai.tool.result",
        "input.value",
        "output.value",
        "traceloop.entity.input",
        "traceloop.entity.output",
    }
)

# URL 전체가 담기는 attribute — query string(검색어/필터 등)을 제거한다.
_URL_ATTRS = frozenset({"url.full", "http.url", "url.query", "http.target"})

# str attribute 값 길이 상한(백스톱). 초과 시 길이만 남기고 내용은 버린다.
_MAX_ATTR_STR_LEN = 400

# 백스톱 길이 제한에서 제외할 키 프리픽스(운영 분석에 필요한 표준 필드).
_LENGTH_BACKSTOP_EXEMPT_PREFIXES = ("exception.", "code.", "db.statement")


def _scrub_attr_value(key: str, value: Any) -> Any:
    if key in _URL_ATTRS and isinstance(value, str):
        if key == "url.query":
            return "[stripped]"
        return value.split("?", 1)[0]
    if isinstance(value, str) and len(value) > _MAX_ATTR_STR_LEN:
        if not key.startswith(_LENGTH_BACKSTOP_EXEMPT_PREFIXES):
            return f"[redacted:{len(value)} chars]"
    return value


def _sanitize_span(span: Any) -> None:
    """ReadableSpan(=_Span)을 in-place로 스크러빙한다.

    - 프롬프트/응답 원문이 담기는 span event를 제거한다 (`exception` event는 보존).
    - 민감 attribute 키를 제거하고, 과도하게 긴 문자열 값을 마스킹한다.
    """
    raw_attributes = getattr(span, "_attributes", None)
    if raw_attributes:
        cleaned: dict[str, Any] = {}
        for key, value in dict(raw_attributes).items():
            if key in _SENSITIVE_SPAN_ATTRS:
                continue
            cleaned[key] = _scrub_attr_value(key, value)
        span._attributes = cleaned

    raw_events = getattr(span, "_events", None)
    if raw_events:
        span._events = [event for event in raw_events if event.name == "exception"]


class _SanitizingSpanExporter(SpanExporter):
    """delegate exporter로 넘기기 전에 각 span의 민감 정보를 제거하는 래퍼."""

    def __init__(self, delegate: SpanExporter) -> None:
        self._delegate = delegate

    def export(self, spans: Sequence[Any]) -> SpanExportResult:
        for span in spans:
            try:
                _sanitize_span(span)
            except Exception:  # noqa: BLE001 - 스크러빙 실패가 export를 막지 않도록
                logger.warning("[OTEL] span sanitize failed", exc_info=True)
        return self._delegate.export(spans)

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return self._delegate.force_flush(timeout_millis)

    def shutdown(self) -> None:
        self._delegate.shutdown()


# --- 초기화 ----------------------------------------------------------------

_configured = False


def _otlp_endpoint_configured() -> bool:
    return bool(
        os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
        or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    )


def _build_resource() -> Resource:
    # OTEL_SERVICE_NAME 미설정 시 기본값을 넣어준다 (명시 설정이 항상 우선).
    os.environ.setdefault("OTEL_SERVICE_NAME", _DEFAULT_SERVICE_NAME)
    # Resource.create()가 OTEL_SERVICE_NAME / OTEL_RESOURCE_ATTRIBUTES를 자동 병합한다.
    return Resource.create()


def instrument_fastapi_app(app: Any) -> None:
    """FastAPI app 인스턴스에 서버 span 계측을 적용한다 (health probe 제외).

    전역 `FastAPIInstrumentor().instrument()`는 계측 활성화 시점보다 먼저
    `from fastapi import FastAPI`로 클래스를 바인딩한 모듈에는 적용되지 않으므로,
    app 생성부에서 명시적으로 이 함수를 호출한다.
    """
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=trace.get_tracer_provider(),
            excluded_urls=_EXCLUDED_URLS,
        )
    except Exception:  # noqa: BLE001
        logger.warning("[OTEL] FastAPI app instrumentation failed", exc_info=True)


def _instrument_libraries(tracer_provider: TracerProvider) -> None:
    """인프라 클라이언트 자동 계측을 활성화한다. 개별 실패가 초기화를 막지 않는다."""
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument(tracer_provider=tracer_provider)
    except Exception:  # noqa: BLE001
        logger.warning("[OTEL] redis instrumentation failed", exc_info=True)

    try:
        from opentelemetry.instrumentation.botocore import BotocoreInstrumentor

        BotocoreInstrumentor().instrument(  # type: ignore[no-untyped-call]
            tracer_provider=tracer_provider
        )
    except Exception:  # noqa: BLE001
        logger.warning("[OTEL] botocore instrumentation failed", exc_info=True)

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument(tracer_provider=tracer_provider)
    except Exception:  # noqa: BLE001
        logger.warning("[OTEL] httpx instrumentation failed", exc_info=True)


def configure_tracing() -> None:
    """분산 트레이싱을 초기화한다. FastAPI app 생성 전에 1회 호출한다 (idempotent)."""
    global _configured
    if _configured:
        return

    resource = _build_resource()
    # 샘플러는 OTEL_TRACES_SAMPLER / OTEL_TRACES_SAMPLER_ARG 환경변수로 결정된다
    # (미설정 시 SDK 기본값 parentbased_always_on).
    tracer_provider = TracerProvider(resource=resource)

    if _otlp_endpoint_configured():
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = _SanitizingSpanExporter(OTLPSpanExporter())
            tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info(
                "[OTEL] OTLP trace exporter enabled (service=%s)",
                resource.attributes.get("service.name"),
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "[OTEL] OTLP exporter init failed; continuing without export",
                exc_info=True,
            )
    else:
        logger.info(
            "[OTEL] OTEL_EXPORTER_OTLP_ENDPOINT not set; tracing runs without export"
        )

    trace.set_tracer_provider(tracer_provider)
    set_global_textmap(
        CompositePropagator(
            [TraceContextTextMapPropagator(), W3CBaggagePropagator()]
        )
    )
    _instrument_libraries(tracer_provider)

    _configured = True
