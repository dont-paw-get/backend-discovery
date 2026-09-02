# PLAN — backend-discovery

## [계획 초안 · 사용자 확인 대기] 도서 추천 카드 장르(16개 표준) 필드 추가

**배경**: 2026-09-02 사용자 지적 — 추천 응답(`RecommendedBookCard`)에 장르 필드가 없어 프론트가 등록 화면에서 장르를 자동 채울 수 없다. 실제 추천 도서의 장르를 기존 `StandardGenre`(ERD 16개 표준 Enum, `backend-book`의 `genre_type`과 1:1 동기화됨) 규격에 맞춰 내려주기로 확정.

**핵심 제약**: 기존 `POST /api/v1/classify-genre`(`GenreClassifierService`)는 CLIAR-235에서 **ISBN 전용**으로 개편되어 title/author 입력을 받지 않는다. 그런데 추천 카드(`RecommendedBookCard`)에는 ISBN이 없다(Tavily 웹 검색 결과 기반이라 ISBN을 안정적으로 확보하기 어려움). 따라서 classify-genre 엔드포인트를 그대로 호출하는 방식은 불가능하고, **추천 에이전트가 도서를 생성하는 시점에 장르까지 함께 판단하게** 해야 한다.

**설계 방향 (제안)**:
1. `LIBRARIAN_SYSTEM_PROMPT`(cat/stork 둘 다)의 마크다운 템플릿에 `- **장르**: {16개 Enum 중 하나}` 라인 추가. 프롬프트에 16개 Enum 목록을 명시하고, 반드시 그 중 하나(영문 대문자, 모르면 `NONE`)로만 작성하도록 지시(`GENRE_CLASSIFIER_SYSTEM_PROMPT`의 16개 항목 설명을 재사용/공유 상수화 검토).
2. `post_processor.py`에 `_GENRE_LINE_PATTERN` 정규식 추가, `parse_recommended_books_from_markdown`이 장르 라인을 파싱.
3. 파싱된 원문 문자열은 `domain/genre/classifier.py`의 기존 순수 함수 `match_standard_genre`(이미 완화 매칭 로직 보유)로 `StandardGenre` Enum에 매핑 — 새 매칭 로직을 중복 구현하지 않고 재사용. LLM이 형식을 어겨도(예: "미스터리" 한글로만 씀) `match_standard_genre`가 완화 매칭.
4. `RecommendedBookFields`(TypedDict)와 `RecommendedBookCard`(Pydantic)에 `genre: StandardGenre` 필드 추가(매칭 실패 시 `StandardGenre.NONE`).
5. `truncate_books_by_count`는 블록 단위 자르기라 영향 없음(장르 라인이 블록 안에 포함되면 그대로 보존됨) — 확인만 하고 로직 변경 불필요할 가능성 높음.
6. 적용 범위: `RecommendedBookCard`(추천, 동기 `chat`만 제공)에 한정. `LibraryBookCard`(내 서재 조회, `backend-book` 원본 데이터 그대로 전달)는 이번 범위 아님(서재 도서는 이미 backend-book이 자체 genre_type을 갖고 있을 가능성이 높아 discovery가 재분류할 필요가 없음 — 확인 필요 시 별도 논의).
7. `docs/api/openapi.yaml`의 `RecommendedBookCard` 스키마에 `genre` 필드 추가(우선 반영 대상, AGENTS.md 동기화 규칙).

**확인 필요 (사용자 컨펌 대기)**:
- 스트리밍(`stream_chat`) 경로는 CLIAR-229 때 헤더 확정 시점 제약으로 `recommended_books` 자체를 제공하지 않기로 결정된 상태(동기 `chat`만 제공). 장르 필드도 동일하게 동기 경로에만 적용하면 되는지, 혹은 스트리밍 구조화 출력 자체를 이번에 재검토할지.
- 티켓 번호 미정 — 신규 티켓 생성 여부 확인 필요.

**남은 작업(컨펌 후 착수)**:
- [ ] 티켓 번호 확정 및 `develop`에서 새 브랜치 분기
- [ ] Task 1: `LIBRARIAN_SYSTEM_PROMPT`(cat/stork) 마크다운 템플릿에 장르 라인 추가
- [ ] Task 2: `post_processor.py` 장르 파싱 + `match_standard_genre` 연동
- [ ] Task 3: `RecommendedBookCard`/`RecommendedBookFields` 스키마에 `genre` 필드 추가, `openapi.yaml` 동기화
- [ ] Task 4: 단위 테스트(파서, 스키마, fallback NONE 매칭) 추가 및 전체 회귀 확인
- [ ] Task 5: dev 배포 후 실제 추천 요청으로 `genre` 필드 확인, 하네스 문서 동기화


## 진행 순서 (2026-09-01 확정)

CLIAR-171과 CLIAR-216이 `src/discovery/domain/orchestrator/agent.py`의 같은 페르소나 프롬프트 상수를 건드리므로 병행하지 않는다.
프롬프트를 **축소하는 작업(CLIAR-171)이 확장하는 작업(CLIAR-216)보다 먼저**다.

| 순서 | 티켓 | 범위 | 선행 조건 |
| --- | --- | --- | --- |
| 1 | **CLIAR-158** | ✅ **완료·develop 머지** (Task 1·2 코드 구현 완료 및 머지. Task 3~5는 dev 실측 필요 — 별도 스파이크로 처리) | 없음 |
| 2 | **CLIAR-215** (QA기반 최적화a) | ✅ **완료** — Task 1(실측 러너 및 실측 완료)·Task 2(인증 Presence Check, 401, ADR 0007)·Task 3(위기 109 핫라인 게이트)·Task 4(공백 422 및 입력 게이트)·Task 5(P1 회귀 확인)·Task 6(단위 테스트 196건 통과) | 없음 |
| 3 | **CLIAR-171** | ✅ **완료** — Task 1-0(search_books 페이로드 축소) + Task 1(오케스트레이터 카드 재생성 제거 및 splice 결합) + Task 2(리전/프로필 비교) + Task 3(추론 파라미터 튜닝) | CLIAR-215 완료 |
| 4 | **CLIAR-229** | ✅ **완료** — 도서 추천 카드 구조화 필드(`RecommendedBookCard`, 저자/쪽수 분리) + 출력 HTML 태그 노출 방어(`sanitize_html_tags`) | CLIAR-171 완료 |
| 5 | **CLIAR-235** | ✅ **완료** — 도서 장르 분류 API의 ISBN 단일 요청 필드 개편 (title/author/raw_category 제거 및 ISBN 전용 분류로 간소화) | 없음 |
| 6 | **CLIAR-236** | ✅ **완료** — 고도화 후 자잘한 버그 수정: Claude Sonnet 5 도구 호출 포맷 붕괴(assistant message prefill ValidationException) 방어 재시도 로직 (`is_tool_call_format_error`, chat/stream_chat 1회 재시도 배선, 단위 테스트 6건) | CLIAR-229 완료 |
| 7 | **CLIAR-237** | ✅ **완료** — 추천 도서 페이지수를 `RecommendBooksTool` 내부에서 `backend-book` 알라딘 실조회(`GET /api/v1/books/search?isbn=...`)로 검증. ISBN 내부 주석(`<!-- isbn: ... -->`) 파싱·제거, `BookMetadataClient` 신설, 단위 테스트 19건 | CLIAR-236 완료 |
| 8 | **CLIAR-216** (QA기반 최적화b) | 🔄 **다음 착수 대상** — 공통 가드레일 리팩터 + 안전·엣지·환각·감정 프롬프트 고도화. 블루 스위치 후 서재 오분류(미재현) 엣지 케이스를 이 티켓 Task 2에 편입 | CLIAR-237 완료 |

순서 근거: (1) CLIAR-158은 충돌 대상이 없는 순손실 제거이고 계측 기반이 이후 티켓의 판단 근거가 된다. (2) CLIAR-171이 프롬프트를 줄인 뒤에 CLIAR-216이 확장해야 재작업과 회귀 원인 혼선을 피할 수 있다. (3) CLIAR-215는 P1 안전성·인증 공백을 다루지만 구현 위치가 입력 게이트 코드와 `api/deps.py`라 프롬프트와 충돌하지 않아 앞으로 당겼다. 계획 확정 시 이 근거를 `.harness/DECISIONS.md`에 기록했다.

---

### [진행 중] CLIAR-158: 순손실 제거 및 레이턴시 계측 (Task 1·2 완료·develop 머지, Task 3~5는 후속 실측 과제)

브랜치: (머지 완료, `CLIAR-158-Latency-Observability`는 삭제됨)

Task 1(계측 모듈 & 개인정보 화이트리스트 필터링), Task 2-1(tail consult 버그 수정 & 1.5s/20s 타임아웃), Task 2-2(prefetch 결과 1회차 재사용 & 라우터 signals fallback)는 구현 완료되어 `origin/develop`에 머지됨.

#### 남은 실측 과제 (dev 배포 필요)

- [ ] **Task 3: 프롬프트 캐싱 dev 환경 히트 및 비용 실측**
  - [ ] `Settings.enable_prompt_caching` 런타임 배선 완료됨 (현재 기본값 `False` 안전 유지).
  - [ ] dev 배포 후 캐시 TTL 5분 내 연속 3턴 실행하여 `accumulated_usage.cacheReadInputTokens > 0` 실측.
  - [ ] 트래픽 패턴상 캐시 쓰기 비용 대비 읽기 이득이 확인되면 기본 활성화(`True`), 손해이면 `False` 확정 및 근거 기록.
- [ ] **Task 4: reasoning/thinking 기본 동작 확인**
  - [ ] Bedrock 측 기본 동작으로 reasoning 토큰이 발생하는지 Task 1 로그(`outputTokens` 대비 실제 응답 길이)로 실측 확인.
- [ ] **Task 5: 전후 비교표 작성 및 문서 동기화**
  - [ ] 시나리오 4종 × 3회 전후 비교표 작성 (TTFB, 총 소요, `consult` 호출 횟수, 입출력·캐시 토큰).
  - [ ] `STATE.md` 단계 완료 갱신, `HANDOFF.md` 인수인계.

---

### [완료] CLIAR-229: [오케스트레이터] 등록하기(제목·저자·페이지수 자동추출) 버그 수정 + 출력단 HTML 태그 노출 방어

브랜치: `CLIAR-229-Recommendation-Card-Structuring` (`develop`에서 분기)

**배경**: 프론트 "책 등록" 화면에서 AI 추천 도서의 "저자" 입력란에 `톰 버틀러 보던 (548쪽)`처럼 쪽수가 함께 들어가는 버그가 발견됨. 원인은 추천 카드(`### 📖`)가 CLIAR-196에서 서재 카드(`### 📚`)에 도입한 구조화 필드(`LibraryBookCard`) 패턴을 따르지 않고 여전히 순수 마크다운 텍스트로만 내려가, 프론트가 `- **저자**: {name} ({page}쪽)` 문자열 전체를 author로 파싱하기 때문. `<br>` 태그 노출 문제는 백엔드 코드에 `<br>` 생성 지점이 없음을 확인함(`grep_search`로 전체 소스 확인) — 프론트 마크다운 렌더러의 `\n`→`<br>` 변환 이스케이프 문제로 추정되나, 백엔드도 방어적으로 raw HTML 태그를 sanitize하는 안전장치를 추가한다.

- [x] **Task 1: 추천 카드 구조화 필드 도입 (핵심 수정)** — `RecommendedBookCard` 스키마(openapi.yaml + Pydantic), `ChatResponse.recommended_books`(동기 `chat` 응답만), `parse_recommended_books_from_markdown` 파서, `OrchestratorService.chat` 배선 완료
- [x] **Task 2: 출력 HTML 태그 노출 방어** — `sanitize_html_tags` 순수 함수 신설, `chat`/`stream_chat` 세션 히스토리 저장 시점에 적용 완료
- [x] **Task 3: 검증 및 문서 동기화** — 단위 테스트 12건 신규(파서 5건, sanitize 2건, 라우터 1건, 언패킹 갱신 4개 파일), 전체 단위 212건 + 통합 16건 통과, ADR 0008 작성, 하네스 문서 동기화 완료
- [x] **Task 4 (프론트엔드 전달 항목)**: 아래 "프론트엔드 조치 요청 사항" 참고

---

### [완료] CLIAR-236: 고도화 후 자잘한 버그 수정 (Claude Sonnet 5 도구 호출 포맷 붕괴 방어 재시도)

브랜치: `CLIAR-236-Post-Optimization-Bug-Fixes` (`develop`에서 분기)

**배경 (2026-09-02 dev 재현 및 로그 실측)**: CLIAR-171/CLIAR-229 배포 후 dev에서 슈빌(stork) 모드로 "명탐정 코난 추천해줘" 요청 → `switch_to`로 블루(cat)로 전환 제안 → 사용자가 전환 → 다음 요청("명탐정 코난 가장 유명한 에피소드 추천해줘" 계열, 3번째 `consult_librarian` 재호출 사이클)에서 다음 에러로 실패, 사서 fallback 문구("냥냥... 통신 연결이 잠시 끊겼다냥")가 노출됨:

```
ValidationException: The model returned the following errors: This model does not
support assistant message prefill. The conversation must end with a user message.
```

**근본 원인**: `kubectl logs`로 실제 스트림 원문을 확인한 결과, Claude Sonnet 5가 `recommend_books` 도구를 호출할 때 정상적인 Bedrock Converse `toolUse` 콘텐츠 블록이 아니라 **XML 텍스트를 그대로 assistant 텍스트로 출력**했다(`<invoke name="recommend_books"><parameter name="query">...</parameter></invoke>`). Strands가 이를 tool_use로 인식하지 못해 다음 사이클에서 정상적인 user 응답(toolResult)이 이어지지 못하고 대화가 assistant로 끝난 상태가 되어 Bedrock이 검증 오류로 거부했다. `temperature`/`top_p` 파라미터를 완전히 제거(CLIAR-171 핫픽스, PR #34/#35)한 이후 Bedrock 기본 샘플링값을 쓰게 된 것이 이 포맷 붕괴 빈도에 영향을 줬을 가능성이 있으나(Sonnet 5는 두 파라미터 모두 미지원이라 되돌릴 수 없음), 확정된 인과관계는 아니며 모델의 확률적 오류로 간주한다.

- [x] **Task 1: `chat`/`stream_chat`에 도구 호출 포맷 붕괴 재시도 로직 추가**
  - [x] `ValidationException` 메시지에 "assistant message prefill" 또는 "must end with a user message"가 포함된 경우를 식별하는 헬퍼(`is_tool_call_format_error`, `TOOL_CALL_FORMAT_ERROR_PATTERNS`) 신설
  - [x] 해당 예외가 감지되면, 오염된 `agent.messages`를 재사용하지 않고 **새 `Agent`를 세션 히스토리 기준으로 처음부터 재생성**하여 1회 재시도
  - [x] 재시도도 실패하면 기존과 동일하게 `get_llm_fallback_message`로 폴백 (무한 재시도 방지, 최대 1회로 제한)
  - [x] `chat`(동기)과 `stream_chat`(스트리밍) 양쪽에 동일 패턴 적용. 스트리밍은 첫 청크가 이미 전송된 이후 실패할 경우 재시도가 부분 응답과 섞이지 않도록 주의(첫 청크 전송 전 실패 시에만 재시도, 이미 청크가 나간 뒤에는 기존처럼 fallback chunk를 append)
- [x] **Task 2: 재현 및 회귀 테스트**
  - [x] `agent.invoke_async` 및 `agent.stream_async`가 특정 예외를 던지도록 mock하여 재시도 경로(성공/재시도 후 실패/TTFB 후 미재시도) 단위 테스트 6건 작성
  - [x] 기존 `[BEDROCK_FALLBACK]` 관련 테스트 회귀 확인
- [x] **Task 3: 검증 및 문서 동기화**
  - [x] 정적 분석(`ruff`, `mypy`) 및 전체 단위 테스트(232건) 100% 통과
  - [x] `.harness/STATE.md`, `.harness/PLAN.md`, `.harness/HANDOFF.md` 문서 동기화 완료
  - [ ] **(dev 배포 후 후속 실측)**: dev 배포 후 동일 시나리오(사서 전환 후 연속 도구 호출) 재현 시 `[FORMAT_COLLAPSE_RETRY]` 로그 및 `format_retry_triggered` 메트릭 발생 여부 실측 확인, Bedrock 예외 메시지 문구 변동 모니터링

---

### [완료] CLIAR-237: 도서 추천 총 페이지수 검색 실패 시 알라딘 API로 정확하게 가져오기

브랜치: `CLIAR-237-Page-Count-Aladin-Verification` (`develop`에서 분기)

**배경 (2026-09-02 dev 재현 및 로그 실측)**: dev 환경에서 "비즈니스/경제 책 추천해줘"를 재현한 결과, 추천 에이전트(`RecommendBooksTool` → Tavily `search_books`)가 생성한 `### 📖` 카드의 저자 줄에 `- **저자**: 모건 하우절 (약 300쪽)`처럼 근사치·불확실 표현이 그대로 섞여 나왔다. 파싱 결과 `page_count=null`이 되고 `author` 필드에도 `"모건 하우절 (약 300쪽)"`처럼 쪽수 텍스트가 오염되어 CLIAR-229에서 고쳤던 회귀가 재발했다. 근본적으로 LLM+웹검색(Tavily) 조합은 페이지수를 정확히 알지 못하거나 부정확하게 생성할 수 있는 신뢰 불가능한 소스이므로, 정규식 보강만으로는 "정확도" 문제 자체를 해결할 수 없다. 프론트 "책 등록" 폼이 이 값을 그대로 자동입력에 쓰므로, 틀린 페이지수가 서재 DB에 영구 저장되는 위험이 있다.

**해결 방향(A안, 사용자 확정 2026-09-02)**: `backend-book`이 이미 보유한 알라딘 연동 API `GET /api/v1/books/search?isbn=...`를 재사용하여, 추천 에이전트가 확보한 ISBN으로 실제 서지 데이터(`book.totalPages`)를 재조회해 LLM이 생성한 페이지수를 신뢰 가능한 값으로 덮어쓴다. 이 API는 로그인 사용자의 서재에 해당 ISBN이 이미 있으면 알라딘을 호출하지 않고 저장된 `libraryBook` 데이터를 반환하고, 없으면 알라딘에서 조회해 `book`으로 반환하며, 알라딘에도 없으면 `book` 자체가 응답에서 생략된다(수동 입력 폴백 케이스).

**실측 확인된 응답 스키마** (사용자가 실제 호출 결과 공유, 2026-09-02):
```json
{
  "alreadyRegistered": false,
  "book": {
    "title": "어린 왕자",
    "author": "앙투안 드 생텍쥐페리",
    "isbn": "9788932917245",
    "publisher": "열린책들",
    "publishedDate": "2015-10-20",
    "totalPages": 160,
    "coverUrl": "https://example.com/covers/9788932917245.jpg"
  }
}
```
이번 티켓에서는 `book.totalPages`만 사용한다(제목/저자/출판사 등 다른 필드는 CLIAR-229 마크다운 카드가 이미 담당하므로 재사용하지 않음). `alreadyRegistered=true`인 `libraryBook` 응답 스키마는 아직 실측 전이라 Task 1에서 `book`과 동일 취급 가능한지 확인 필요(필드명이 다를 경우 대응 추가).

**선결 확인 사항 (2026-09-02 방향 확정)**:
- `libraryBook`(이미 서재에 등록된 경우) 응답 스키마는 실측 전이라 `book`과 동일하다고 가정하고 구현한다. DTO는 `extra="ignore"` + 전 필드 옵셔널로 방어적으로 설계하여, 실제 필드명이 다르면 `totalPages`를 못 찾아 `None`을 반환할 뿐 예외로 전체 응답을 막지 않는다. 이후 dev 재현으로 실제 스키마가 다르면 alias만 추가한다.
- 인증 헤더는 순수 서지 조회 목적이므로 **우선 `Authorization` 없이 호출**한다. dev 재현 시 401/403이 나오면 `Authorization` 패스스루를 추가한다(현재 설계상 실패해도 graceful degradation으로 전체 응답이 막히지 않으므로 나중에 추가해도 안전).
- ISBN을 추천 에이전트가 못 찾는 경우(Tavily 웹검색 결과에 ISBN이 없는 경우)는 구조적 한계로 받아들인다 — 이 경우 `page_count`는 기존과 동일하게 LLM 생성값 또는 `null`로 남는다. 100% 커버리지는 이번 범위의 목표가 아니다.

- [x] **Task 1: 추천 에이전트가 ISBN을 확보하도록 확장**
  - [x] `LIBRARIAN_SYSTEM_PROMPT`(cat/stork 둘 다)에 `<!-- isbn: {ISBN} -->` 내부 주석 규칙(8번) 추가. 확인 불가 시 근사치("약", "대략" 등) 대신 라인 자체를 생략하도록 3번 규칙도 강화.
  - [x] `post_processor.py`의 `RecommendedBookFields`에 `isbn` 필드 추가, `parse_recommended_books_from_markdown`이 `<!-- isbn: ... -->`(10/13자리 숫자만 허용)를 파싱. `strip_isbn_comments`로 최종 응답에서 주석을 항상 제거하는 안전장치 추가.
- [x] **Task 2: `backend-book` ISBN 조회 클라이언트 (`BookMetadataClient`) 구현**
  - [x] `core/config.py`/`.env.example`에 `book_metadata_api_url`(기본값 `library_api_url`과 동일 서비스 재사용), `book_metadata_timeout_seconds`(3초) 추가.
  - [x] `domain/orchestrator/book_metadata_response.py`(`BookMetadata`, `BookMetadataSearchResponse` — `libraryBook`을 `book`으로 정규화하는 `model_validator` 포함) 및 `domain/orchestrator/tools/book_metadata_client.py`(`fetch_total_pages`) 구현. `Authorization` 헤더 없이 호출(선결 결정대로 우선 미포함), 실패 시 예외 없이 `None` 반환.
- [x] **Task 3: 페이지수 검증 배선 — 원래 계획(`OrchestratorService`) 대신 `RecommendBooksTool` 내부에서 처리 (설계 변경, 이유는 아래)**
  - [x] `RecommendBooksTool.recommend()`가 `truncate_books_by_count` 이후 `_verify_page_counts()`를 호출해 ISBN이 파싱되면 `asyncio.gather`로 병렬 검증하고, `_replace_page_count_for_title`로 저자 줄의 `(N쪽)`/`(약 N쪽)` 표기를 검증된 값으로 교체. ISBN 주석은 이 지점에서 항상 제거.
  - [x] `api/deps.py`에 `get_book_metadata_client` 의존성 추가, `get_recommend_books_tool`에 배선.
  - **설계 변경 이유**: 원래 계획은 `OrchestratorService.chat`의 `recommended_books` 조립 시점(동기 경로만)에서 검증하는 것이었으나, ISBN 주석이 오케스트레이터 응답 텍스트에 그대로 남아있으면 **스트리밍 경로에서 청크가 실시간으로 그대로 사용자에게 노출**되는 문제가 있음을 구현 중 발견했다. `RecommendBooksTool`(하위 추천 에이전트 도구) 반환 지점에서 검증과 주석 제거를 모두 끝내면 동기/스트리밍 양쪽 모두 안전하고, `OrchestratorService`는 전혀 수정할 필요가 없어졌다(더 단순한 설계로 귀결).
- [x] **Task 4: 검증 및 문서 동기화**
  - [x] 단위 테스트 19건 신규: ISBN 파서 3건 + `strip_isbn_comments` 3건(`test_post_processor.py`), `BookMetadataClient` 6건(`test_book_metadata_client.py`, 신규 파일), `RecommendBooksTool` 페이지수 검증 3건(`test_recommend_tool.py`).
  - [x] 정적 분석(`ruff`, `mypy`) 및 `pytest -m "not integration"` 247건 100% 통과(전체 회귀 없음).
  - [ ] **(dev 배포 후 후속 실측)**: "약 300쪽" 등 근사치가 나오는 도서로 재현하여 최종 `page_count`가 알라딘 실측값으로 교체되는지 확인. `libraryBook` 실제 스키마가 `book`과 다른지, `book_metadata_api_url` 무인증 호출이 401/403 없이 성공하는지 확인.
  - [x] API wire 계약 변경 없음(`RecommendedBookCard.page_count` 필드 자체는 그대로, description만 정확도 문구로 보강) — 새 ADR 불필요로 판단, `openapi.yaml`만 description 갱신.

**레이턴시 영향**: `backend-book` 조회는 동기 `chat` 응답 조립 후반(이미 `recommend_books` 완료 시점)에 추가되므로 스트리밍 TTFB에는 영향 없음. 다만 동기 경로의 총 응답 시간은 추천 권수만큼 조회가 늘어날 수 있어 `asyncio.gather`로 병렬화하고, 타임아웃을 짧게(예: 3초) 잡아 실패해도 전체 응답이 막히지 않게 한다.

**백로그로 이관 검토 항목**: 페이지수 신뢰도 플래그(`page_count_confidence: "verified"|"estimated"|"unknown"`)를 `RecommendedBookCard`에 추가해 프론트가 "확인됨" 표시를 할 수 있게 하는 것은 API 계약 확장이라 이번 범위에서는 제외하고 별도 논의.

---

### [상세 계획 수립 대상] CLIAR-216: QA 데이터셋 기반 가드레일 및 프롬프트 고도화 (CLIAR-237 완료 후 착수)

브랜치: `CLIAR-216-Prompt-Guardrails` (CLIAR-171 머지 후 `develop`에서 분기)

- [ ] **Task 1: 블루/슈빌 프롬프트 공통 가드레일(`SHARED_GUARDRAILS`) 모듈화 리팩터링**
  - `agent.py`에서 중복되는 도구 분기/서재 안내/안전 가드레일을 공통 상수로 분리하고 페르소나 어조만 조합하도록 정돈
- [ ] **Task 2: QA 46건 실측 기반 프롬프트 엣지 케이스 보강**
  - 환각 방지(없는 책 지어내기 방어 지침 강화), 감정/위로 대화의 페르소나 공감 톤 보강
- [ ] **Task 3: QA 러너(`scripts/qa_runner.py`) 전체 46건 재실측 및 통과율 검증**
- [ ] **Task 4: 정적 분석, 단위 테스트 갱신 및 문서 동기화**

### 백로그로 이관 (이번 범위 제외)

- **직결 스트리밍(Bypass) 아키텍처 변경**: Agent-as-a-Tool의 `str` 반환 계약상 불가. 의도 분기를 서비스 레이어 코드로 이관해야 하며 CLIAR-208/213의 프롬프트 분기 재구현 + `switch_to`/`signals`/`library_books` 배선 전면 영향. CLIAR-171 Task 1의 효과 측정 후 필요성 재판단
- **Early Stop(권수 충족 시 조기 중단)**: 중단할 스트림이 없고 `truncate_books_by_count`와 충돌. 기본 2권 + 수량 엄수 프롬프트로 기대 이득 이미 회수됨
- **`signals`를 헤더에서 SSE 첫 이벤트로 이관**: `get_initial_meta`의 TTFB 하한을 구조적으로 없애는 방법이지만 ADR 0003/0005 계약 변경 + 프론트 동반 수정 필요. CLIAR-158 Task 2로 실질 해소되는지 먼저 확인
- **Bedrock Guardrails 검토**: 지연을 **증가**시키므로 레이턴시 최적화 티켓과 상충. 내용상 CLIAR-215 Task 3과 중복이므로 그쪽에서 "코드 게이트 vs Guardrails" 비교로 다룬다
