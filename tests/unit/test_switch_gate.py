"""사서 전환 결정론적 게이트(switch_gate) 단위 테스트.

CLIAR-305 후속(2026-09-06): "블루/슈빌로 바꿔줘"처럼 상대 사서로의 명시적 전환 요청을
LLM 도구 호출 없이 결정론적으로 감지하여 switch_to를 채우는 게이트를 검증한다.
"""

from discovery.domain.orchestrator.switch_gate import (
    detect_switch_request,
    evaluate_switch_gate,
)


class TestDetectSwitchRequest:
    """상대 사서로의 명시적 전환 요청 감지 로직."""

    def test_cat_active_requesting_stork_returns_stork(self) -> None:
        assert detect_switch_request("슈빌 사서로 바꿔줘", "cat") == "stork"
        assert detect_switch_request("황새 사서 불러줘", "cat") == "stork"

    def test_stork_active_requesting_cat_returns_cat(self) -> None:
        assert detect_switch_request("블루 사서로 바꿔줘", "stork") == "cat"
        assert detect_switch_request("고양이 사서랑 얘기할래", "stork") == "cat"

    def test_none_librarian_defaults_to_cat(self) -> None:
        # librarian_id None이면 cat 활성으로 취급 → stork 호출 시 전환
        assert detect_switch_request("슈빌로 바꿔줘", None) == "stork"

    def test_calling_self_is_not_a_switch(self) -> None:
        # cat 활성 상태에서 블루(자기 자신)를 불러도 전환이 아님
        assert detect_switch_request("블루야 안녕", "cat") is None
        # stork 활성 상태에서 슈빌(자기 자신)을 불러도 전환이 아님
        assert detect_switch_request("슈빌 안녕", "stork") is None

    def test_ordinary_message_is_not_a_switch(self) -> None:
        assert detect_switch_request("재밌는 소설 추천해줘", "cat") is None
        assert detect_switch_request("오늘 날씨 어때?", "stork") is None

    def test_domain_topic_without_call_is_not_a_switch(self) -> None:
        # 비즈니스 주제 언급(도메인)만으로는 전환 게이트가 발동하지 않는다
        # (도메인 기반 switch는 LLM/consult 흐름에 맡긴다).
        assert detect_switch_request("경영 전략에 대해 알려줘", "cat") is None


class TestEvaluateSwitchGate:
    """게이트가 결정론적 LibrarianResponse(switch_to 포함)를 반환하는지."""

    def test_switch_request_returns_response_with_switch_to(self) -> None:
        res = evaluate_switch_gate("슈빌 사서로 바꿔줘", "cat")
        assert res is not None
        assert res.switch_to is not None
        assert res.switch_to.id == "stork"
        assert res.message  # 안내 문구 존재

    def test_reverse_switch_request(self) -> None:
        res = evaluate_switch_gate("블루 사서로 바꿔줘", "stork")
        assert res is not None
        assert res.switch_to is not None
        assert res.switch_to.id == "cat"

    def test_non_switch_returns_none(self) -> None:
        assert evaluate_switch_gate("추리 소설 추천해줘", "cat") is None

    def test_calling_self_returns_none(self) -> None:
        assert evaluate_switch_gate("블루야 반가워", "cat") is None
