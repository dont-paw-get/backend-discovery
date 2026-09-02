"""위기 및 자해 대응을 위한 결정론적 안전 게이트(Safety Gate).

사용자의 발화에서 자해, 자살, 극단적 위기 신호가 감지되면 LLM 추론을 거치지 않고
즉시 공감 및 공인 위기상담전화(109 등) 핫라인 안내를 결정론적으로 반환한다.
(CLIAR-208 원칙의 명시적 안전 예외)
"""

import re

CRISIS_KEYWORDS_PATTERN = re.compile(
    r"("
    r"자살|"
    r"자해|"
    r"죽고\s*싶|"
    r"살기\s*싫|"
    r"목숨을?\s*끊|"
    r"세상을?\s*떠나고\s*싶|"
    r"생을?\s*마감|"
    r"죽어버리고\s*싶|"
    r"뛰어내리고\s*싶|"
    r"사라지고\s*싶어?\s*죽겠"
    r")",
    re.IGNORECASE,
)

BOOK_TITLE_EXCLUSIONS_PATTERN = re.compile(
    r"(자살론|자살가게|자살\s*토끼|자살\s*클럽|자살의\s*이해)",
    re.IGNORECASE,
)

CAT_CRISIS_RESPONSE = (
    "많이 지치고 힘든 시간을 보내고 계신 것 같아 마음이 아프다냥... 🐾\n"
    "혼자서 이 힘든 짐을 다 짊어지려 하지 마시고, 따뜻한 도움을 받아보시는 건 어떨까냥?\n\n"
    "• 자살예방 상담전화: ☎ 109 (24시간 무료)\n"
    "• 정신건강 상담전화: ☎ 1577-0199 (24시간)\n"
    "• 생명의 전화: ☎ 1588-9191\n\n"
    "당신의 삶은 소중하다냥. 언제든 다시 이야기하러 와달라냥."
)

STORK_CRISIS_RESPONSE = (
    "많이 지치고 깊은 어둠 속에 계신 것 같아 깊은 위로의 말씀을 드립니다. 🪶\n"
    "결코 혼자가 아니며, 전문가의 따뜻한 손길과 도움이 언제나 열려 있습니다.\n\n"
    "• 자살예방 상담전화: ☎ 109 (24시간 무료)\n"
    "• 정신건강 상담전화: ☎ 1577-0199 (24시간)\n"
    "• 생명의 전화: ☎ 1588-9191\n\n"
    "소중한 당신을 늘 응원하며 기다리고 있겠습니다."
)


def is_crisis_message(message: str) -> bool:
    """발화 내용에 위기/자해/자살 관련 신호가 포함되어 있는지 판정한다."""
    if not message or not message.strip():
        return False

    cleaned = message.strip()
    if not CRISIS_KEYWORDS_PATTERN.search(cleaned):
        return False

    # 도서명 언급(예: '자살론 책 추천해줘')이며 직접적인 위기 발언이 없는 경우 제외
    if BOOK_TITLE_EXCLUSIONS_PATTERN.search(cleaned):
        direct_crisis = re.search(
            r"(죽고\s*싶|살기\s*싫|자해|목숨|세상을\s*떠나|생을\s*마감)", cleaned
        )
        if not direct_crisis:
            return False

    return True


def evaluate_safety_gate(message: str, librarian_id: str | None = None) -> str | None:
    """위기 상황 발화 시 페르소나별 핫라인 안내 메시지를 반환하고, 아니면 None을 반환한다."""
    if not is_crisis_message(message):
        return None

    if librarian_id == "stork":
        return STORK_CRISIS_RESPONSE
    return CAT_CRISIS_RESPONSE
