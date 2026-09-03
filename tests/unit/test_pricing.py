"""core/pricing.py — Bedrock 토큰 사용량 → USD 비용 계산 순수 함수 검증.

결정론적 계산이므로 실제 AWS/네트워크 호출 없이 입력값과 기대 출력값만 검증한다.
"""

from discovery.core.pricing import SONNET_5_MODEL_ID, estimate_cost_usd


def test_estimate_cost_usd_computes_input_and_output_tokens() -> None:
    usage = {"inputTokens": 1000, "outputTokens": 1000}
    cost = estimate_cost_usd(SONNET_5_MODEL_ID, usage)
    # 입력 1000토큰 * $0.003/1k + 출력 1000토큰 * $0.015/1k = $0.018
    assert cost == 0.018


def test_estimate_cost_usd_includes_cache_read_and_write_tokens() -> None:
    usage = {
        "inputTokens": 0,
        "outputTokens": 0,
        "cacheReadInputTokens": 1000,
        "cacheWriteInputTokens": 1000,
    }
    cost = estimate_cost_usd(SONNET_5_MODEL_ID, usage)
    # 캐시읽기 1000 * $0.0003/1k + 캐시쓰기 1000 * $0.00375/1k = $0.00405
    assert cost == 0.00405


def test_estimate_cost_usd_missing_keys_default_to_zero() -> None:
    cost = estimate_cost_usd(SONNET_5_MODEL_ID, {})
    assert cost == 0.0


def test_estimate_cost_usd_unknown_model_returns_none() -> None:
    cost = estimate_cost_usd("unknown-model-id", {"inputTokens": 1000})
    assert cost is None


def test_estimate_cost_usd_ignores_negative_token_counts() -> None:
    """usage 딕셔너리에 방어적으로 음수가 섞여도 비용이 음수가 되지 않는다."""
    usage = {"inputTokens": -500, "outputTokens": 1000}
    cost = estimate_cost_usd(SONNET_5_MODEL_ID, usage)
    # 음수 입력은 0으로 clamp, 출력만 반영: 1000 * $0.015/1k = $0.015
    assert cost == 0.015


def test_estimate_cost_usd_rounds_to_six_decimal_places() -> None:
    usage = {"inputTokens": 1, "outputTokens": 0}
    cost = estimate_cost_usd(SONNET_5_MODEL_ID, usage)
    assert cost == round(0.001 / 1000 * 3, 6)
