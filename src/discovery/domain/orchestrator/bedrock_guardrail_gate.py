"""Amazon Bedrock Guardrails 기반 입력 검증 게이트 (BedrockGuardrailGate).

사용자의 프롬프트에 악의적인 프롬프트 인젝션(Prompt Injection), 탈옥(Jailbreak),
시스템 프롬프트 탈취, 유해 콘텐츠(Denied Topics), 개인정보(PII) 노출 시도가 있는지
AWS Bedrock ApplyGuardrail API를 통해 LLM 호출 전(Pre-flight)에 사전 차단한다.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

CAT_GUARDRAIL_BLOCKED_RESPONSE = (
    "냥? 그 요청은 보안 및 안전 정책상 도와드릴 수 없다냥! 🐾 "
    "도서 추천이나 서재 관련 질문을 편하게 말씀해달라냥."
)

STORK_GUARDRAIL_BLOCKED_RESPONSE = (
    "두둥! 입력하신 내용은 보안 및 서비스 안전 가이드라인에 따라 처리할 수 없습니다. 🪶 "
    "도서 추천이나 독서 활동에 관한 질문을 부탁드립니다."
)

DEFAULT_GUARDRAIL_BLOCKED_RESPONSE = (
    "입력하신 내용은 보안 및 서비스 안전 가이드라인에 따라 처리할 수 없습니다."
)


def get_guardrail_blocked_response(librarian_id: str | None = None) -> str:
    """페르소나에 맞는 가드레일 차단 응답 문구를 반환한다."""
    if librarian_id == "stork":
        return STORK_GUARDRAIL_BLOCKED_RESPONSE
    return CAT_GUARDRAIL_BLOCKED_RESPONSE


async def evaluate_bedrock_guardrail(
    message: str,
    librarian_id: str | None,
    *,
    bedrock_client: Any | None,
    guardrail_id: str | None,
    guardrail_version: str = "DRAFT",
    enabled: bool = False,
) -> str | None:
    """Bedrock ApplyGuardrail API로 사용자 입력을 사전 검증한다.

    Returns:
        차단 시 페르소나 안내 메시지(str), 안전하거나 비활성화/에러 시 None (통과).
    """
    if not enabled or not guardrail_id or bedrock_client is None:
        return None

    if not message or not message.strip():
        return None

    try:

        def _call_apply_guardrail() -> dict[str, Any]:
            return bedrock_client.apply_guardrail(  # type: ignore[no-any-return]
                guardrailIdentifier=guardrail_id,
                guardrailVersion=guardrail_version,
                source="INPUT",
                content=[{"text": {"text": message.strip()}}],
            )

        response = await asyncio.to_thread(_call_apply_guardrail)
        action = response.get("action")
        if action == "BLOCKED":
            logger.warning(
                "[BEDROCK_GUARDRAIL] Prompt blocked by guardrail %s (action=%s, assessments=%s)",
                guardrail_id,
                action,
                response.get("assessments"),
            )
            # Guardrail 콘솔에 정의된 커스텀 차단 문구가 있으면 우선 활용, 없으면 페르소나 문구
            outputs = response.get("outputs", [])
            if outputs and isinstance(outputs, list) and isinstance(outputs[0], dict):
                raw_text = outputs[0].get("text")
                if isinstance(raw_text, str) and raw_text.strip():
                    return str(raw_text.strip())
            return get_guardrail_blocked_response(librarian_id)

        return None
    except Exception as exc:
        logger.warning(
            "[BEDROCK_GUARDRAIL] Failed to evaluate guardrail (graceful fail-open): %s",
            exc,
        )
        return None
