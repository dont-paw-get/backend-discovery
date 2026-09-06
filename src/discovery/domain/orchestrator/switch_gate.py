"""결정론적 사서 전환 게이트(Switch Gate).

사용자가 "블루로 바꿔줘", "슈빌 불러줘"처럼 **상대 사서로의 전환을 명시적으로**
요청하는 경우, LLM/도구 호출을 거치지 않고 결정론적으로 전환 판단을 생성한다.

배경(2026-09-06, dev 라이브 실측): 기존에는 이 전환 판단을 오케스트레이터 프롬프트가
`consult_librarian` 도구를 호출하도록 유도하는 방식(비결정적)에 의존했다. Haiku 4.5가
도구 호출을 확률적으로 건너뛰면 `switch_to`가 채워지지 않고 "전환 기능이 없다"는
거절을 지어내는 버그가 재현됐다(6회 중 정상 2 / 거절 1 / 빈응답 3). 이 게이트는
`safety_gate`/`input_gate`와 동일한 패턴으로 LLM 앞단에서 전환 요청을 결정론적으로
가로채 이미 검증된 `evaluate_local_persona_response`의 전환 판단을 그대로 사용한다.

전환은 **상대 사서**로만 감지한다. 현재 활성 사서 자신을 부르는 경우(예: cat 활성
상태에서 "블루야")는 전환이 아니므로 게이트가 발동하지 않고 정상 대화 흐름으로 넘긴다.
"""

from discovery.domain.orchestrator.librarian_response import LibrarianResponse
from discovery.domain.orchestrator.tools.librarian_tool import (
    CAT_CALL_KEYWORDS,
    STORK_CALL_KEYWORDS,
    _is_calling_librarian,
    evaluate_local_persona_response,
)


def detect_switch_request(message: str, librarian_id: str | None) -> str | None:
    """상대 사서로의 명시적 전환 요청인지 판정하고, 전환 대상 사서 ID를 반환한다.

    Args:
        message: 사용자 메시지.
        librarian_id: 현재 활성 사서 ID('cat' 또는 'stork'). None이면 'cat'로 취급.

    Returns:
        전환 대상 사서 ID('cat' 또는 'stork'). 전환 요청이 아니면 None.
        현재 활성 사서 자신을 부르는 경우도 전환이 아니므로 None.
    """
    current = (librarian_id or "cat").strip().lower()
    msg_lower = message.lower()

    if current == "cat":
        # cat 활성 상태에서 stork(상대)를 명시적으로 호출하면 전환
        if _is_calling_librarian(msg_lower, STORK_CALL_KEYWORDS):
            return "stork"
        return None

    # stork 활성 상태에서 cat(상대)를 명시적으로 호출하면 전환
    if _is_calling_librarian(msg_lower, CAT_CALL_KEYWORDS):
        return "cat"
    return None


def evaluate_switch_gate(
    message: str,
    librarian_id: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> LibrarianResponse | None:
    """명시적 사서 전환 요청 감지 시 결정론적 전환 응답을 반환하고, 아니면 None.

    반환되는 `LibrarianResponse`는 `evaluate_local_persona_response`가 생성한 것으로,
    `switch_to`가 반드시 채워져 있다(전환 대상 사서). 호출부(OrchestratorService)는
    이 응답의 message/signals/switch_to를 그대로 클라이언트에 전달하고 세션 메타의
    활성 사서를 갱신한다.
    """
    if detect_switch_request(message, librarian_id) is None:
        return None

    response = evaluate_local_persona_response(
        message=message,
        librarian_id=librarian_id,
        latitude=latitude,
        longitude=longitude,
    )
    # 방어: 로컬 엔진이 전환을 못 잡은 경우(감지 로직 불일치)는 게이트 미발동으로 처리해
    # LLM 정상 흐름에 맡긴다(switch_to 없는 응답을 강제 반환하지 않음).
    if response.switch_to is None:
        return None
    return response
