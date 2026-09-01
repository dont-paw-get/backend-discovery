# ADR 0005: 서재 도서 구조화 응답(library_books) 및 '책 열기' 연동 계약 구축

- **상태**: Accepted
- **날짜**: 2026-08-31
- **관련 티켓**: CLIAR-196
- **참여**: 오케스트레이터 및 프론트엔드 연동 도메인

---

## 1. 배경 및 문제점

1. **텍스트 파싱의 취약성 및 과잉 카드 생성**:
   - 기존 서재 조회 응답은 LLM이 마크다운 텍스트를 자유롭게 생성(`『제목』`, `진행률: 88%` 등)하였음.
   - 프론트엔드 마크다운 렌더러가 콜론(`:`)과 줄바꿈을 도서 카드로 오인하여, 1권의 책에 대해 3개의 엉뚱한 "등록 ➔" 버튼을 마구 렌더링하는 결함이 발생함.
2. **도서 식별자(`book_id`) 누락으로 인한 '책 열기' 불가능**:
   - `SearchMyLibraryTool`이 가져온 `LibraryBookItem`에는 `book_id`가 있었으나, LLM 포맷팅 텍스트에 포함되지 않아 클라이언트가 서재 상세 화면(`book_id` 기반 라우팅)을 호출할 수 없었음.
   - LLM 텍스트에 숫자를 노출하면 사용자가 읽는 대화문에 '도서 ID: 101' 같은 배선 데이터가 섞여 어색해지는 부작용이 존재함.

---

## 2. 결정 사항

### 2.1 클라이언트 응답 전용 DTO (`LibraryBookCard`) 및 `ChatResponse.library_books` 도입
- `api/schemas/chat.py`에 계층 분리 원칙에 따른 얇은 응답 전용 스키마 `LibraryBookCard`를 정의한다:
  - `book_id: int | str` (Alias: `bookId`)
  - `title: str`
  - `author: str | None`
  - `reading_status: str | None` (Alias: `readingStatus`)
  - `progress: int | None`
- `ChatResponse`에 `library_books: list[LibraryBookCard] | None = None` 필드를 추가하고, 스트리밍 응답 헤더 및 CORS `expose_headers`에 `X-Library-Books`를 등록한다.

### 2.2 LLM 프롬프트 식별자 비노출 & 도구 콜백을 통한 데이터 전달
- `format_books_for_llm`에는 `book_id`를 노출하지 않고 순수 도서명/저자/상태만 전달하여, LLM이 식별자 숫자를 본문에 앵무새처럼 출력하는 위험을 원천 차단한다.
- `book_id`를 포함한 원본 도서 데이터는 `SearchMyLibraryTool.as_tool`의 `on_books_fetched` 콜백을 통해 서비스 레이어 ➔ `ChatResponse.library_books` 구조화 데이터로만 직접 전달된다.

### 2.3 오케스트레이터 시스템 프롬프트 정돈 (자연어 대화문 강제)
- `CAT_ORCHESTRATOR_PROMPT`, `STORK_ORCHESTRATOR_PROMPT`의 서재 안내 지침을 "콜론/줄바꿈 분할/볼드체 나열 금지, 자연스러운 한두 문장 대화문 서술"로 엄격화하여 프론트엔드 파서 오작동을 방어한다.
- 추천 도서 마크다운 카드(`### 📖`)와 서재 조회의 역할 경계를 엄격히 분리한다.

---

## 3. 프론트엔드 연동 가이드

1. **내 서재 조회 결과 렌더링**:
   - `response.library_books` 배열이 존재하는 경우, 프론트엔드는 텍스트 파싱을 거치지 않고 해당 배열의 도서 카드를 렌더링합니다.
   - 카드에는 **[책 열기]** 버튼을 노출하고, 클릭 시 기존 서재 상세 모달 또는 상세 라우트(`/library/books/{book_id}`)로 직결합니다.
2. **도서 추천(`recommend_books`)과의 구분**:
   - **도서 추천**: 본문에 `### 📖 {제목}` 카드가 포함되어 [서재에 등록하기] 버튼 노출.
   - **서재 조회**: 본문은 사서의 부드러운 대화문으로 표출되고, 구조화된 `library_books` 데이터를 기반으로 [책 열기] 버튼 노출.

---

## 4. 파급 효과
- **안정성**: 텍스트 파싱 취약점 제거 및 프론트엔드-백엔드 간 견고한 DTO 계약 확립.
- **사용자 경험 (UX)**: 사서의 자연스러운 안내 말풍선 + 하단에 정확한 서재 도서 '책 열기' UI 제공.
