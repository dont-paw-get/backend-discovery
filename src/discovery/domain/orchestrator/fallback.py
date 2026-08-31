"""Bedrock LLM 장애, 권한 예외, 타임아웃 발생 시
사서 페르소나별 Graceful Fallback 메시지 유틸리티.
"""

CAT_FALLBACK_MESSAGE = (
    "냥냥... 서재 책장을 정리하던 중에 통신 연결이 잠시 끊겼다냥 🐾 잠시 후에 다시 이야기해달라냥!"
)

STORK_FALLBACK_MESSAGE = (
    "두둥! 서재 사서실 통신에 일시적인 장애가 발생했습니다 🪶 잠시 후 다시 말씀해 주십시오."
)


def get_llm_fallback_message(librarian_id: str | None = None) -> str:
    """활성 사서 ID(cat ⇄ stork)에 맞춘 친절한 에러 Fallback 안내 메시지를 반환한다."""
    if librarian_id == "stork":
        return STORK_FALLBACK_MESSAGE
    return CAT_FALLBACK_MESSAGE
