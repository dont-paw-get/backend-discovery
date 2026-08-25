"""도서 표준 장르 분류기 도메인 로직 및 프롬프트 정의."""

import json
import logging
import re
from typing import Any

from discovery.api.schemas.genre import BookClassificationResponse, StandardGenre

logger = logging.getLogger(__name__)

GENRE_CLASSIFIER_SYSTEM_PROMPT = """당신은 도서 메타데이터를 분석하여
표준 장르로 정확하게 분류하는 전문 사서 AI입니다.
주어진 도서 제목(title), 저자(author), 원본 카테고리(raw_category) 정보를 종합 분석하여,
반드시 아래 정의된 16개 표준 장르 Enum(genre_type) 중 가장 적합한 1개를 선택하세요.


[16개 표준 장르 Enum 목록]
1. SCIENCE_FICTION: SF, 공상과학, 사이버펑크, 스페이스 오페라 등
2. FANTASY: 판타지, 무협, 다크판타지, 어반판타지, 로맨스판타지 등
3. ROMANCE: 로맨스, 순정, 연애소설 등
4. MYSTERY_THRILLER: 추리, 미스터리, 스릴러, 서스펜스, 공포, 호러, 범죄소설 등
5. LITERARY_FICTION: 한국소설, 영미소설, 고전문학, 일반문학, 순수소설, 테마소설 등
6. ESSAY: 수필, 산문집, 그림에세이, 일상에세이, 여행에세이 등
7. POETRY_DRAMA: 시집, 희곡, 대본집, 시론 등
8. HUMANITIES: 철학, 심리학, 윤리학, 언어학, 신화/종교학(학술), 고전인문 등
9. HISTORY: 한국사, 세계사, 동양사, 서양사, 고고학, 역사인물/사건 등
10. BUSINESS_ECONOMICS: 경영학, 경제학, 마케팅/세일즈, 재테크, 주식/투자, 비즈니스 등
11. SELF_HELP: 성공/처세, 인간관계, 화술/협상, 시간관리, 습관, 리더십, 동기부여 등
12. SCIENCE: 자연과학, 수학, 물리학, 화학, 생명과학, 지구과학, 천문학, 교양과학 등
13. ARTS: 미술, 음악, 디자인, 사진, 건축, 영화/드라마/공연, 만화(기법), 공예 등
14. RELIGION: 기독교, 불교, 가톨릭, 이슬람교, 종교일반, 신앙/명상 등
15. COMPUTER_IT: 프로그래밍, 개발, IT교양, 컴퓨터공학, 인공지능/데이터, 네트워크/보안 등
16. NONE: 위 장르에 해당하지 않거나 도서 정보가 부족하여 식별 불가능한 경우

[분류 원칙]
1. raw_category(알라딘/OCR 원본 카테고리)에 명확한 분류 단서가 있다면 최우선으로 고려하세요.
2. raw_category가 모호하거나 없더라도, 제목(title)과 저자(author)의 특성을 파악하여
   가장 가까운 표준 장르 Enum을 도출하세요.
3. 소설 중에서 세부 장르(SF, 판타지, 로맨스, 미스터리/스릴러) 구분이 뚜렷하지 않은
   일반 문학이나 고전문학 등은 'LITERARY_FICTION'으로 분류하세요.
4. 어떤 범주에도 명확히 부합하지 않거나 도서 정보가 너무 부족한 경우 'NONE'으로 분류하세요.

[출력 형식]
반드시 다른 설명이나 마크다운 코드블록 없이, 오직 아래의 유효한 JSON 형식 단 1개만 출력하세요:
{"genre": "<16개 표준 장르 Enum 영문 대문자>", "confidence": <0.0 ~ 1.0 실수>}
"""


def build_classification_prompt(title: str, author: str = "", raw_category: str = "") -> str:
    """도서 장르 분류를 위한 LLM 사용자 프롬프트를 생성한다."""
    return (
        f"도서 정보:\n"
        f"- 제목: {title}\n"
        f"- 저자: {author if author else '정보 없음'}\n"
        f"- 원본 카테고리: {raw_category if raw_category else '정보 없음'}\n\n"
        f"위 도서를 분석하여 16개 표준 장르 Enum 중 가장 적합한 1개와 신뢰도를 JSON으로 반환하세요."
    )


def match_standard_genre(genre_str: str) -> StandardGenre | None:
    """문자열을 StandardGenre Enum에 매핑한다."""
    cleaned = genre_str.strip().strip("\"'").upper()

    # 1. Enum value 직접 매칭
    for g in StandardGenre:
        if g.value == cleaned:
            return g

    # 2. Enum name 매칭
    try:
        return StandardGenre[cleaned]
    except KeyError:
        pass

    # 3. 정확한 별칭/동의어 매핑 (대소문자 무시)
    exact_alias_map: dict[str, StandardGenre] = {
        # SCIENCE_FICTION
        "SCIENCE_FICTION": StandardGenre.SCIENCE_FICTION,
        "SCIENCE FICTION": StandardGenre.SCIENCE_FICTION,
        "SF": StandardGenre.SCIENCE_FICTION,
        "공상과학": StandardGenre.SCIENCE_FICTION,
        # FANTASY
        "FANTASY": StandardGenre.FANTASY,
        "판타지": StandardGenre.FANTASY,
        "무협": StandardGenre.FANTASY,
        # ROMANCE
        "ROMANCE": StandardGenre.ROMANCE,
        "로맨스": StandardGenre.ROMANCE,
        "순정": StandardGenre.ROMANCE,
        "연애소설": StandardGenre.ROMANCE,
        # MYSTERY_THRILLER
        "MYSTERY_THRILLER": StandardGenre.MYSTERY_THRILLER,
        "MYSTERY": StandardGenre.MYSTERY_THRILLER,
        "THRILLER": StandardGenre.MYSTERY_THRILLER,
        "미스터리/스릴러": StandardGenre.MYSTERY_THRILLER,
        "미스터리": StandardGenre.MYSTERY_THRILLER,
        "스릴러": StandardGenre.MYSTERY_THRILLER,
        "추리": StandardGenre.MYSTERY_THRILLER,
        "추리소설": StandardGenre.MYSTERY_THRILLER,
        "호러": StandardGenre.MYSTERY_THRILLER,
        "공포": StandardGenre.MYSTERY_THRILLER,
        # LITERARY_FICTION
        "LITERARY_FICTION": StandardGenre.LITERARY_FICTION,
        "LITERARY FICTION": StandardGenre.LITERARY_FICTION,
        "GENERAL_FICTION": StandardGenre.LITERARY_FICTION,
        "순수소설/일반소설": StandardGenre.LITERARY_FICTION,
        "순수소설": StandardGenre.LITERARY_FICTION,
        "일반소설": StandardGenre.LITERARY_FICTION,
        "한국소설": StandardGenre.LITERARY_FICTION,
        "영미소설": StandardGenre.LITERARY_FICTION,
        "세계소설": StandardGenre.LITERARY_FICTION,
        "고전문학": StandardGenre.LITERARY_FICTION,
        "소설": StandardGenre.LITERARY_FICTION,
        "문학": StandardGenre.LITERARY_FICTION,
        # ESSAY
        "ESSAY": StandardGenre.ESSAY,
        "에세이": StandardGenre.ESSAY,
        "수필": StandardGenre.ESSAY,
        "산문집": StandardGenre.ESSAY,
        "산문": StandardGenre.ESSAY,
        # POETRY_DRAMA
        "POETRY_DRAMA": StandardGenre.POETRY_DRAMA,
        "POETRY": StandardGenre.POETRY_DRAMA,
        "DRAMA": StandardGenre.POETRY_DRAMA,
        "시/희곡": StandardGenre.POETRY_DRAMA,
        "시": StandardGenre.POETRY_DRAMA,
        "희곡": StandardGenre.POETRY_DRAMA,
        "대본집": StandardGenre.POETRY_DRAMA,
        # HUMANITIES
        "HUMANITIES": StandardGenre.HUMANITIES,
        "인문학": StandardGenre.HUMANITIES,
        "인문": StandardGenre.HUMANITIES,
        "철학": StandardGenre.HUMANITIES,
        "심리학": StandardGenre.HUMANITIES,
        # HISTORY
        "HISTORY": StandardGenre.HISTORY,
        "역사": StandardGenre.HISTORY,
        "한국사": StandardGenre.HISTORY,
        "세계사": StandardGenre.HISTORY,
        # BUSINESS_ECONOMICS
        "BUSINESS_ECONOMICS": StandardGenre.BUSINESS_ECONOMICS,
        "BUSINESS_ECONOMY": StandardGenre.BUSINESS_ECONOMICS,
        "경제/경영": StandardGenre.BUSINESS_ECONOMICS,
        "경제": StandardGenre.BUSINESS_ECONOMICS,
        "경영": StandardGenre.BUSINESS_ECONOMICS,
        "경영학": StandardGenre.BUSINESS_ECONOMICS,
        "재테크": StandardGenre.BUSINESS_ECONOMICS,
        "투자": StandardGenre.BUSINESS_ECONOMICS,
        "비즈니스": StandardGenre.BUSINESS_ECONOMICS,
        # SELF_HELP
        "SELF_HELP": StandardGenre.SELF_HELP,
        "자기계발": StandardGenre.SELF_HELP,
        "자기관리": StandardGenre.SELF_HELP,
        "성공": StandardGenre.SELF_HELP,
        # SCIENCE
        "SCIENCE": StandardGenre.SCIENCE,
        "과학": StandardGenre.SCIENCE,
        "자연과학": StandardGenre.SCIENCE,
        "교양과학": StandardGenre.SCIENCE,
        # ARTS
        "ARTS": StandardGenre.ARTS,
        "ART": StandardGenre.ARTS,
        "예술": StandardGenre.ARTS,
        "미술": StandardGenre.ARTS,
        "음악": StandardGenre.ARTS,
        "디자인": StandardGenre.ARTS,
        # RELIGION
        "RELIGION": StandardGenre.RELIGION,
        "종교": StandardGenre.RELIGION,
        "기독교": StandardGenre.RELIGION,
        "불교": StandardGenre.RELIGION,
        "가톨릭": StandardGenre.RELIGION,
        # COMPUTER_IT
        "COMPUTER_IT": StandardGenre.COMPUTER_IT,
        "IT_COMPUTER": StandardGenre.COMPUTER_IT,
        "컴퓨터/IT": StandardGenre.COMPUTER_IT,
        "컴퓨터": StandardGenre.COMPUTER_IT,
        "IT": StandardGenre.COMPUTER_IT,
        "프로그래밍": StandardGenre.COMPUTER_IT,
        "소프트웨어": StandardGenre.COMPUTER_IT,
        "개발": StandardGenre.COMPUTER_IT,
        # NONE
        "NONE": StandardGenre.NONE,
        "기타": StandardGenre.NONE,
        "ETC": StandardGenre.NONE,
    }

    if cleaned in exact_alias_map:
        return exact_alias_map[cleaned]

    raw_clean = genre_str.strip().strip("\"'")
    if raw_clean in exact_alias_map:
        return exact_alias_map[raw_clean]

    # 4. 문자열 내 키워드 포함 검사 (긴 키워드 우선)
    sorted_keywords = sorted(exact_alias_map.keys(), key=len, reverse=True)
    for kw in sorted_keywords:
        if len(kw) >= 2 and (kw in raw_clean or kw.upper() in cleaned):
            return exact_alias_map[kw]

    return None


def parse_classification_response(raw_text: str) -> BookClassificationResponse:
    """LLM 출력 텍스트에서 JSON 및 StandardGenre를 추출하여 응답 모델로 파싱한다."""
    if not raw_text or not raw_text.strip():
        logger.warning("장르 분류 LLM 응답이 비어 있어 'NONE'으로 대체합니다.")
        return BookClassificationResponse(genre=StandardGenre.NONE, confidence=0.0)

    # 1. JSON 블록 정규식 탐색
    cleaned_text = raw_text.strip()
    # 마크다운 코드블록 제거
    if "```" in cleaned_text:
        cleaned_text = re.sub(r"```json\s*", "", cleaned_text)
        cleaned_text = re.sub(r"```", "", cleaned_text).strip()

    json_match = re.search(r"\{[^{}]*\}", cleaned_text, re.DOTALL)
    if json_match:
        try:
            data: dict[str, Any] = json.loads(json_match.group(0))
            raw_genre = str(data.get("genre", "")).strip()
            confidence_val = data.get("confidence", 1.0)
            try:
                confidence = float(confidence_val)
                confidence = max(0.0, min(1.0, confidence))
            except (ValueError, TypeError):
                confidence = 1.0

            mapped_genre = match_standard_genre(raw_genre)
            if mapped_genre is not None:
                return BookClassificationResponse(genre=mapped_genre, confidence=confidence)
            else:
                logger.warning(
                    "알 수 없는 장르 문자열('%s')로 인해 'NONE'으로 대체합니다. 원본: %s",
                    raw_genre,
                    raw_text,
                )
                return BookClassificationResponse(genre=StandardGenre.NONE, confidence=0.0)
        except json.JSONDecodeError as exc:
            logger.warning("JSON 파싱 에러(%s). 텍스트 직접 매칭을 시도합니다: %s", exc, raw_text)

    # 2. JSON 파싱 실패 시 텍스트 전체에서 장르 키워드 추출 시도
    mapped_genre = match_standard_genre(cleaned_text)
    if mapped_genre is not None:
        return BookClassificationResponse(genre=mapped_genre, confidence=0.7)

    logger.warning("장르 분류 파싱 실패. 'NONE'으로 fallback합니다: %s", raw_text)
    return BookClassificationResponse(genre=StandardGenre.NONE, confidence=0.0)
