"""구조화 레이턴시 및 메트릭 로깅 모듈.

- 단일 JSON 라인 로깅 (logger.info)
- 개인정보 보호: 사용자 메시지 원문은 로깅하지 않고 message_length만 기록
- Strands AgentResult.metrics 요약 덤프 및 직접 계측 구간(TTFB, initial_meta 등) 기록
"""

import json
import logging
from typing import Any

logger = logging.getLogger("discovery.observability")


def log_agent_metrics(
    *,
    phase: str,
    session_id: str,
    librarian_id: str | None = None,
    mode: str = "sync",
    message_length: int | None = None,
    metrics_summary: dict[str, Any] | None = None,
    direct_metrics: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Agent 실행 메트릭 및 계측 데이터를 단일 JSON 라인으로 로깅한다."""
    payload: dict[str, Any] = {
        "event": "agent_metrics",
        "phase": phase,
        "session_id": session_id,
        "librarian_id": librarian_id or "cat",
        "mode": mode,
    }
    if message_length is not None:
        payload["message_length"] = message_length

    if direct_metrics:
        payload["direct_metrics"] = direct_metrics

    if metrics_summary:
        filtered_tool_usage: dict[str, Any] = {}
        raw_tool_usage = metrics_summary.get("tool_usage")
        if isinstance(raw_tool_usage, dict):
            for tool_name, usage_val in raw_tool_usage.items():
                if isinstance(usage_val, dict):
                    filtered_tool_usage[tool_name] = {
                        "execution_stats": usage_val.get("execution_stats", {}),
                    }
                else:
                    filtered_tool_usage[tool_name] = {}

        payload["strands_metrics"] = {
            "total_cycles": metrics_summary.get("total_cycles", 0),
            "total_duration": metrics_summary.get("total_duration", 0),
            "average_cycle_time": metrics_summary.get("average_cycle_time", 0),
            "tool_usage": filtered_tool_usage,
            "accumulated_usage": metrics_summary.get("accumulated_usage", {}),
        }

    if extra:
        payload.update(extra)

    try:
        logger.info(json.dumps(payload, ensure_ascii=False, default=str))
    except Exception as e:
        logger.warning("[OBSERVABILITY_LOG_FAILED] Failed to serialize metrics log: %s", e)
