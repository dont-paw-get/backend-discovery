"""구조화된 stdout JSON 로깅.

Grafana Alloy가 컨테이너 stdout을 수집해 Loki로 전달하므로 Loki client는 두지
않는다. 각 로그 레코드에 활성 OpenTelemetry Span Context의 trace_id/span_id를
JSON 필드로 주입해 Loki ↔ Tempo correlation을 가능하게 한다.

로그 한 줄 = valid JSON 한 개. 최소 필드:
    timestamp, level, service, logger, message, trace_id, span_id, exception

trace_id/span_id는 high-cardinality 값이므로 JSON 필드로만 유지하고 Loki label로
승격하지 않는다 (Alloy 수집 설정 쪽 책임).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from discovery.core.trace_context import current_trace_ids

# logging.LogRecord의 표준 필드. 이 외의 항목만 추가 컨텍스트(extra)로 취급한다.
_STANDARD_LOGRECORD_FIELDS = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "taskName", "message", "asctime",
    }
)

# extra로 흘러들어올 수 있는 민감 키. 값 자체를 남기지 않고 마스킹한다.
_SENSITIVE_EXTRA_KEYS = (
    "authorization", "auth_token", "token", "access_token", "refresh_token",
    "id_token", "cookie", "api_key", "apikey", "secret", "password", "credential",
    "aws_access_key", "aws_secret", "session_token", "prompt", "system_prompt",
    "message_text", "query_text", "answer", "response_body", "request_body",
)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in _SENSITIVE_EXTRA_KEYS)


class JsonLogFormatter(logging.Formatter):
    """LogRecord를 단일 JSON 라인으로 직렬화하는 포매터."""

    def __init__(self, *, service_name: str) -> None:
        super().__init__()
        self._service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        trace_id, span_id = current_trace_ids()

        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "service": self._service_name,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": trace_id,
            "span_id": span_id,
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        elif record.exc_text:
            payload["exception"] = record.exc_text

        for key, value in record.__dict__.items():
            if key in _STANDARD_LOGRECORD_FIELDS or key.startswith("_"):
                continue
            if key in payload:
                continue
            payload[key] = "[REDACTED]" if _is_sensitive_key(key) else value

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_json_logging(*, service_name: str, level: int = logging.INFO) -> None:
    """루트 로거를 stdout JSON 핸들러 하나로 재구성한다.

    uvicorn/애플리케이션 로그가 모두 동일한 JSON 포맷으로 stdout에 출력된다.
    파일 핸들러는 두지 않는다 (Pod 내부 로그 파일 금지).
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter(service_name=service_name))

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

    # 애플리케이션 로거는 항상 INFO 이상을 관측한다 (uvicorn 기본 effective level 회피).
    logging.getLogger("discovery").setLevel(level)

    # uvicorn access 로그는 FastAPI 자동 계측 span과 중복되므로 억제한다.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
