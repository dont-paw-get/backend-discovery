"""결정론적 비정상 입력 게이트(Input Gate).

자모 난타, 숫자만 입력, 이모지만 입력 등 무의미하거나 정형화된 비정상 입력을
LLM 추론 없이 즉각적으로 감지하여 페르소나별 자연스러운 되묻기/안내를 반환한다.
"""

import re
from enum import Enum


class InvalidInputType(str, Enum):
    JAMO_ONLY = "jamo_only"
    DIGITS_ONLY = "digits_only"
    EMOJI_ONLY = "emoji_only"


JAMO_PATTERN = re.compile(r"^[ㄱ-ㅎㅏ-ㅣ\s]+$")
DIGITS_PATTERN = re.compile(r"^[\d\s]+$")
EMOJI_ONLY_PATTERN = re.compile(
    r"^[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50\u200d\ufe0f\s]+$"
)

CAT_RESPONSES = {
    InvalidInputType.JAMO_ONLY: (
        "냥? 오타가 난 것 같다냥! 🐾 "
        "찾으시는 책 제목이나 관심 있는 분야를 알려주시면 정성껏 추천해 드리겠다냥!"
    ),
    InvalidInputType.DIGITS_ONLY: (
        "냥? 숫자만 적혀 있어 어떤 의미인지 잘 모르겠다냥! 🐾 "
        "도서 제목이나 추천받고 싶은 주제를 편하게 말씀해달라냥!"
    ),
    InvalidInputType.EMOJI_ONLY: (
        "냥? 귀여운 이모티콘이다냥! 🐾 "
        "어떤 책을 찾고 계신지 단어나 문장으로 말씀해 주시면 바로 찾아드리겠다냥!"
    ),
}

STORK_RESPONSES = {
    InvalidInputType.JAMO_ONLY: (
        "두둥! 말씀하신 내용을 파악하기 어렵습니다. 🪶 "
        "찾으시는 도서 제목이나 관심 분야를 알려주시면 정성껏 안내해 드리겠습니다."
    ),
    InvalidInputType.DIGITS_ONLY: (
        "두둥! 숫자만으로는 의도를 파악하기 어렵습니다. 🪶 "
        "도서 검색이나 추천에 필요한 키워드를 남겨주시면 최적의 도서를 선별해 드리겠습니다."
    ),
    InvalidInputType.EMOJI_ONLY: (
        "두둥! 남겨주신 이모티콘을 확인했습니다. 🪶 "
        "어떤 분야의 책을 찾으시는지 말씀해 주시면 알맞은 명저를 안내해 드리겠습니다."
    ),
}


def detect_invalid_input_type(message: str) -> InvalidInputType | None:
    """메시지가 자모/숫자/이모지만으로 구성된 비정상 입력인지 판정한다."""
    if not message or not message.strip():
        return None

    cleaned = message.strip()

    if JAMO_PATTERN.fullmatch(cleaned):
        return InvalidInputType.JAMO_ONLY

    if DIGITS_PATTERN.fullmatch(cleaned):
        return InvalidInputType.DIGITS_ONLY

    if EMOJI_ONLY_PATTERN.fullmatch(cleaned):
        return InvalidInputType.EMOJI_ONLY

    return None


def evaluate_input_gate(message: str, librarian_id: str | None = None) -> str | None:
    """비정상 입력 감지 시 페르소나별 안내 문구를 반환하고, 정상이면 None을 반환한다."""
    input_type = detect_invalid_input_type(message)
    if input_type is None:
        return None

    if librarian_id == "stork":
        return STORK_RESPONSES[input_type]
    return CAT_RESPONSES[input_type]
