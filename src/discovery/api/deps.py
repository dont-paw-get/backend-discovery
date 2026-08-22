"""FastAPI 의존성 주입 지점. 테스트에서 이 함수들을 오버라이드해 실제 인프라를 대체한다."""

from datetime import UTC, datetime

from fastapi import Request

from discovery.core.config import get_settings
from discovery.infrastructure.cache.chat_session_store import ChatSessionStore


def get_now() -> datetime:
    """현재 시각. `datetime.now()` 직접 호출 대신 이 의존성을 통해 주입받는다.

    AGENTS.md 테스트 원칙: 제어 불가능한 값(현재 시각)은 DI로 받아 결정론적으로 테스트한다.
    """
    return datetime.now(UTC)


def get_chat_session_store(request: Request) -> ChatSessionStore:
    """app.state.redis(lifespan에서 생성)를 사용하는 대화 세션 스토어."""
    settings = get_settings()
    return ChatSessionStore(
        request.app.state.redis,
        max_turns=settings.chat_history_max_turns,
        ttl_seconds=settings.chat_session_ttl_seconds,
    )
