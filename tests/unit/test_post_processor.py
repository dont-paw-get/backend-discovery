"""truncate_books_by_count 순수 함수 단위 테스트.

다양한 마크다운 포맷(서두 유무, 권수 초과/미달/일치, 헤딩 누락, 음수 count)에 대해
결과 마크다운의 도서 블록 수와 서두 보존 동작을 결과 검증 우선 원칙으로 검증한다.
"""

from discovery.domain.librarian.post_processor import (
    parse_recommended_books_from_markdown,
    sanitize_html_tags,
    strip_isbn_comments,
    truncate_books_by_count,
)

SAMPLE_THREE_BOOKS = """요청하신 따뜻한 힐링 소설 3권을 추천해 드립니다.

### 📖 불편한 편의점
- **저자**: 김호연 (268쪽)
- **추천 이유**: 골목길 작은 편의점에서 펼쳐지는 이웃들의 따뜻한 이야기입니다.

### 📖 달러구트 꿈 백화점
- **저자**: 이미예 (300쪽)
- **추천 이유**: 잠들어야만 입장할 수 있는 신비로운 백화점에서 만나는 위로의 이야기입니다.

### 📖 어서 오세요, 휴남동 서점입니다
- **저자**: 황보름 (364쪽)
- **추천 이유**: 동네 작은 서점에서 책과 사람을 통해 상처를 치유하는 힐링 소설입니다."""

SAMPLE_NO_PREAMBLE_THREE_BOOKS = """### 📖 불편한 편의점
- **저자**: 김호연
- **추천 이유**: 골목길 이야기.

### 📖 달러구트 꿈 백화점
- **저자**: 이미예
- **추천 이유**: 꿈 백화점 이야기.

### 📖 어서 오세요, 휴남동 서점입니다
- **저자**: 황보름
- **추천 이유**: 서점 이야기."""


def test_truncate_three_books_to_one() -> None:
    # 3권 중 count=1 요청 시 첫 번째 도서만 남고 서두가 보존되어야 한다.
    result = truncate_books_by_count(SAMPLE_THREE_BOOKS, count=1)

    assert "요청하신 따뜻한 힐링 소설 3권을 추천해 드립니다." in result
    assert "### 📖 불편한 편의점" in result
    assert "### 📖 달러구트 꿈 백화점" not in result
    assert "### 📖 어서 오세요, 휴남동 서점입니다" not in result
    assert result.count("### 📖") == 1


def test_truncate_three_books_to_two() -> None:
    # 3권 중 count=2 요청 시 상위 2권만 남고 3번째 도서는 잘려야 한다.
    result = truncate_books_by_count(SAMPLE_THREE_BOOKS, count=2)

    assert "요청하신 따뜻한 힐링 소설 3권을 추천해 드립니다." in result
    assert "### 📖 불편한 편의점" in result
    assert "### 📖 달러구트 꿈 백화점" in result
    assert "### 📖 어서 오세요, 휴남동 서점입니다" not in result
    assert result.count("### 📖") == 2


def test_truncate_three_books_with_count_three_or_more() -> None:
    # 3권 중 count=3 또는 count=5 요청 시 원본 전체가 무손실 보존되어야 한다.
    result_3 = truncate_books_by_count(SAMPLE_THREE_BOOKS, count=3)
    assert result_3 == SAMPLE_THREE_BOOKS
    assert result_3.count("### 📖") == 3

    result_5 = truncate_books_by_count(SAMPLE_THREE_BOOKS, count=5)
    assert result_5 == SAMPLE_THREE_BOOKS
    assert result_5.count("### 📖") == 3


def test_truncate_no_preamble_books() -> None:
    # 서두 없이 바로 ### 📖로 시작하는 경우에도 count=1 자르기가 정상 동작해야 한다.
    result = truncate_books_by_count(SAMPLE_NO_PREAMBLE_THREE_BOOKS, count=1)

    assert "### 📖 불편한 편의점" in result
    assert "### 📖 달러구트 꿈 백화점" not in result
    assert result.count("### 📖") == 1


def test_truncate_non_conforming_markdown() -> None:
    # ### 📖 헤딩이 없는 일반 텍스트는 원본 그대로 반환된다.
    plain_text = "안녕하세요! 책 추천을 도와드릴게요. 어떤 장르를 원하시나요?"
    result = truncate_books_by_count(plain_text, count=1)
    assert result == plain_text


def test_truncate_zero_or_negative_count() -> None:
    # count <= 0인 경우 원본 그대로 반환된다.
    result_zero = truncate_books_by_count(SAMPLE_THREE_BOOKS, count=0)
    assert result_zero == SAMPLE_THREE_BOOKS

    result_neg = truncate_books_by_count(SAMPLE_THREE_BOOKS, count=-1)
    assert result_neg == SAMPLE_THREE_BOOKS


def test_truncate_empty_markdown() -> None:
    # 빈 문자열 처리
    assert truncate_books_by_count("", count=1) == ""
    assert truncate_books_by_count("   ", count=1) == "   "



# ---------------------------------------------------------------------------
# parse_recommended_books_from_markdown / sanitize_html_tags
# (CLIAR-229: 저자/쪽수 구조화 분리 및 HTML 태그 노출 방어)
# ---------------------------------------------------------------------------

SAMPLE_TWO_BOOKS_WITH_PAGE_COUNT = """세계 경영학 필독서를 추천해드릴게요.

### 📖 세계 경영학 필독서 50
- **저자**: 톰 버틀러 보던 (548쪽)
- **추천 이유**: 경영학의 핵심 고전들을 압축적으로 정리한 명저입니다.

### 📖 좋은 전략 나쁜 전략
- **저자**: 리처드 루멜트
- **추천 이유**: 전략의 본질을 꿰뚫는 실무 지침서입니다."""


def test_parse_recommended_books_separates_author_and_page_count() -> None:
    # 저자 필드에 쪽수가 섞여 들어가지 않고 별도 정수 필드로 분리되어야 한다.
    books = parse_recommended_books_from_markdown(SAMPLE_TWO_BOOKS_WITH_PAGE_COUNT)

    assert len(books) == 2
    assert books[0]["title"] == "세계 경영학 필독서 50"
    assert books[0]["author"] == "톰 버틀러 보던"
    assert "쪽" not in (books[0]["author"] or "")
    assert books[0]["page_count"] == 548
    assert books[0]["reason"] == "경영학의 핵심 고전들을 압축적으로 정리한 명저입니다."


def test_parse_recommended_books_handles_missing_page_count() -> None:
    # 쪽수가 없는 도서는 page_count가 None이어야 하고 저자명은 그대로 보존된다.
    books = parse_recommended_books_from_markdown(SAMPLE_TWO_BOOKS_WITH_PAGE_COUNT)

    assert books[1]["title"] == "좋은 전략 나쁜 전략"
    assert books[1]["author"] == "리처드 루멜트"
    assert books[1]["page_count"] is None


def test_parse_recommended_books_returns_empty_list_when_no_book_headers() -> None:
    # ### 📖 헤딩이 없는 일반 텍스트는 빈 리스트를 반환한다.
    plain_text = "안녕하세요! 오늘 날씨가 좋네요."
    assert parse_recommended_books_from_markdown(plain_text) == []
    assert parse_recommended_books_from_markdown("") == []


def test_parse_recommended_books_skips_block_without_title() -> None:
    # 헤딩은 있지만 제목이 비어 있는 비정형 블록은 건너뛴다.
    malformed = "### 📖 \n- **저자**: 홍길동\n"
    assert parse_recommended_books_from_markdown(malformed) == []


SAMPLE_BOOK_WITH_ISBN = """### 📖 어린 왕자
- **저자**: 앙투안 드 생텍쥐페리 (약 160쪽)
- **추천 이유**: 어른을 위한 동화로도 사랑받는 고전입니다.
<!-- isbn: 9788932917245 -->"""

SAMPLE_BOOK_WITHOUT_ISBN = """### 📖 넛지: 파이널 에디션
- **저자**: 리처드 탈러, 캐스 선스타인
- **추천 이유**: 행동경제학의 고전입니다."""


def test_parse_recommended_books_extracts_isbn_comment() -> None:
    # <!-- isbn: ... --> 내부 주석에서 ISBN을 정확히 추출해야 한다.
    books = parse_recommended_books_from_markdown(SAMPLE_BOOK_WITH_ISBN)
    assert len(books) == 1
    assert books[0]["isbn"] == "9788932917245"


def test_parse_recommended_books_isbn_none_when_comment_missing() -> None:
    # ISBN 주석이 없으면 isbn 필드는 None이어야 한다.
    books = parse_recommended_books_from_markdown(SAMPLE_BOOK_WITHOUT_ISBN)
    assert len(books) == 1
    assert books[0]["isbn"] is None


def test_parse_recommended_books_ignores_invalid_isbn_length() -> None:
    # 10자리/13자리가 아닌 숫자는 ISBN으로 인정하지 않는다.
    malformed_isbn = (
        "### 📖 테스트 도서\n- **저자**: 홍길동\n- **추천 이유**: 테스트\n"
        "<!-- isbn: 12345 -->"
    )
    books = parse_recommended_books_from_markdown(malformed_isbn)
    assert books[0]["isbn"] is None


def test_strip_isbn_comments_removes_comment_line() -> None:
    # 최종 사용자 응답에는 ISBN 주석이 절대 남아있으면 안 된다.
    result = strip_isbn_comments(SAMPLE_BOOK_WITH_ISBN)
    assert "<!-- isbn:" not in result
    assert "### 📖 어린 왕자" in result


def test_strip_isbn_comments_noop_when_no_comment() -> None:
    # 주석이 없는 텍스트는 그대로 반환된다.
    result = strip_isbn_comments(SAMPLE_BOOK_WITHOUT_ISBN)
    assert result == SAMPLE_BOOK_WITHOUT_ISBN


def test_strip_isbn_comments_handles_empty_string() -> None:
    assert strip_isbn_comments("") == ""


def test_sanitize_html_tags_removes_br_variants() -> None:
    # <br>, <br/>, <br />, 대소문자 변형까지 모두 개행으로 정규화되어야 한다.
    raw = "안녕하세요<br>반갑습니다<br/>또 만나요<BR /><Br>끝."
    result = sanitize_html_tags(raw)

    assert "<br" not in result.lower()
    assert "안녕하세요" in result
    assert "반갑습니다" in result


def test_sanitize_html_tags_noop_when_no_html() -> None:
    # HTML 태그가 없는 텍스트는 그대로 반환된다.
    clean_text = "일반적인 마크다운 텍스트입니다.\n\n### 📖 도서 제목"
    assert sanitize_html_tags(clean_text) == clean_text
    assert sanitize_html_tags("") == ""
