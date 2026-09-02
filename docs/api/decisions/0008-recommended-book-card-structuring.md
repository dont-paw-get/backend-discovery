# ADR 0008: 도서 추천 카드 구조화 응답(recommended_books) 및 출력 HTML 태그 노출 방어

- **상태**: Accepted
- **날짜**: 2026-09-02
- **관련 티켓**: CLIAR-229
- **참여**: 오케스트레이터 및 프론트엔드 연동 도메인

---

## 1. 배경 및 문제점

1. **텍스트 파싱의 취약성으로 인한 "저자" 필드 오염**:
   - 도서 추천 응답(`### 📖`)은 CLIAR-196에서 서재 카드(`### 📚`, ADR 0005)에 도입한
     구조화 필드 패턴을 따르지 않고, 여전히 순수 마크다운 텍스트(`- **저자**: {name} ({page}쪽)`)로만
     제공되고 있었다.
   - 프론트엔드 "책 등록" 화면이 이 마크다운 줄 전체를 "저자" 입력란에 그대로 파싱하여,
     `톰 버틀러 보던 (548쪽)`처럼 쪽수가 저자명에 함께 들어가는 버그가 발생함.
2. **출력 텍스트에 raw HTML 태그(`<br>`)가 노출되는 사례 보고**:
   - 사용자 응답 화면에 `<br>` 문자열이 그대로 노출되는 경우가 확인됨.
   - 백엔드 소스 전체를 검색한 결과 `<br>`를 생성하는 지점이 전혀 없음을 확인했다(프론트
     마크다운 렌더러의 개행 처리 이슈로 추정, `.harness/DECISIONS.md` 2026-09-02 참고).
     다만 LLM 자유 생성 과정에서 HTML 태그를 흉내내어 출력할 가능성에 대한 출력단 방어가
     없었다.

---

## 2. 결정 사항

### 2.1 추천 카드 구조화 DTO (`RecommendedBookCard`) 및 `ChatResponse.recommended_books` 도입
- `api/schemas/chat.py`에 `LibraryBookCard`(ADR 0005)와 동일한 패턴의 응답 전용 스키마
  `RecommendedBookCard`를 정의한다:
  - `title: str`
  - `author: str | None` (쪽수 제외)
  - `page_count: int | None`
  - `reason: str | None`
- `ChatResponse`에 `recommended_books: list[RecommendedBookCard] | None = None` 필드를
  추가한다. 기존 `message`(마크다운 텍스트)는 하위 호환을 위해 그대로 유지하고,
  `recommended_books`는 병행 제공되는 추가 필드다.
- **동기(`chat`) 응답에만 제공한다.** 스트리밍(`stream_chat`) 경로는 최종 텍스트가
  완성되어야 파싱이 가능한데 HTTP 헤더는 스트림 시작 전에 이미 확정되므로(ADR 0007
  2.2절과 동일한 구조적 제약), 이번 범위에서는 스트리밍 경로에 구조화 필드를
  제공하지 않는다.

### 2.2 마크다운 → 구조화 필드 파서 (`parse_recommended_books_from_markdown`)
- `domain/librarian/post_processor.py`에 순수 함수 `parse_recommended_books_from_markdown`을
  신설한다. `### 📖` 블록을 분할하고, `- **저자**: {name} ({page}쪽)` 정규식으로
  저자명과 쪽수를 분리한다(쪽수가 없으면 `page_count=None`).
- 파싱에 실패한 블록(제목 누락 등)은 결과에서 건너뛴다. 원본 마크다운(`message`)은
  항상 그대로 보존되므로 파싱 실패가 사용자에게 보이는 답변 자체를 깨뜨리지 않는다.
- `OrchestratorService.chat`의 최종 응답 텍스트에서 이 파서를 호출하여 `recommended_books`를
  구성한다.

### 2.3 출력 HTML 태그 노출 방어 (`sanitize_html_tags`)
- `domain/librarian/post_processor.py`에 순수 함수 `sanitize_html_tags`를 신설하여
  `<br>`, `<br/>`, `<br />`(대소문자 무관) 패턴을 마크다운 개행(`\n`)으로 정규화한다.
- `chat`과 `stream_chat` 양쪽 모두, 세션 히스토리에 저장되는 최종 어시스턴트 응답
  텍스트에 적용한다.

---

## 3. 프론트엔드 연동 가이드

1. **도서 등록 화면 자동 입력**:
   - `response.recommended_books` 배열이 존재하는 경우, "저자"와 "총 페이지 수" 입력란은
     각각 `recommended_books[i].author`, `recommended_books[i].page_count`를 직접 사용하고,
     `message`의 마크다운 텍스트를 정규식으로 파싱하지 않는다.
   - `page_count`가 `null`인 경우 쪽수 확인이 불가능했던 도서이므로, 입력란을 빈 값으로
     두거나 사용자가 직접 입력하도록 안내한다.
2. **스트리밍(`stream=true`) 응답은 `recommended_books`를 제공하지 않는다**:
   - 도서 등록 자동 입력 플로우는 동기(`stream=false`) 요청을 사용해야 한다.
3. **`<br>` 등 HTML 태그 노출 문제**:
   - 백엔드가 생성하는 원인이 아님을 확인했다(코드 검색 결과 `<br>` 생성 지점 없음).
   - 마크다운 렌더러가 `\n`을 `<br>`로 변환하는 로직이 있다면, 변환 후 결과를 다시
     `dangerouslySetInnerHTML` 등으로 HTML 이스케이프 없이 렌더링하고 있는지, 혹은
     변환 자체가 불필요한 이중 처리인지 점검이 필요하다.
   - 백엔드도 방어적으로 알려진 HTML 태그 패턴을 sanitize하는 안전장치(2.3절)를
     추가했으나, 이는 LLM이 실수로 HTML을 흉내낼 경우에 대한 것이며 프론트 렌더러
     자체의 이스케이프 문제를 대체하지 않는다.

---

## 4. 파급 효과
- **안정성**: "저자" 필드에 쪽수가 섞여 들어가는 파싱 취약점을 구조적으로 제거.
  LLM이 마크다운 표기 방식을 미묘하게 바꾸어도(예: "쪽" → "페이지") `recommended_books`
  파싱이 실패할 수는 있지만, 실패 시에도 원본 `message`가 항상 보존되어 완전히
  깨지지 않는다.
- **일관성**: 서재 카드(ADR 0005)와 추천 카드가 동일한 "구조화 필드 병행 제공" 패턴을
  공유하여 향후 유지보수 시 예측 가능성이 높아짐.
