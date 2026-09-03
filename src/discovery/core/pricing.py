"""Bedrock 모델 토큰 단가 및 요청당 비용(USD) 계산.

CLIAR-276: LLM 파이프라인 자체의 비용 관측이 비어 있어(토큰 수는 로그에 있으나 USD로
환산되지 않음), 이 모듈이 그 계산만 순수 함수로 담당한다. 계산 결과의 소비처(CloudWatch
전송 등)는 이 모듈의 책임이 아니다 — `core/cloudwatch_metrics.py`가 담당한다.

현재 이 서비스는 Sonnet 5(`global.anthropic.claude-sonnet-5`) 단일 모델만 사용한다
(`core/config.py`, AGENTS.md SCP 정책상 다른 모델 전환·실측 여유가 없음). 단가 테이블은
딕셔너리 구조로 두어 향후 모델이 추가되면 행 하나만 추가하면 되도록 확장 지점을 미리
마련한다(지금은 1개 행만 등록).

단가 출처 및 기준일 (2026-09-04 확인):
- Anthropic 공식 발표(https://www.anthropic.com/claude/sonnet) 및 Bedrock 리셀러
  교차 검증(requesty.ai, futureagi.com) 기준 Sonnet 5 정가: 입력 $3/output $15 (1M 토큰당),
  2026-09-01부터 적용(2026-08-31까지의 소개가 $2/$10는 이미 종료됨 — 확인 시점 기준 정가 채택).
- 프롬프트 캐시 읽기(cache read)는 입력가의 10%로 계산한다(Anthropic 공식 "최대 90% 절감"
  발표 및 캐시 읽기 실측가 $0.30/M 교차 확인 — 정가 $3 기준 10%와 일치).
- 프롬프트 캐시 쓰기(cache write, 5분 TTL 기준)는 Anthropic 표준 정책상 입력가의 1.25배로
  계산한다. 이 서비스는 현재 `enable_prompt_caching=False`(CLIAR-158)라 캐시 쓰기가
  실제로는 발생하지 않지만, 활성화될 경우를 대비해 단가를 미리 등록해 둔다.
- AWS 리전별 단가 차이는 이번 범위에서 반영하지 않는다(글로벌 크로스리전 프로필 사용 중이라
  단일 리전 단가를 특정하기 어려움 — 필요 시 실제 청구서 대비 검증 후 리전별 계수 추가 검토).
"""

from dataclasses import dataclass
from typing import Final

# 모델 ID는 core/config.py의 librarian_model_id / orchestrator_model_id 값과 1:1 대응한다.
SONNET_5_MODEL_ID: Final[str] = "global.anthropic.claude-sonnet-5"


@dataclass(frozen=True)
class TokenPricing:
    """모델 1종의 토큰 타입별 단가(1,000 토큰당 USD)."""

    input_per_1k: float
    output_per_1k: float
    cache_read_per_1k: float
    cache_write_per_1k: float


# 모델 ID -> 단가. 모델이 추가되면 이 dict에 행만 추가한다(코드 로직 변경 불필요).
MODEL_PRICING: Final[dict[str, TokenPricing]] = {
    SONNET_5_MODEL_ID: TokenPricing(
        input_per_1k=0.003,
        output_per_1k=0.015,
        cache_read_per_1k=0.0003,
        cache_write_per_1k=0.00375,
    ),
}


def estimate_cost_usd(model_id: str, usage: dict[str, int]) -> float | None:
    """Bedrock `accumulated_usage` 딕셔너리로부터 요청 1건의 예상 비용(USD)을 계산한다.

    Args:
        model_id: 호출에 사용된 Bedrock 모델 ID(`core/config.py`의 `*_model_id` 값).
        usage: Strands `AgentResult.metrics.get_summary()["accumulated_usage"]` 형태의
            딕셔너리. 키는 `inputTokens`, `outputTokens`, `cacheReadInputTokens`,
            `cacheWriteInputTokens`를 기대하며, 없는 키는 0으로 취급한다.

    Returns:
        예상 비용(USD, 소수점 6자리 반올림). 단가 테이블에 없는 `model_id`이면 `None`을
        반환한다(비용을 추정할 수 없음을 명시적으로 알리기 위해 0.0으로 눙치지 않는다).
    """
    pricing = MODEL_PRICING.get(model_id)
    if pricing is None:
        return None

    input_tokens = max(int(usage.get("inputTokens", 0) or 0), 0)
    output_tokens = max(int(usage.get("outputTokens", 0) or 0), 0)
    cache_read_tokens = max(int(usage.get("cacheReadInputTokens", 0) or 0), 0)
    cache_write_tokens = max(int(usage.get("cacheWriteInputTokens", 0) or 0), 0)

    cost = (
        (input_tokens / 1000) * pricing.input_per_1k
        + (output_tokens / 1000) * pricing.output_per_1k
        + (cache_read_tokens / 1000) * pricing.cache_read_per_1k
        + (cache_write_tokens / 1000) * pricing.cache_write_per_1k
    )
    return round(cost, 6)
