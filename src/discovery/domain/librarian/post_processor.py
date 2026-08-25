"""도서 추천 에이전트의 응답 텍스트를 결정론적으로 후처리하는 순수 함수 모듈."""

import re


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
