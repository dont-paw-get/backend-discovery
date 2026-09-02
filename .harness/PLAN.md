# PLAN — backend-discovery

## [코드 완료 · dev 배포/스크레이핑 확인 대기] 관측 인프라(dont-paw-get/infra) 연동 — dev 환경

브랜치: `관측-인프라-연동` (티켓 없음 — 배포용 임시 작업, 커밋 `[CLIAR-XX]` 태그 생략, 사용자 확정 2026-09-02)

**배경**: infra 저장소에 Prometheus/Grafana/Loki/Tempo + RCA Agent(Grafana 알림 → Discord 원인분석)가 dev 클러스터(`monitoring` ns)에 구축됨. infra의 "HTTP 5xx 에러율" / "p99 레이턴시" 알림이 동작하려면 이 서비스가 Prometheus HTTP 메트릭을 노출하고 ServiceMonitor로 스크레이핑돼야 한다.

**서비스명**: `<SVC>` = `backend-discovery` (메트릭 `application` 태그 = `OTEL_SERVICE_NAME` = 트레이스 `service.name` = k8s 리소스명, 전부 동일).

**구현 완료 (코드 세부는 `.harness/STATE.md`)**:
- Task 1: `prometheus-client` 의존성 추가, `core/metrics.py`(순수 ASGI 미들웨어 + Micrometer 호환 `http_server_requests_seconds` 히스토그램, 버킷 60초까지, `application` 라벨 = `OTEL_SERVICE_NAME`), `main.py`에 미들웨어 + `GET /metrics` 배선.
- Task 2: `k8s/overlays/dev/servicemonitor.yaml`(name `backend-discovery`, `port: http`, `path: /metrics`, `interval: 30s`) + dev kustomization resources 추가. prod overlay 미변경.
- Task 3: `k8s/overlays/dev/configmap-patch.yaml`에 `OTEL_METRICS_EXPORTER=none` / `OTEL_LOGS_EXPORTER=none` 추가.
- Task 4: 변경 없음 (`core/logging.py`가 이미 `trace_id`+`level` 출력).
- Task 5: `core/tracing.py:_EXCLUDED_URLS`에 `metrics` 추가.
- Task 6: **사용자 지시로 보류** — genre classifier 베어 모델 ID는 이번 범위에서 건드리지 않음.
- 검증: `tests/unit/test_metrics.py` 3건 신규, 전체 254건 + `ruff`/`mypy` + `kubectl kustomize k8s/overlays/dev` 통과.

**남은 작업 (dev 배포 후)**:
- [ ] dev 배포 후 `/metrics`가 `http_server_requests_seconds_bucket`/`_count`/`_sum`을 `application="backend-discovery"` 라벨로 노출하는지 확인
- [ ] Prometheus가 ServiceMonitor `backend-discovery`(`dpyb-discovery-dev`)로 실제 타깃을 잡고 스크레이핑하는지 `kubectl`/Prometheus targets에서 확인
- [ ] infra 저장소에 회신: (1) `<SVC>`=`backend-discovery` (2) ServiceMonitor `backend-discovery` / `dpyb-discovery-dev` (3) Micrometer 이름 모방이라 알림 규칙 수정 불필요 — `http_server_requests_seconds_{count,bucket}`, 라벨 `method,uri,status,outcome,application` (4) 스크레이핑 확인 결과
- [ ] (후속 검토) `/metrics`가 Ingress `path: /` 로 외부 노출됨 — dev 한정 수용, 필요 시 ingress 차단 또는 별도 포트 분리

---

## [코드 구현 완료 · dev 실측 대기] CLIAR-244: 도서 추천 카드 장르(16개 표준) 필드 추가

**배경 (2026-09-02, 스크린샷으로 재확인)**: 지금 프론트 상단 칩에 "미스터리"가 이미 표시되고 있으나, 이 값은 `ChatResponse.signals.genre_focus`(`backend-librarian`이 대화 분석으로 자유 판단한 `list[str] | str`, 코드로 확인: `librarian_response.py:58`)로 **16개 표준 `StandardGenre` Enum 매핑을 거치지 않은 값**이다. 사용자 요청: (1) 상단 칩에는 날씨/시간대/분위기만 남기고 장르 칩은 제거, (2) 대신 **각 도서 카드 내부**(저자 옆)에 그 도서의 실제 표준 장르를 표시, (3) "등록하기" 버튼 클릭 시 이 장르 값이 등록 요청 페이로드에 함께 실려야 함 — 즉 표시 이동이 아니라 `RecommendedBookCard`에 구조화 필드로 편입되어야 하는 문제.

**핵심 제약**: 기존 `POST /api/v1/classify-genre`(`GenreClassifierService`)는 CLIAR-235에서 **ISBN 전용**으로 개편되어 title/author 입력을 받지 않는다. 추천 카드(`RecommendedBookCard`)는 Tavily 웹검색 기반이라 ISBN을 안정적으로 확보하기 어렵다. 따라서 classify-genre 엔드포인트를 그대로 재호출하는 방식은 불가능하고, **추천 에이전트가 도서를 생성하는 시점에 장르까지 함께 판단하게** 해야 한다.

**구현 완료 세부**: `.harness/STATE.md` 참고.

**남은 작업**:
- [ ] dev 배포 후 실제 추천 요청으로 `recommended_books[i].genre` 필드가 채워지는지 확인
- [ ] 프론트 전달 사항 정리 완료 (`.harness/HANDOFF.md` 참고)

---

## [코드 구현 완료 · dev 실측 대기] 제목·저자 기반 알라딘 조회 API 연동 (CLIAR-237 브랜치 연장)

**배경**: CLIAR-237 dev 실측 결과 LLM이 ISBN을 못 찾아 `page_count: null`로 남는 사례가 빈번함을 확인해, 팀원(backend-book)에게 요청한 `GET /api/v1/books/search/by-title-author`(제목·저자 교집합 검색) API를 연동했다. ISBN 경로(`<!-- isbn: ... -->` 주석, `fetch_total_pages` 호출)는 완전히 제거하고 title/author 기반으로 통일했다(사용자 확정, 2026-09-02). 구현 완료 세부는 `.harness/STATE.md` 참고.

**남은 작업**:
- [ ] dev 배포 후 "백야행", "유리 세공" 등 기존에 `page_count: null`로 남던 사례 재현하여 title/author 경로 동작 확인

---

## [진행 중 · 원인 미해결] dev 환경 504 Gateway Timeout (CloudFront) — 도서 추천 응답 지연

**배경 (2026-09-02 실측)**: 사용자가 dev(CloudFront `d1wab52ln5by5k.cloudfront.net`)에서 도서 추천 요청 시 브라우저에서 `504 Gateway Timeout`(정확히 30.02초)을 다수 재현. 응답 헤더에 `via: CloudFront`, `x-cache: Error from cloudfront`가 확인되어 **CloudFront가 오리진(ALB) 응답을 기다리다 자체적으로 타임아웃**시킨 것으로 확정(백엔드가 아니라 CloudFront가 504를 만들어냄).

**로그로 확인된 실측 사실**:
- `kubectl logs`로 확인한 실제 오케스트레이터 요청 소요시간: **32초, 39초, 40.6초, 41.3초** (모두 200 성공 응답이었으나 소요시간이 김).
- 병목은 `recommend_books`(하위 추천 에이전트) 도구 하나가 17~26초를 씀(오케스트레이터 총 시간의 절반 이상).
- `strands_metrics.total_duration`(LLM 사이클 실행시간 합산)은 6~13초인데, 우리가 감싼 wall-clock(`total_duration_ms`)은 그보다 10초 이상 더 큼 — Strands가 측정하지 않는 구간(에이전트/모델 객체 생성, Bedrock 크로스리전 프로필 자체의 네트워크 latency 등)에서 시간이 추가로 소모되는 것으로 추정되나 **정확한 원인 미확인**.
- 사용자가 CloudFront의 Origin Response Timeout을 30초 → 60초로 변경한 뒤에도 504가 재현됨. 이후 CloudFront distribution이 "Deploying" 상태였을 가능성을 짚었고, 사용자가 "넘어온다"고 확인(재현 안 됨)해 이번 세션은 일단 완화된 것으로 보고 종료. **다만 재현이 사라진 게 설정 전파 완료 때문인지, 우연히 짧게 끝난 요청이었는지 확정 검증은 안 됨.**

**다음 세션이 확인/진행할 것**:
- [ ] CloudFront Origin Response Timeout이 실제로 60초로 "Deployed" 상태인지 재확인, 그리고 60초보다 오래 걸리는 요청(위 실측상 40초대는 자주 나옴)이 안전한지 몇 차례 더 재현 테스트
- [ ] ALB idle timeout도 확인 필요(`k8s/base/ingress.yaml`에 명시적 어노테이션 없어 기본값 60초로 추정 — CloudFront보다 먼저 끊길 가능성은 낮으나 미확인)
- [ ] **근본 해결(권장)**: `recommend_books` 도구의 17~26초 소요 자체를 줄이는 작업. CLIAR-158 Task 3~5(캐싱/reasoning 실측), 백로그의 "직결 스트리밍" 항목과 연계 검토. 지금처럼 타임아웃만 늘리는 건 임시방편이며, 요청이 더 길어지면(예: 5권 추천) 다시 504가 날 수 있음
- [ ] 위 "총 시간 - Strands 사이클 시간 = 10초 이상 간극"의 정확한 원인 규명(에이전트 생성 오버헤드 vs Bedrock 네트워크 latency vs 다른 요인) — 세부 계측 지점 추가하여 실측

---

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
  - [x] **(dev 배포 후 실측 완료, 2026-09-02)**: PR #40 머지·dev 배포 확인. `kubectl logs`로 실제 요청에서 `<!-- isbn: ... -->` 파싱 및 `book_metadata_client` 호출(알라딘 API가 401 반환 — 무인증 호출이 거부됨, 아래 발견 사항 참고)이 정상적으로 트리거되는 것을 확인. graceful degradation도 의도대로 동작(401이어도 전체 응답 안 깨짐).
  - [x] API wire 계약 변경 없음(`RecommendedBookCard.page_count` 필드 자체는 그대로, description만 정확도 문구로 보강) — 새 ADR 불필요로 판단, `openapi.yaml`만 description 갱신.

**dev 실측으로 발견된 후속 이슈 (별도 트랙, 코드 미착수)**:
1. **`book_metadata_api_url` 무인증 호출이 401을 반환함** — 선결 결정("우선 Authorization 없이 호출")과 달리 실제로는 인증이 필요한 것으로 보임. 다만 CLIAR-237의 graceful degradation 설계 덕분에 전체 응답이 깨지지 않고 LLM 생성값을 그대로 유지하는 것으로 안전하게 처리됨(설계가 의도대로 방어 역할을 함). `Authorization` 패스스루 추가는 아래 2번 항목(팀원 신규 API)으로 대체될 가능성이 높아 즉시 조치하지 않음.
2. **LLM이 ISBN 자체를 못 찾아 주석을 생략하는 경우가 실측상 빈번함** — "백야행", "유리 세공" 등 여러 사례에서 `page_count: null`로 남음(Tavily 검색 결과에 ISBN이 우연히 없으면 LLM이 통째로 생략). 사용자가 팀원에게 **"제목+저자로 알라딘 검색 → 최상단 결과의 isbn, totalPages 반환"** 하는 신규 API를 요청함(2026-09-02). API가 나오면 ISBN 주석 의존 없이 `BookMetadataClient`에 `fetch_by_title_author(title, author)` 메서드를 추가하는 방향으로 재설계 예정 — **다음 세션 최우선 작업**.

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
