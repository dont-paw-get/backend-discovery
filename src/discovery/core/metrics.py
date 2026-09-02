"""Prometheus HTTP 서버 메트릭 (Micrometer 호환 이름).

infra(dont-paw-get/infra)의 "HTTP 5xx 에러율" / "p99 레이턴시" 알림 규칙은 Spring
Micrometer가 노출하는 `http_server_requests_seconds_*` 메트릭 기준으로 작성돼 있다.
이 서비스는 Spring이 아니지만 **동일한 메트릭 이름·구조**(히스토그램 + `_count`/`_sum`)를
내보내 infra 알림 규칙을 수정 없이 재사용하게 한다.

- 메트릭: `http_server_requests_seconds` (Histogram)
  라벨: `method`, `uri`, `status`, `outcome`, `application`
  → `http_server_requests_seconds_bucket`(le) / `_count` / `_sum` 자동 생성.
- `application` 라벨 = `OTEL_SERVICE_NAME` (트레이스 `service.name`과 강제 일치) →
  RCA Agent가 메트릭 ↔ 로그 ↔ 트레이스를 같은 서비스로 상관분석한다.
- 스트리밍 응답(이 서비스의 주 경로)도 마지막 body 청크까지의 wall-clock을 계측하기
  위해 `BaseHTTPMiddleware`가 아니라 순수 ASGI 미들웨어로 구현한다.
- k8s probe(`/health`)와 스크레이핑 경로(`/metrics`)는 계측에서 제외한다.
"""

from __future__ import annotations

import os
import time
from typing import Any

from prometheus_client import CONTENT_TYPE_LATEST, Histogram, generate_latest
from starlette.types import ASGIApp, Message, Receive, Scope, Send

METRICS_PATH = "/metrics"

# 계측 대상에서 제외할 경로(probe·스크레이핑). tracing._EXCLUDED_URLS와 목적이 같다.
_EXCLUDED_PATHS = frozenset({METRICS_PATH, "/health", "/api/v1/health"})

# 메트릭 태그값을 트레이스 service.name과 동일하게 맞춘다 (미설정 시 기본값 동일).
_APPLICATION = os.environ.get("OTEL_SERVICE_NAME", "").strip() or "backend-discovery"

# LLM 응답이 30~40초대라 Prometheus 기본 상한(10초)에서 끊지 않고 60초까지 확장한다.
_LATENCY_BUCKETS = (
    0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0, 45.0, 60.0,
)

http_server_requests_seconds = Histogram(
    "http_server_requests_seconds",
    "HTTP 서버 요청 지연 시간 및 처리량 (Micrometer 호환)",
    labelnames=("method", "uri", "status", "outcome", "application"),
    buckets=_LATENCY_BUCKETS,
)


def _outcome(status_code: int) -> str:
    """HTTP 상태 코드 계열을 Micrometer `outcome` 태그 값으로 변환한다."""
    if 200 <= status_code < 300:
        return "SUCCESS"
    if 300 <= status_code < 400:
        return "REDIRECTION"
    if 400 <= status_code < 500:
        return "CLIENT_ERROR"
    if status_code >= 500:
        return "SERVER_ERROR"
    return "INFORMATIONAL"


def _normalize_uri(path: str, path_params: dict[str, Any]) -> str:
    """실제 경로에서 path 파라미터 값을 `{name}` 템플릿으로 되돌려 카디널리티를 낮춘다."""
    for name, value in path_params.items():
        if isinstance(value, str) and value:
            path = path.replace(value, "{" + name + "}")
    return path or "/"


class PrometheusMiddleware:
    """요청별 지연 시간을 `http_server_requests_seconds`에 기록하는 순수 ASGI 미들웨어."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path", "") in _EXCLUDED_PATHS:
            await self._app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - start
            # 라우터가 동일 scope를 in-place로 갱신하므로 호출 이후 endpoint 매칭 여부를 알 수 있다.
            if "endpoint" in scope:
                uri = _normalize_uri(scope.get("path", ""), dict(scope.get("path_params") or {}))
            else:
                uri = "NO_ROUTE"
            http_server_requests_seconds.labels(
                method=scope.get("method", "UNKNOWN"),
                uri=uri,
                status=str(status_code),
                outcome=_outcome(status_code),
                application=_APPLICATION,
            ).observe(elapsed)


def render_latest() -> tuple[bytes, str]:
    """`/metrics` 응답 본문과 Content-Type을 반환한다."""
    return generate_latest(), CONTENT_TYPE_LATEST
