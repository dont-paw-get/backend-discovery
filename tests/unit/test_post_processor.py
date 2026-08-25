"""truncate_books_by_count 순수 함수 단위 테스트.

다양한 마크다운 포맷(서두 유무, 권수 초과/미달/일치, 헤딩 누락, 음수 count)에 대해
결과 마크다운의 도서 블록 수와 서두 보존 동작을 결과 검증 우선 원칙으로 검증한다.
"""

from discovery.domain.librarian.post_processor import truncate_books_by_count

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
