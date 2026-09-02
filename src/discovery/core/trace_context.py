"""활성 OpenTelemetry Span Context에서 trace_id/span_id를 추출하는 헬퍼.

로깅 포매터와 구조화 메트릭 로그가 공통으로 사용한다. business/domain 코드가
OpenTelemetry SDK에 직접 의존하지 않도록 이 한 곳에만 의존성을 둔다.
"""

from __future__ import annotations

from opentelemetry import trace


def current_trace_ids() -> tuple[str | None, str | None]:
    """현재 활성 span의 (trace_id, span_id)를 W3C 포맷 hex 문자열로 반환한다.

    - trace_id: 32자리 소문자 hex
    - span_id: 16자리 소문자 hex
    - 활성/유효한 span이 없으면 (None, None)
    """
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None, None
    return f"{span_context.trace_id:032x}", f"{span_context.span_id:016x}"
