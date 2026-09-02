import re
from typing import Any, TypedDict


class RecommendedBookFields(TypedDict):
    """`### 📖` 마크다운 도서 블록에서 파싱한 구조화 필드."""

    title: str
    author: str | None
    page_count: int | None
    reason: str | None


_BOOK_BLOCK_PATTERN = re.compile(r"(?=(?:^|\n)### 📖)")
_TITLE_LINE_PATTERN = re.compile(r"^### 📖\s*(.*)$")
# "- **저자**: {저자명} ({페이지수}쪽)" 또는 "- **저자**: {저자명}" (쪽수 없음) 모두 매칭.
# 저자명에는 최소한의 탐욕 배제(non-greedy)를 적용해 뒤의 "(N쪽)"이 저자명에 섞이지 않게 한다.
_AUTHOR_LINE_PATTERN = re.compile(
    r"-\s*\*\*저자\*\*:\s*(.+?)(?:\s*\((\d+)\s*쪽\))?\s*$", re.MULTILINE
)
_REASON_LINE_PATTERN = re.compile(r"-\s*\*\*추천\s*이유\*\*:\s*(.+?)\s*$", re.MULTILINE)


def parse_recommended_books_from_markdown(markdown: str) -> list[RecommendedBookFields]:
    """추천 에이전트/오케스트레이터가 생성한 `### 📖` 마크다운 블록을 구조화 필드로 파싱한다.

    - 저자와 쪽수를 분리한다: `- **저자**: {name} ({page}쪽)` → `author="{name}"`,
      `page_count={page}`. 쪽수가 없으면 `page_count=None`.
    - 파싱 실패(필수 필드 누락 등)한 블록은 결과에서 건너뛴다(원본 마크다운 텍스트는
      항상 `message` 필드로 별도 보존되므로 파싱 실패가 사용자 응답 자체를 깨뜨리지 않는다).

    Args:
        markdown: `### 📖` 헤더를 포함할 수 있는 마크다운 텍스트(오케스트레이터 최종 응답 등).

    Returns:
        파싱된 도서 필드 목록. 도서 블록이 없으면 빈 리스트.
    """
    if not markdown or "### 📖" not in markdown:
        return []

    blocks = [b.strip() for b in _BOOK_BLOCK_PATTERN.split(markdown) if b.strip()]
    books: list[RecommendedBookFields] = []
    for block in blocks:
        if not block.startswith("### 📖"):
            continue
        first_line = block.splitlines()[0]
        title_match = _TITLE_LINE_PATTERN.match(first_line)
        if not title_match:
            continue
        title = title_match.group(1).strip()
        if not title:
            continue

        author: str | None = None
        page_count: int | None = None
        author_match = _AUTHOR_LINE_PATTERN.search(block)
        if author_match:
            author = author_match.group(1).strip() or None
            if author_match.group(2):
                page_count = int(author_match.group(2))

        reason: str | None = None
        reason_match = _REASON_LINE_PATTERN.search(block)
        if reason_match:
            reason = reason_match.group(1).strip() or None

        books.append(
            RecommendedBookFields(
                title=title, author=author, page_count=page_count, reason=reason
            )
        )
    return books


_HTML_TAG_PATTERN = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)


def sanitize_html_tags(text: str) -> str:
    """LLM 응답에 실수로 섞여 나올 수 있는 raw HTML 태그를 마크다운 개행으로 정규화한다.

    현재는 `<br>`, `<br/>`, `<br />`(대소문자 무관) 패턴만 개행(`\\n`)으로 치환한다.
    백엔드 자체는 `<br>`를 생성하지 않지만(코드 검색으로 확인됨), LLM 자유 생성 과정에서
    HTML 태그를 흉내내어 출력할 가능성에 대한 출력단 방어 장치다.
    """
    if not text:
        return text
    return _HTML_TAG_PATTERN.sub("\n", text)


def extract_text_from_message(message: Any) -> str:
    """AgentResult.message에서 텍스트 콘텐츠를 추출한다."""
    if isinstance(message, dict):
        content = message.get("content", [])
        if isinstance(content, list):
            return "".join(
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and "text" in b and isinstance(b["text"], str)
            )
    return ""



def truncate_books_by_count(markdown: str, count: int) -> str:
    """마크다운 응답에서 `### 📖` 헤더 단위로 도서 블록을 파싱하여 지정된 `count`개만 보존한다.

    - 헤딩 `### 📖` 이전의 서두 멘트(Preamble)는 항상 보존된다.
    - 추출된 도서 블록 수가 `count` 이하이거나, `count <= 0`,
      또는 헤딩이 없는 경우 원본을 무손실 반환한다.
    - 추출된 도서 블록 수가 `count`보다 많을 경우 상위 `count`개 블록만 결합하여 반환한다.

    Args:
        markdown: 추천 에이전트가 생성한 마크다운 원본 텍스트.
        count: 보존할 최대 도서 권수.

    Returns:
        지정된 권수로 잘라내고 서두가 보존된 마크다운 문자열.
    """
    if count <= 0 or not markdown or not markdown.strip():
        return markdown

    # `### 📖` 패턴 매칭 (줄 시작 또는 공백 뒤의 ### 📖)
    pattern = re.compile(r"(?:^|\n)(?=### 📖)")
    parts = pattern.split(markdown)

    # 헤딩이 전혀 없거나 첫 부분만 있는 경우
    if len(parts) <= 1:
        # 혹시 맨 처음에 바로 ### 📖로 시작하여 split된 경우 확인
        if markdown.strip().startswith("### 📖"):
            book_pattern = re.compile(r"(?=(?:^|\n)### 📖)")
            blocks = [b for b in book_pattern.split(markdown) if b.strip()]
            if len(blocks) <= count:
                return markdown
            return "\n\n".join(b.strip() for b in blocks[:count])
        return markdown

    # parts[0]: 첫 번째 `### 📖` 이전의 서두(Preamble) (없으면 빈 문자열)
    # parts[1:]: 각 도서 블록 (`### 📖 ...`)
    preamble = parts[0].strip()
    book_blocks = [p.strip() for p in parts[1:] if p.strip()]

    # 도서 블록 수가 요구 권수 이하이면 원본 그대로 반환
    if len(book_blocks) <= count:
        return markdown

    # 요구 권수만큼만 선택
    selected_books = book_blocks[:count]

    # 서두가 있으면 서두 + 도서 블록 결합, 없으면 도서 블록만 결합
    if preamble:
        return f"{preamble}\n\n" + "\n\n".join(selected_books)
    return "\n\n".join(selected_books)
