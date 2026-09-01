"""observability.py 단위 테스트."""

import json
import logging
from unittest.mock import MagicMock

import pytest

from discovery.core.observability import log_agent_metrics


def test_log_agent_metrics_emits_json(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="discovery.observability"):
        log_agent_metrics(
            phase="orchestrator",
            session_id="sess-123",
            librarian_id="cat",
            mode="stream",
            message_length=15,
            metrics_summary={
                "total_cycles": 2,
                "total_duration": 1.25,
                "average_cycle_time": 0.625,
                "tool_usage": {"recommend_books": {"total_time": 0.8}},
                "accumulated_usage": {
                    "inputTokens": 500,
                    "outputTokens": 120,
                    "cacheReadInputTokens": 300,
                },
            },
            direct_metrics={"ttfb_ms": 350.5, "total_duration_ms": 1250.0},
        )

    assert len(caplog.records) == 1
    log_record = caplog.records[0]
    payload = json.loads(log_record.message)

    assert payload["event"] == "agent_metrics"
    assert payload["phase"] == "orchestrator"
    assert payload["session_id"] == "sess-123"
    assert payload["librarian_id"] == "cat"
    assert payload["mode"] == "stream"
    assert payload["message_length"] == 15
    assert payload["direct_metrics"]["ttfb_ms"] == 350.5
    assert payload["direct_metrics"]["total_duration_ms"] == 1250.0
    assert payload["strands_metrics"]["total_cycles"] == 2
    assert payload["strands_metrics"]["accumulated_usage"]["cacheReadInputTokens"] == 300


def test_log_agent_metrics_handles_mock_and_none_safely(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="discovery.observability"):
        log_agent_metrics(
            phase="recommend_agent",
            session_id="sess-mock",
            metrics_summary={"mock_obj": MagicMock()},
            direct_metrics=None,
        )

    assert len(caplog.records) == 1
    log_record = caplog.records[0]
    payload = json.loads(log_record.message)
    assert payload["event"] == "agent_metrics"
    assert payload["phase"] == "recommend_agent"
    assert payload["session_id"] == "sess-mock"
    assert payload["librarian_id"] == "cat"


def test_log_agent_metrics_filters_out_sensitive_input_params(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_message = "요즘 우울해서 병원 다녀요, 홍길동 010-1234-5678"
    raw_tool_usage = {
        "consult_librarian": {
            "tool_info": {
                "name": "consult_librarian",
                "input_params": {"message": sensitive_message},
            },
            "execution_stats": {
                "invocations": 1,
                "total_time": 0.45,
            },
        },
        "recommend_books": {
            "tool_info": {
                "name": "recommend_books",
                "input_params": {"query": "비밀 검색어"},
            },
            "execution_stats": {
                "invocations": 1,
                "total_time": 1.2,
            },
        },
    }

    with caplog.at_level(logging.INFO, logger="discovery.observability"):
        log_agent_metrics(
            phase="orchestrator",
            session_id="sess-privacy",
            message_length=len(sensitive_message),
            metrics_summary={"tool_usage": raw_tool_usage},
        )

    assert len(caplog.records) == 1
    log_record = caplog.records[0]
    # Verify sensitive data is NOT anywhere in the log string
    assert sensitive_message not in log_record.message
    assert "비밀 검색어" not in log_record.message
    assert "input_params" not in log_record.message
    assert "tool_info" not in log_record.message

    payload = json.loads(log_record.message)
    tool_usage = payload["strands_metrics"]["tool_usage"]
    assert "consult_librarian" in tool_usage
    assert tool_usage["consult_librarian"] == {
        "execution_stats": {"invocations": 1, "total_time": 0.45}
    }
    assert tool_usage["recommend_books"] == {
        "execution_stats": {"invocations": 1, "total_time": 1.2}
    }

