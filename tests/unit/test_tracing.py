"""OpenTelemetry 트레이싱 + 구조화 JSON 로깅 검증.

커버리지:
- OTEL_EXPORTER_OTLP_ENDPOINT 미설정에서도 초기화가 예외 없이 동작 (idempotent)
- endpoint 감지 로직이 두 환경변수를 모두 읽음
- /health 등 probe는 server span 제외, 일반 경로는 server span 생성
- inbound traceparent를 이어받아 동일 Trace ID 유지 (직접 파싱 없이 propagator/계측)
- httpx / redis / botocore 아웃바운드 자동 계측 활성화
- JSON 로그가 한 줄 valid JSON, trace_id(32)/span_id(16) hex 주입, 민감 키 마스킹
- span sanitizer가 프롬프트/시스템 프롬프트/장문/gen_ai 이벤트 제거, 토큰·예외는 보존
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

import httpx
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


# --------------------------------------------------------------------------- #
# 초기화                                                                       #
# --------------------------------------------------------------------------- #
def test_configure_tracing_is_idempotent_without_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    from discovery.core import tracing

    tracing.configure_tracing()
    tracing.configure_tracing()  # 두 번째 호출도 예외 없이 no-op


def test_endpoint_detection_reads_both_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    from discovery.core import tracing

    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    assert tracing._otlp_endpoint_configured() is False

    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "http://otel-collector.monitoring.svc.cluster.local:4318",
    )
    assert tracing._otlp_endpoint_configured() is True


# --------------------------------------------------------------------------- #
# FastAPI: server span, health 제외, traceparent 연속성                         #
# --------------------------------------------------------------------------- #
@pytest.fixture
def span_exporter() -> InMemorySpanExporter:
    """전역(이미 계측된) TracerProvider에 in-memory exporter를 임시로 부착한다."""
    exporter = InMemorySpanExporter()
    provider = trace.get_tracer_provider()
    assert isinstance(provider, TracerProvider)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


def _server_spans(exporter: InMemorySpanExporter) -> list[ReadableSpan]:
    return [s for s in exporter.get_finished_spans() if s.kind.name == "SERVER"]


async def _get(app: Any, path: str, headers: dict[str, str] | None = None) -> int:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(path, headers=headers or {})
    return response.status_code


@pytest.mark.asyncio
async def test_health_probe_excluded_but_normal_route_has_server_span(
    span_exporter: InMemorySpanExporter,
) -> None:
    from discovery.main import create_app

    app = create_app()

    async def ping() -> dict[str, str]:
        return {"pong": "ok"}

    app.router.add_api_route("/__otel_ping__", ping, methods=["GET"])

    assert await _get(app, "/health") == 200
    assert await _get(app, "/api/v1/health") == 200
    assert await _get(app, "/__otel_ping__") == 200

    routes = {
        str(s.attributes.get("http.route") if s.attributes else "") or s.name
        for s in _server_spans(span_exporter)
    }
    assert any("__otel_ping__" in route for route in routes)
    assert not any("health" in route for route in routes)


@pytest.mark.asyncio
async def test_inbound_traceparent_is_continued_with_same_trace_id(
    span_exporter: InMemorySpanExporter,
) -> None:
    from discovery.main import create_app

    app = create_app()

    async def ping() -> dict[str, str]:
        return {"pong": "ok"}

    app.router.add_api_route("/__otel_tp__", ping, methods=["GET"])

    upstream_trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    traceparent = f"00-{upstream_trace_id}-00f067aa0ba902b7-01"

    assert await _get(app, "/__otel_tp__", {"traceparent": traceparent}) == 200

    server_spans = _server_spans(span_exporter)
    assert server_spans
    assert any(f"{s.context.trace_id:032x}" == upstream_trace_id for s in server_spans)


def test_outbound_and_infra_clients_are_instrumented() -> None:
    """사서/서재 API·Tavily(httpx), Redis, Bedrock(botocore) 자동 계측이 켜져 있다."""
    from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor

    import discovery.main  # noqa: F401  (import 시 configure_tracing 실행)

    assert HTTPXClientInstrumentor().is_instrumented_by_opentelemetry
    assert RedisInstrumentor().is_instrumented_by_opentelemetry
    assert BotocoreInstrumentor().is_instrumented_by_opentelemetry  # type: ignore[no-untyped-call]


# --------------------------------------------------------------------------- #
# Span sanitizer                                                               #
# --------------------------------------------------------------------------- #
def _make_span(
    attributes: dict[str, Any], events: list[tuple[str, dict[str, Any]]]
) -> ReadableSpan:
    provider = TracerProvider()
    span = provider.get_tracer("t").start_span("invoke_agent")
    for key, value in attributes.items():
        span.set_attribute(key, value)
    for name, attrs in events:
        span.add_event(name, attributes=attrs)
    span.end()
    assert isinstance(span, ReadableSpan)
    return span


def test_sanitizer_strips_prompt_and_content_keeps_metrics() -> None:
    from discovery.core.tracing import _sanitize_span

    span = _make_span(
        attributes={
            "system_prompt": "당신은 사서입니다 ...",
            "gen_ai.input.messages": '[{"role":"user","content":"내 비밀 질문"}]',
            "gen_ai.usage.total_tokens": 123,
            "gen_ai.request.model": "global.anthropic.claude-sonnet-5",
            "gen_ai.operation.name": "invoke_agent",
            "big": "x" * 5000,
        },
        events=[
            ("gen_ai.user.message", {"content": "내 비밀 질문 원문"}),
            ("gen_ai.choice", {"message": "LLM 전체 응답 원문"}),
            ("exception", {"exception.type": "ValueError"}),
        ],
    )
    _sanitize_span(span)

    attrs = span.attributes or {}
    assert "system_prompt" not in attrs
    assert "gen_ai.input.messages" not in attrs
    assert attrs["gen_ai.usage.total_tokens"] == 123
    assert attrs["gen_ai.request.model"] == "global.anthropic.claude-sonnet-5"
    assert str(attrs["big"]).startswith("[redacted:")
    assert [e.name for e in span.events] == ["exception"]


def test_sanitizer_strips_url_query_string() -> None:
    from discovery.core.tracing import _sanitize_span

    span = _make_span(
        attributes={"url.full": "http://backend-book.local/api/v1/library/books?author=name"},
        events=[],
    )
    _sanitize_span(span)
    attrs = span.attributes or {}
    assert attrs["url.full"] == "http://backend-book.local/api/v1/library/books"


def test_sanitizing_exporter_delegates_cleaned_spans() -> None:
    from discovery.core.tracing import _SanitizingSpanExporter

    delegate = InMemorySpanExporter()
    exporter = _SanitizingSpanExporter(delegate)

    span = _make_span(
        attributes={"system_prompt": "secret"},
        events=[("gen_ai.choice", {"message": "x"})],
    )
    exporter.export([span])

    exported = delegate.get_finished_spans()[0]
    assert "system_prompt" not in (exported.attributes or {})
    assert list(exported.events) == []


# --------------------------------------------------------------------------- #
# JSON 로깅                                                                    #
# --------------------------------------------------------------------------- #
def _format_record(record: logging.LogRecord) -> dict[str, Any]:
    from discovery.core.logging import JsonLogFormatter

    line = JsonLogFormatter(service_name="backend-discovery").format(record)
    assert "\n" not in line
    payload: dict[str, Any] = json.loads(line)
    return payload


def _make_record(**extra: Any) -> logging.LogRecord:
    record = logging.LogRecord(
        name="discovery.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="discovery request completed",
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_log_has_minimum_fields() -> None:
    payload = _format_record(_make_record())
    for key in ("timestamp", "level", "service", "logger", "message", "trace_id", "span_id"):
        assert key in payload
    assert payload["level"] == "INFO"
    assert payload["service"] == "backend-discovery"
    assert payload["message"] == "discovery request completed"


def test_json_log_trace_ids_null_without_active_span() -> None:
    payload = _format_record(_make_record())
    assert payload["trace_id"] is None
    assert payload["span_id"] is None


def test_json_log_trace_ids_injected_with_active_span(
    span_exporter: InMemorySpanExporter,
) -> None:
    with trace.get_tracer("test").start_as_current_span("unit"):
        payload = _format_record(_make_record())
    assert payload["trace_id"] is not None
    assert len(payload["trace_id"]) == 32
    assert len(payload["span_id"]) == 16
    assert payload["trace_id"] == payload["trace_id"].lower()
    int(payload["trace_id"], 16)
    int(payload["span_id"], 16)


def test_json_log_masks_sensitive_extra_keys() -> None:
    payload = _format_record(
        _make_record(authorization="Bearer abc", api_key="sk-123", result_count=5)
    )
    assert payload["authorization"] == "[REDACTED]"
    assert payload["api_key"] == "[REDACTED]"
    assert payload["result_count"] == 5


def test_json_log_exception_field_on_exc_info() -> None:
    from discovery.core.logging import JsonLogFormatter

    try:
        raise RuntimeError("bedrock down")
    except RuntimeError:
        record = logging.LogRecord(
            name="discovery.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="agent failed",
            args=(),
            exc_info=sys.exc_info(),
        )
    payload: dict[str, Any] = json.loads(
        JsonLogFormatter(service_name="backend-discovery").format(record)
    )
    assert "RuntimeError: bedrock down" in payload["exception"]


# --------------------------------------------------------------------------- #
# 민감정보 보호 (구조화 메트릭 로그)                                            #
# --------------------------------------------------------------------------- #
def test_log_agent_metrics_has_no_prompt_or_keys(caplog: pytest.LogCaptureFixture) -> None:
    from discovery.core.observability import log_agent_metrics

    secret_prompt = "SYSTEM: 당신은 사서. USER: 내 신용카드 번호는..."
    with caplog.at_level(logging.INFO, logger="discovery.observability"):
        log_agent_metrics(
            phase="orchestrator",
            session_id="s1",
            message_length=len(secret_prompt),
            metrics_summary={
                "total_cycles": 1,
                "accumulated_usage": {"inputTokens": 10, "outputTokens": 3},
                "tool_usage": {"recommend_books": {"execution_stats": {"invocations": 1}}},
            },
        )
    line = caplog.records[-1].getMessage()
    assert secret_prompt not in line
    assert "sk-" not in line
    payload: dict[str, Any] = json.loads(line)
    assert "prompt" not in payload
